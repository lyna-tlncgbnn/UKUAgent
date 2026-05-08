"""Confluence Wiki tools for DeerFlow.

These tools intentionally expose only low-risk read operations plus page
creation. Updating and deleting existing pages are not available in v1.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

import httpx
from dotenv import load_dotenv
from langchain.tools import tool

logger = logging.getLogger(__name__)

load_dotenv()

DEFAULT_TIMEOUT = 20.0
BODY_PREVIEW_LIMIT = 4096


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
def wiki_get_page_tool(page_id: str) -> str:
    """Read a Confluence Wiki page by pageId.

    Args:
        page_id: Confluence page id from the page URL or search results.
    """
    data, error, _ = _request_json(
        "GET",
        f"/rest/api/content/{page_id}",
        endpoint="wiki_get_page",
        params={"expand": "space,version,body.storage,operations"},
    )
    if error:
        return error
    assert data is not None
    try:
        base_url, _, _ = _get_config()
    except Exception:
        base_url = ""
    body = data.get("body", {}).get("storage", {}).get("value", "") or ""
    output = _page_summary(data, base_url)
    output.update(
        {
            "version": data.get("version", {}).get("number"),
            "bodyRepresentation": data.get("body", {}).get("storage", {}).get("representation"),
            "bodyStorageLength": len(body),
            "bodyStoragePreview": body[:BODY_PREVIEW_LIMIT],
            "operations": _operation_names(data),
        }
    )
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
