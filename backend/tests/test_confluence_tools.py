"""Tests for Confluence Wiki tools."""

from __future__ import annotations

import json
from typing import Any

from deerflow.community.confluence import tools as confluence_tools


def _tool_result(tool: Any, **kwargs: Any) -> dict[str, Any]:
    return json.loads(tool.func(**kwargs))


def _page(body: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": "123",
        "title": "Quarterly Metrics",
        "status": "current",
        "space": {"key": "UKU", "name": "UKU Space"},
        "version": {"number": 7},
        "operations": [{"operation": "read"}, {"operation": "update"}],
        "body": body,
        "_links": {
            "webui": "/spaces/UKU/pages/123/Quarterly+Metrics",
            "self": "https://wiki.example.com/rest/api/content/123",
        },
    }


def _patch_request(monkeypatch, page: dict[str, Any], calls: list[dict[str, Any]] | None = None) -> None:
    def _fake_request_json(method: str, path: str, *, endpoint: str, **kwargs: Any):
        if calls is not None:
            calls.append({"method": method, "path": path, "endpoint": endpoint, **kwargs})
        return page, None, "https://wiki.example.com/rest/api/content/123"

    monkeypatch.setattr(confluence_tools, "_request_json", _fake_request_json)
    monkeypatch.setattr(confluence_tools, "_get_config", lambda: ("https://wiki.example.com", "user", "pass"))


def test_wiki_get_page_defaults_to_markdown(monkeypatch) -> None:
    calls: list[dict[str, Any]] = []
    _patch_request(
        monkeypatch,
        _page({"view": {"value": "<h1>Overview</h1><p>Hello <strong>World</strong></p>", "representation": "view"}}),
        calls,
    )

    result = _tool_result(confluence_tools.wiki_get_page_tool, page_id="123")

    assert calls[0]["params"]["expand"] == "space,version,body.view,operations"
    assert result["pageId"] == "123"
    assert result["title"] == "Quarterly Metrics"
    assert result["version"] == 7
    assert result["bodyFormat"] == "markdown"
    assert "# Overview" in result["body"]
    assert "Hello" in result["body"]
    assert "World" in result["body"]
    assert result["bodyLength"] == len(result["body"])
    assert result["returnedLength"] == len(result["body"])
    assert result["isTruncated"] is False
    assert result["operations"] == ["read", "update"]


def test_wiki_get_page_storage_returns_raw_storage_and_compat_fields(monkeypatch) -> None:
    storage = '<p>Hello</p><ac:structured-macro ac:name="toc" />'
    calls: list[dict[str, Any]] = []
    _patch_request(
        monkeypatch,
        _page({"storage": {"value": storage, "representation": "storage"}}),
        calls,
    )

    result = _tool_result(confluence_tools.wiki_get_page_tool, page_id="123", body_format="storage")

    assert calls[0]["params"]["expand"] == "space,version,body.storage,operations"
    assert result["bodyFormat"] == "storage"
    assert result["body"] == storage
    assert result["bodyRepresentation"] == "storage"
    assert result["bodyStorageLength"] == len(storage)
    assert result["bodyStoragePreview"] == storage


