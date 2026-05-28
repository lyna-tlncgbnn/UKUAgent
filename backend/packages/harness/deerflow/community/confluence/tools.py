"""Confluence Wiki tools for DeerFlow.

These tools intentionally expose only low-risk read operations plus page
creation. Updating and deleting existing pages are not available in v1.
"""

from __future__ import annotations

import json
import logging
import os
from html.parser import HTMLParser
from typing import Any

import httpx
from bs4 import BeautifulSoup, Tag
from dotenv import load_dotenv
from langchain.tools import tool
from markdownify import markdownify as html_to_markdown

logger = logging.getLogger(__name__)

load_dotenv()

DEFAULT_TIMEOUT = 20.0
BODY_PREVIEW_LIMIT = 4096
DEFAULT_BODY_LIMIT = 20000
MIN_BODY_LIMIT = 1000
MAX_BODY_LIMIT = 80000

READ_BODY_FORMATS = {"agent_json", "markdown", "text", "view_html", "storage", "metadata"}
CHUNK_BODY_FORMATS = {"markdown", "text", "view_html", "storage"}


class _PlainTextHTMLParser(HTMLParser):
    _BLOCK_TAGS = {
        "address",
        "article",
        "aside",
        "blockquote",
        "div",
        "dl",
        "fieldset",
        "figcaption",
        "figure",
        "footer",
        "form",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "header",
        "hr",
        "li",
        "main",
        "nav",
        "ol",
        "p",
        "pre",
        "section",
        "table",
        "tbody",
        "td",
        "tfoot",
        "th",
        "thead",
        "tr",
        "ul",
    }
    _SKIP_TAGS = {"script", "style"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self._SKIP_TAGS:
            self._skip_depth += 1
            return
        if tag == "br" or tag in self._BLOCK_TAGS:
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self._SKIP_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)
            return
        if tag in self._BLOCK_TAGS:
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0:
            self._parts.append(data)

    def text(self) -> str:
        lines = [" ".join(line.split()) for line in "".join(self._parts).splitlines()]
        return "\n".join(line for line in lines if line)


class ConfluenceConfigError(RuntimeError):
    """Raised when Confluence environment configuration is incomplete."""