def test_wiki_get_page_markdown_expands_table_rowspan(monkeypatch) -> None:
    html = """
    <table>
      <tr>
        <th>device</th><th>dj_gl_fdc_izi</th><th>00B</th><th>00A</th><th>001</th><th>002</th><th>003</th><th>099</th>
      </tr>
      <tr>
        <td rowspan="6">iOS</td><td>&gt;=800</td>
        <td rowspan="2">A</td><td rowspan="2">F</td><td rowspan="2">F</td><td rowspan="2">A</td><td rowspan="2">A</td><td rowspan="2">F</td>
      </tr>
      <tr><td>600-800</td></tr>
      <tr><td>500-600</td><td>B</td><td></td><td></td><td>B</td><td>B</td><td></td></tr>
      <tr><td>410-500</td><td>F</td><td></td><td></td><td>F</td><td>F</td><td></td></tr>
      <tr><td>270-410</td><td>U</td><td>U</td><td>U</td><td>U</td><td>U</td><td>U</td></tr>
      <tr><td>&lt;270</td><td>R</td><td>R</td><td>R</td><td>R</td><td>R</td><td>R</td></tr>
    </table>
    """
    _patch_request(monkeypatch, _page({"view": {"value": html, "representation": "view"}}))

    result = _tool_result(confluence_tools.wiki_get_page_tool, page_id="123")

    assert "| iOS | >=800 | A | F | F | A | A | F |" in result["body"]
    assert "| iOS | 600-800 | A | F | F | A | A | F |" in result["body"]
    assert "| iOS | <270 | R | R | R | R | R | R |" in result["body"]


def test_wiki_get_page_agent_json_extracts_structured_tables(monkeypatch) -> None:
    html = """
    <h2>首申定价&提现策略</h2>
    <p>20260522</p>
    <table>
      <tr>
        <th>device</th><th>dj_gl_fdc_izi</th><th>00B</th><th>00A</th><th>001</th><th>002</th><th>003</th><th>099</th>
      </tr>
      <tr>
        <td rowspan="6">iOS</td><td>&gt;=800</td>
        <td rowspan="2">A</td><td rowspan="2">F</td><td rowspan="2">F</td><td rowspan="2">A</td><td rowspan="2">A</td><td rowspan="2">F</td>
      </tr>
      <tr><td>600-800</td></tr>
      <tr><td>500-600</td><td>B</td><td></td><td></td><td>B</td><td>B</td><td></td></tr>
    </table>
    """
    _patch_request(monkeypatch, _page({"view": {"value": html, "representation": "view"}}))

    result = _tool_result(confluence_tools.wiki_get_page_tool, page_id="123", body_format="agent_json")

    assert result["bodyFormat"] == "agent_json"
    assert "| iOS | 600-800 | A | F | F | A | A | F |" in result["body"]
    assert result["tableCount"] == 1
    table = result["tables"][0]
    assert table["index"] == 0
    assert table["caption"] == ""
    assert table["contextHeading"] == "首申定价&提现策略"
    assert table["headers"] == ["device", "dj_gl_fdc_izi", "00B", "00A", "001", "002", "003", "099"]
    assert table["matrix"][2] == ["iOS", "600-800", "A", "F", "F", "A", "A", "F"]
    assert table["rows"][1] == {
        "device": "iOS",
        "dj_gl_fdc_izi": "600-800",
        "00B": "A",
        "00A": "F",
        "001": "F",
        "002": "A",
        "003": "A",
        "099": "F",
    }
    assert table["rowCount"] == 3
    assert table["columnCount"] == 8


def test_wiki_get_page_agent_json_alias_and_header_fallbacks(monkeypatch) -> None:
    html = """
    <table>
      <tr><td></td><td>status</td><td>status</td></tr>
      <tr><td>A</td><td>ok</td><td>pass</td></tr>
    </table>
    """
    _patch_request(monkeypatch, _page({"view": {"value": html, "representation": "view"}}))

    result = _tool_result(confluence_tools.wiki_get_page_tool, page_id="123", body_format="json")

    assert result["bodyFormat"] == "agent_json"
    assert result["tables"][0]["headers"] == ["column_1", "status", "status_2"]
    assert result["tables"][0]["rows"] == [{"column_1": "A", "status": "ok", "status_2": "pass"}]


def test_wiki_get_page_agent_json_body_limit(monkeypatch) -> None:
    html = f"<p>{'x' * 1500}</p><table><tr><th>A</th></tr><tr><td>B</td></tr></table>"
    _patch_request(monkeypatch, _page({"view": {"value": html, "representation": "view"}}))

    result = _tool_result(confluence_tools.wiki_get_page_tool, page_id="123", body_format="agent_json", limit=1000)

    assert result["returnedLength"] == 1000
    assert result["isTruncated"] is True
    assert result["tableCount"] == 1
    assert result["tables"][0]["rows"] == [{"A": "B"}]


def test_wiki_get_page_view_html_text_and_metadata(monkeypatch) -> None:
    html = "<h2>Overview</h2><p>First paragraph.</p><p>Second paragraph.</p>"
    _patch_request(monkeypatch, _page({"view": {"value": html, "representation": "view"}}))

    html_result = _tool_result(confluence_tools.wiki_get_page_tool, page_id="123", body_format="view_html")
    text_result = _tool_result(confluence_tools.wiki_get_page_tool, page_id="123", body_format="text")
    metadata_result = _tool_result(confluence_tools.wiki_get_page_tool, page_id="123", body_format="metadata")

    assert html_result["body"] == html
    assert text_result["body"] == "Overview\nFirst paragraph.\nSecond paragraph."
    assert metadata_result["bodyFormat"] == "metadata"
    assert "body" not in metadata_result
    assert metadata_result["operations"] == ["read", "update"]


def test_wiki_get_page_truncates_with_explicit_state(monkeypatch) -> None:
    content = "x" * 1500
    _patch_request(monkeypatch, _page({"storage": {"value": content, "representation": "storage"}}))

    result = _tool_result(confluence_tools.wiki_get_page_tool, page_id="123", body_format="storage", limit=1000)

    assert result["body"] == "x" * 1000
    assert result["bodyLength"] == 1500
    assert result["returnedLength"] == 1000
    assert result["isTruncated"] is True


def test_wiki_get_page_body_chunk_reads_subsequent_chunks(monkeypatch) -> None:
    content = "x" * 2500
    _patch_request(monkeypatch, _page({"storage": {"value": content, "representation": "storage"}}))

    first = _tool_result(
        confluence_tools.wiki_get_page_body_chunk_tool,
        page_id="123",
        body_format="storage",
        offset=1000,
        limit=1000,
    )
    last = _tool_result(
        confluence_tools.wiki_get_page_body_chunk_tool,
        page_id="123",
        body_format="storage",
        offset=2000,
        limit=1000,
    )

    assert first["body"] == "x" * 1000
    assert first["offset"] == 1000
    assert first["nextOffset"] == 2000
    assert first["hasMore"] is True
    assert last["body"] == "x" * 500
    assert last["offset"] == 2000
    assert last["nextOffset"] is None
    assert last["hasMore"] is False


def test_wiki_get_page_rejects_invalid_body_format() -> None:
    result = _tool_result(confluence_tools.wiki_get_page_tool, page_id="123", body_format="pdf")

    assert result["error"] is True
    assert "Unsupported body_format" in result["message"]
    assert result["allowedBodyFormats"] == ["agent_json", "markdown", "metadata", "storage", "text", "view_html"]


def test_wiki_get_page_body_chunk_rejects_agent_json() -> None:
    result = _tool_result(confluence_tools.wiki_get_page_body_chunk_tool, page_id="123", body_format="agent_json")

    assert result["error"] is True
    assert result["endpoint"] == "wiki_get_page_body_chunk"
    assert result["allowedBodyFormats"] == ["markdown", "storage", "text", "view_html"]


def test_wiki_get_page_returns_request_error(monkeypatch) -> None:
    error = json.dumps({"error": True, "endpoint": "wiki_get_page", "status_code": 404})

    def _fake_request_json(method: str, path: str, *, endpoint: str, **kwargs: Any):
        return None, error, None

    monkeypatch.setattr(confluence_tools, "_request_json", _fake_request_json)

    result = _tool_result(confluence_tools.wiki_get_page_tool, page_id="missing")

    assert result == {"error": True, "endpoint": "wiki_get_page", "status_code": 404}