def _json(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


def _get_config() -> tuple[str, str, str]:
    base_url = os.getenv("CONFLUENCE_BASE_URL", "").rstrip("/")
    username = os.getenv("CONFLUENCE_USERNAME", "")
    password = os.getenv("CONFLUENCE_PASSWORD", "")

    missing = [
        name
        for name, value in {
            "CONFLUENCE_BASE_URL": base_url,
            "CONFLUENCE_USERNAME": username,
            "CONFLUENCE_PASSWORD": password,
        }.items()
        if not value
    ]
    if missing:
        raise ConfluenceConfigError(f"Missing required environment variables: {', '.join(missing)}")
    return base_url, username, password


def _client() -> tuple[httpx.Client, str]:
    base_url, username, password = _get_config()
    client = httpx.Client(
        base_url=base_url,
        auth=httpx.BasicAuth(username, password),
        timeout=DEFAULT_TIMEOUT,
        trust_env=False,
    )
    return client, base_url


def _error(endpoint: str, exc: Exception | None = None, response: httpx.Response | None = None) -> str:
    payload: dict[str, Any] = {"error": True, "endpoint": endpoint}
    if isinstance(exc, ConfluenceConfigError):
        payload["message"] = str(exc)
    elif exc is not None:
        payload["message"] = f"{type(exc).__name__}: {exc}"
    if response is not None:
        payload["status_code"] = response.status_code
        payload["response"] = response.text[:1000]
    return _json(payload)


def _request_json(method: str, path: str, *, endpoint: str, **kwargs: Any) -> tuple[dict[str, Any] | None, str | None, str | None]:
    try:
        with _client()[0] as client:
            response = client.request(method, path, **kwargs)
        if response.status_code >= 400:
            return None, _error(endpoint, response=response), None
        return response.json(), None, str(response.url)
    except ConfluenceConfigError as exc:
        return None, _error(endpoint, exc=exc), None
    except Exception as exc:
        logger.exception("Confluence request failed: %s %s", method, path)
        return None, _error(endpoint, exc=exc), None


def _absolute_url(base_url: str, links: dict[str, Any], key: str) -> str:
    value = links.get(key)
    if not value:
        return ""
    if isinstance(value, str) and value.startswith("http"):
        return value
    return f"{base_url}{value}"


def _operation_names(data: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for operation in data.get("operations", []) or []:
        name = operation.get("operation") or operation.get("name") or operation.get("targetType")
        if name and name not in names:
            names.append(name)
    return names


def _page_summary(item: dict[str, Any], base_url: str) -> dict[str, Any]:
    space = item.get("space") or {}
    links = item.get("_links") or {}
    return {
        "pageId": item.get("id"),
        "title": item.get("title"),
        "spaceKey": space.get("key"),
        "spaceName": space.get("name"),
        "status": item.get("status"),
        "webUrl": _absolute_url(base_url, links, "webui"),
        "selfUrl": links.get("self") or _absolute_url(base_url, links, "self"),
    }


def _cql_quote(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _normalize_body_format(body_format: str | None, *, allow_metadata: bool, endpoint: str) -> tuple[str | None, str | None]:
    normalized = (body_format or "markdown").strip().lower().replace("-", "_")
    if normalized in {"html", "view"}:
        normalized = "view_html"
    if normalized == "json":
        normalized = "agent_json"

    allowed = READ_BODY_FORMATS if allow_metadata else CHUNK_BODY_FORMATS
    if normalized not in allowed:
        return None, _json(
            {
                "error": True,
                "endpoint": endpoint,
                "message": f"Unsupported body_format: {body_format!r}.",
                "allowedBodyFormats": sorted(allowed),
            }
        )
    return normalized, None


def _clamp_body_limit(limit: int | None) -> int:
    if limit is None:
        return DEFAULT_BODY_LIMIT
    return max(MIN_BODY_LIMIT, min(int(limit), MAX_BODY_LIMIT))


def _body_expand(body_format: str) -> str:
    if body_format == "metadata":
        return "space,version,operations"
    if body_format == "storage":
        return "space,version,body.storage,operations"
    return "space,version,body.view,operations"


def _html_to_text(html: str) -> str:
    parser = _PlainTextHTMLParser()
    parser.feed(html)
    parser.close()
    return parser.text()


def _cell_text(cell: Tag) -> str:
    return " ".join(cell.get_text(separator="\n", strip=True).split())


def _parse_span(value: Any) -> int:
    try:
        return max(1, int(value))
    except (TypeError, ValueError):
        return 1


def _clone_cell(cell: Tag) -> Tag:
    clone = BeautifulSoup(str(cell), "html.parser").find(cell.name)
    assert isinstance(clone, Tag)
    clone.attrs.pop("rowspan", None)
    clone.attrs.pop("colspan", None)
    return clone


def _empty_cell() -> Tag:
    cell = BeautifulSoup("<td></td>", "html.parser").td
    assert isinstance(cell, Tag)
    return cell


def _direct_table_rows(table: Tag) -> list[Tag]:
    rows: list[Tag] = []
    for child in table.children:
        if not isinstance(child, Tag):
            continue
        if child.name == "tr":
            rows.append(child)
        elif child.name in {"thead", "tbody", "tfoot"}:
            rows.extend(row for row in child.find_all("tr", recursive=False) if isinstance(row, Tag))
    return rows


def _normalize_table_spans(table: Tag) -> None:
    rows = _direct_table_rows(table)
    pending: dict[int, tuple[Tag, int]] = {}
    normalized_rows: list[list[Tag]] = []
    max_width = 0

    for row in rows:
        cells_by_col: dict[int, Tag] = {}
        col = 0
        source_cells = [cell for cell in row.find_all(["td", "th"], recursive=False) if isinstance(cell, Tag)]

        def use_pending_at_current_col() -> None:
            nonlocal col
            pending_cell, remaining = pending[col]
            cells_by_col[col] = _clone_cell(pending_cell)
            if remaining <= 1:
                del pending[col]
            else:
                pending[col] = (pending_cell, remaining - 1)
            col += 1

        for cell in source_cells:
            while col in pending:
                use_pending_at_current_col()

            rowspan = _parse_span(cell.get("rowspan"))
            colspan = _parse_span(cell.get("colspan"))
            for _ in range(colspan):
                cells_by_col[col] = _clone_cell(cell)
                if rowspan > 1:
                    pending[col] = (cell, rowspan - 1)
                col += 1

        for pending_col in sorted(key for key in pending if key >= col):
            col = pending_col
            use_pending_at_current_col()

        row_width = max(cells_by_col, default=-1) + 1
        max_width = max(max_width, row_width)
        normalized_rows.append([cells_by_col.get(index, _empty_cell()) for index in range(row_width)])

    for row, cells in zip(rows, normalized_rows, strict=True):
        row.clear()
        for index in range(max_width):
            row.append(_clone_cell(cells[index]) if index < len(cells) else _empty_cell())


def _normalize_table_html(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for table in soup.find_all("table"):
        if isinstance(table, Tag):
            _normalize_table_spans(table)
    return str(soup)


def _normalize_header(value: str, index: int, seen: dict[str, int]) -> str:
    base = value.strip() or f"column_{index + 1}"
    count = seen.get(base, 0) + 1
    seen[base] = count
    return base if count == 1 else f"{base}_{count}"


def _nearest_context_heading(table: Tag) -> str:
    for previous in table.find_all_previous(["h1", "h2", "h3", "h4", "h5", "h6"]):
        if isinstance(previous, Tag):
            return _cell_text(previous)
    return ""


def _table_matrix(table: Tag) -> list[list[str]]:
    matrix: list[list[str]] = []
    for row in _direct_table_rows(table):
        matrix.append([_cell_text(cell) for cell in row.find_all(["td", "th"], recursive=False)])
    return matrix


def _table_headers(table: Tag, matrix: list[list[str]]) -> tuple[list[str], int]:
    rows = _direct_table_rows(table)
    header_row_index = 0
    for index, row in enumerate(rows):
        if row.find("th", recursive=False):
            header_row_index = index
            break

    raw_headers = matrix[header_row_index] if matrix else []
    seen: dict[str, int] = {}
    return [_normalize_header(value, index, seen) for index, value in enumerate(raw_headers)], header_row_index


def _extract_tables(html: str) -> list[dict[str, Any]]:
    soup = BeautifulSoup(_normalize_table_html(html), "html.parser")
    tables: list[dict[str, Any]] = []
    for index, table in enumerate(soup.find_all("table")):
        if not isinstance(table, Tag):
            continue
        matrix = _table_matrix(table)
        if not matrix:
            continue
        headers, header_row_index = _table_headers(table, matrix)
        data_rows = matrix[header_row_index + 1 :]
        rows = [
            {
                header: data_row[column_index] if column_index < len(data_row) else ""
                for column_index, header in enumerate(headers)
            }
            for data_row in data_rows
        ]
        caption = table.find("caption", recursive=False)
        tables.append(
            {
                "index": index,
                "caption": _cell_text(caption) if isinstance(caption, Tag) else "",
                "contextHeading": _nearest_context_heading(table),
                "headers": headers,
                "matrix": matrix,
                "rows": rows,
                "rowCount": len(data_rows),
                "columnCount": max((len(row) for row in matrix), default=0),
            }
        )
    return tables


def _extract_body(data: dict[str, Any], body_format: str) -> tuple[str, str | None]:
    if body_format == "storage":
        storage = data.get("body", {}).get("storage", {}) or {}
        return storage.get("value", "") or "", storage.get("representation")

    view = data.get("body", {}).get("view", {}) or {}
    html = view.get("value", "") or ""
    if body_format == "view_html":
        return html, view.get("representation")
    if body_format == "text":
        return _html_to_text(html), view.get("representation")
    normalized_html = _normalize_table_html(html)
    return html_to_markdown(normalized_html, heading_style="ATX").strip(), view.get("representation")


def _extract_agent_json_body(data: dict[str, Any]) -> tuple[str, list[dict[str, Any]], str | None]:
    view = data.get("body", {}).get("view", {}) or {}
    html = view.get("value", "") or ""
    normalized_html = _normalize_table_html(html)
    body = html_to_markdown(normalized_html, heading_style="ATX").strip()
    return body, _extract_tables(html), view.get("representation")


def _slice_body(body: str, limit: int, offset: int = 0) -> tuple[str, int, bool]:
    start = max(0, min(int(offset), len(body)))
    end = min(start + limit, len(body))
    return body[start:end], end, end < len(body)


def _read_page_body(page_id: str, body_format: str, *, endpoint: str) -> tuple[dict[str, Any] | None, str | None]:
    data, error, _ = _request_json(
        "GET",
        f"/rest/api/content/{page_id}",
        endpoint=endpoint,
        params={"expand": _body_expand(body_format)},
    )
    if error:
        return None, error
    assert data is not None
    return data, None


@tool("wiki_search_pages", parse_docstring=True)
def wiki_search_pages_tool(query: str, space_key: str | None = None, limit: int = 10) -> str:
    """Search visible Confluence Wiki pages by keyword.

    Args:
        query: Keyword or phrase to search in page title and content.
        space_key: Optional Confluence space key, such as UKU, MIN, or RESEARCH.
        limit: Maximum number of pages to return. Default is 10.
    """
    limit = max(1, min(limit, 25))
    quoted_query = _cql_quote(query)
    cql_parts = ["type = page", f'(title ~ "{quoted_query}" or text ~ "{quoted_query}")']
    if space_key:
        cql_parts.append(f'space = "{_cql_quote(space_key)}"')
    cql = " and ".join(cql_parts)

    try:
        with _client()[0] as client:
            base_url = str(client.base_url).rstrip("/")
            response = client.get(
                "/rest/api/content/search",
                params={"cql": cql, "limit": limit, "expand": "space,version"},
            )
        if response.status_code >= 400:
            return _error("wiki_search_pages", response=response)
        data = response.json()
        results = [_page_summary(item, base_url) for item in data.get("results", [])]
        return _json({"query": query, "spaceKey": space_key, "totalResults": len(results), "results": results})
    except ConfluenceConfigError as exc:
        return _error("wiki_search_pages", exc=exc)
    except Exception as exc:
        logger.exception("Confluence search failed")
        return _error("wiki_search_pages", exc=exc)


@tool("wiki_get_page", parse_docstring=True)
def wiki_get_page_tool(page_id: str, body_format: str = "markdown", limit: int = DEFAULT_BODY_LIMIT) -> str:
    """Read a Confluence Wiki page by pageId.

    Args:
        page_id: Confluence page id from the page URL or search results.
        body_format: Body format to return: markdown, agent_json, text, view_html, storage, or metadata. Default is markdown.
        limit: Maximum body characters to return. Values are clamped to 1000..80000. Default is 20000.
    """
    normalized_format, format_error = _normalize_body_format(body_format, allow_metadata=True, endpoint="wiki_get_page")
    if format_error:
        return format_error
    assert normalized_format is not None

    data, error = _read_page_body(page_id, normalized_format, endpoint="wiki_get_page")
    if error:
        return error
    assert data is not None
    try:
        base_url, _, _ = _get_config()
    except Exception:
        base_url = ""
    output = _page_summary(data, base_url)
    output.update(
        {
            "version": data.get("version", {}).get("number"),
            "bodyFormat": normalized_format,
            "operations": _operation_names(data),
        }
    )

    if normalized_format == "metadata":
        return _json(output)

    if normalized_format == "agent_json":
        body, tables, _ = _extract_agent_json_body(data)
    else:
        body, representation = _extract_body(data, normalized_format)
        tables = None
    normalized_limit = _clamp_body_limit(limit)
    returned_body, returned_length, is_truncated = _slice_body(body, normalized_limit)
    output.update(
        {
            "body": returned_body,
            "bodyLength": len(body),
            "returnedLength": returned_length,
            "isTruncated": is_truncated,
        }
    )
    if tables is not None:
        output.update(
            {
                "tables": tables,
                "tableCount": len(tables),
            }
        )
    if normalized_format == "storage":
        output.update(
            {
                "bodyRepresentation": representation,
                "bodyStorageLength": len(body),
                "bodyStoragePreview": body[:BODY_PREVIEW_LIMIT],
            }
        )
    return _json(output)


@tool("wiki_get_page_body_chunk", parse_docstring=True)
def wiki_get_page_body_chunk_tool(
    page_id: str,
    body_format: str = "markdown",
    offset: int = 0,
    limit: int = DEFAULT_BODY_LIMIT,
) -> str:
    """Read a chunk of a Confluence Wiki page body by pageId.

    Args:
        page_id: Confluence page id from the page URL or search results.
        body_format: Body format to return: markdown, text, view_html, or storage. Default is markdown.
        offset: Character offset in the selected body format. Default is 0.
        limit: Maximum body characters to return. Values are clamped to 1000..80000. Default is 20000.
    """
    normalized_format, format_error = _normalize_body_format(
        body_format,
        allow_metadata=False,
        endpoint="wiki_get_page_body_chunk",
    )
    if format_error:
        return format_error
    assert normalized_format is not None

    data, error = _read_page_body(page_id, normalized_format, endpoint="wiki_get_page_body_chunk")
    if error:
        return error
    assert data is not None

    try:
        base_url, _, _ = _get_config()
    except Exception:
        base_url = ""

    body, representation = _extract_body(data, normalized_format)
    normalized_limit = _clamp_body_limit(limit)
    normalized_offset = max(0, int(offset))
    returned_body, next_offset, has_more = _slice_body(body, normalized_limit, normalized_offset)

    output = _page_summary(data, base_url)
    output.update(
        {
            "version": data.get("version", {}).get("number"),
            "bodyFormat": normalized_format,
            "body": returned_body,
            "bodyLength": len(body),
            "offset": min(normalized_offset, len(body)),
            "returnedLength": len(returned_body),
            "nextOffset": next_offset if has_more else None,
            "hasMore": has_more,
        }
    )
    if normalized_format == "storage":
        output["bodyRepresentation"] = representation
    return _json(output)


@tool("wiki_get_page_permissions", parse_docstring=True)
def wiki_get_page_permissions_tool(page_id: str) -> str:
    """Get current account operations and restrictions for a Confluence Wiki page.

    Args:
        page_id: Confluence page id from the page URL or search results.
    """
    page, page_error, _ = _request_json(
        "GET",
        f"/rest/api/content/{page_id}",
        endpoint="wiki_get_page_permissions",
        params={"expand": "space,version,operations"},
    )
    if page_error:
        return page_error

    restrictions, restrictions_error, _ = _request_json(
        "GET",
        f"/rest/api/content/{page_id}/restriction/byOperation",
        endpoint="wiki_get_page_permissions.restrictions",
    )
    assert page is not None
    return _json(
        {
            "pageId": page.get("id"),
            "title": page.get("title"),
            "spaceKey": (page.get("space") or {}).get("key"),
            "operations": _operation_names(page),
            "restrictions": None if restrictions_error else restrictions,
            "restrictionError": json.loads(restrictions_error) if restrictions_error else None,
        }
    )


@tool("wiki_list_children", parse_docstring=True)
def wiki_list_children_tool(page_id: str, limit: int = 25) -> str:
    """List direct child pages under a Confluence Wiki page.

    Args:
        page_id: Parent Confluence page id.
        limit: Maximum number of child pages to return. Default is 25.
    """
    limit = max(1, min(limit, 50))
    data, error, _ = _request_json(
        "GET",
        f"/rest/api/content/{page_id}/child/page",
        endpoint="wiki_list_children",
        params={"limit": limit, "expand": "space,version"},
    )
    if error:
        return error
    assert data is not None
    try:
        base_url, _, _ = _get_config()
    except Exception:
        base_url = ""
    children = [_page_summary(item, base_url) for item in data.get("results", [])]
    return _json({"parentPageId": page_id, "totalResults": len(children), "children": children})


@tool("wiki_create_page", parse_docstring=True)
def wiki_create_page_tool(
    space_key: str,
    title: str,
    storage_body: str,
    parent_page_id: str | None = None,
) -> str:
    """Create a new Confluence Wiki page using Confluence storage format.

    Args:
        space_key: Confluence space key where the new page will be created.
        title: Title for the new page.
        storage_body: Page body in Confluence storage HTML format.
        parent_page_id: Optional parent page id. When provided, the new page is created as a child page.
    """
    search_query = title.strip()
    if not space_key.strip() or not search_query or not storage_body.strip():
        return _json(
            {
                "error": True,
                "endpoint": "wiki_create_page",
                "message": "space_key, title, and storage_body are required.",
            }
        )

    try:
        with _client()[0] as client:
            base_url = str(client.base_url).rstrip("/")
            existing = client.get(
                "/rest/api/content",
                params={
                    "spaceKey": space_key.strip(),
                    "title": search_query,
                    "type": "page",
                    "status": "current",
                    "limit": 1,
                    "expand": "space",
                },
            )
            if existing.status_code >= 400:
                return _error("wiki_create_page.preflight", response=existing)
            existing_results = existing.json().get("results", [])
            if existing_results:
                return _json(
                    {
                        "error": True,
                        "endpoint": "wiki_create_page",
                        "message": "A page with this title already exists in the target space. Refusing to create a duplicate.",
                        "existingPage": _page_summary(existing_results[0], base_url),
                    }
                )

            payload: dict[str, Any] = {
                "type": "page",
                "title": search_query,
                "space": {"key": space_key.strip()},
                "body": {"storage": {"value": storage_body, "representation": "storage"}},
            }
            if parent_page_id:
                payload["ancestors"] = [{"id": str(parent_page_id)}]

            response = client.post("/rest/api/content", json=payload)
            if response.status_code >= 400:
                return _error("wiki_create_page", response=response)
            data = response.json()
            return _json({"created": True, "page": _page_summary(data, base_url)})
    except ConfluenceConfigError as exc:
        return _error("wiki_create_page", exc=exc)
    except Exception as exc:
        logger.exception("Confluence page creation failed")
        return _error("wiki_create_page", exc=exc)
