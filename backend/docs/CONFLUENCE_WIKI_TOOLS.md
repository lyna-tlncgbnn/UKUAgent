# Confluence Wiki Tools

DeerFlow can expose company Confluence Wiki access to the agent through Python tools. The first version is intentionally conservative: it supports searching, reading, permission inspection, child-page listing, and creating new pages. It does not provide tools for updating or deleting existing pages.

## Environment

Configure Basic Auth credentials in `.env`:

```bash
CONFLUENCE_BASE_URL=http://wiki.example.com
CONFLUENCE_USERNAME=your-confluence-username
CONFLUENCE_PASSWORD=your-confluence-password
```

Do not hard-code Wiki credentials in scripts or tool modules. If credentials were committed or shared in logs/chat, rotate the password before using the tools in a long-running agent.

## Config

Add the `wiki` group and enable the tools in `config.yaml`:

```yaml
tool_groups:
  - name: wiki

tools:
  - name: wiki_search_pages
    group: wiki
    use: deerflow.community.confluence.tools:wiki_search_pages_tool

  - name: wiki_get_page
    group: wiki
    use: deerflow.community.confluence.tools:wiki_get_page_tool

  - name: wiki_get_page_body_chunk
    group: wiki
    use: deerflow.community.confluence.tools:wiki_get_page_body_chunk_tool

  - name: wiki_get_page_permissions
    group: wiki
    use: deerflow.community.confluence.tools:wiki_get_page_permissions_tool

  - name: wiki_list_children
    group: wiki
    use: deerflow.community.confluence.tools:wiki_list_children_tool

  - name: wiki_create_page
    group: wiki
    use: deerflow.community.confluence.tools:wiki_create_page_tool
```

## Available Tools

- `wiki_search_pages(query, space_key=None, limit=10)`: searches visible pages and returns `pageId`, title, space, and URLs.
- `wiki_get_page(page_id, body_format="markdown", limit=20000)`: reads a page by `pageId` and returns metadata, version, current operations, and body content. The default body format is Markdown for agent readability. Use `body_format="agent_json"` for data analysis tasks that must read tables accurately.
- `wiki_get_page_body_chunk(page_id, body_format="markdown", offset=0, limit=20000)`: reads a subsequent body chunk in the selected format. Use this when `wiki_get_page` returns `isTruncated: true`.
- `wiki_get_page_permissions(page_id)`: returns current account operations and page restrictions.
- `wiki_list_children(page_id, limit=25)`: lists direct child pages under a page.
- `wiki_create_page(space_key, title, storage_body, parent_page_id=None)`: creates a new page using Confluence storage HTML. It refuses to create a duplicate page with the same title in the target space.

Use `pageId` as the stable identifier. Page titles are not unique across spaces or parent pages.

## Page Body Formats

`wiki_get_page` and `wiki_get_page_body_chunk` support these formats:

- `markdown`: default. Confluence rendered HTML is converted to Markdown locally. Use this for agent reading, extraction, and analysis. Tables with `rowspan` or `colspan` are expanded into rectangular Markdown tables so merged-cell values remain explicit on every affected row and column.
- `agent_json`: Confluence rendered HTML is converted to Markdown and all tables are also returned as structured JSON. Prefer this format for data analysis, strategy matrices, metric definitions, SQL rules, and business rule tables where column accuracy matters.
- `text`: plain text extracted from Confluence rendered HTML. Use this for concise summaries or keyword checks.
- `view_html`: Confluence rendered HTML from `body.view`. Use this when the caller needs HTML display output.
- `storage`: Confluence storage format from `body.storage`. This is XHTML/XML-like Confluence source content and can contain tags such as macros and page references. Use this to verify exact source content or prepare future write/update flows.
- `metadata`: only supported by `wiki_get_page`; returns page metadata without body content.

`limit` is clamped to `1000..80000` characters. The response includes `bodyLength`, `returnedLength`, and `isTruncated` so callers can detect incomplete content. There is no silent truncation.

`agent_json` adds `tables` and `tableCount`. Each table contains `caption`, `contextHeading`, `headers`, `matrix`, `rows`, `rowCount`, and `columnCount`. `matrix` preserves the full rectangular table, while `rows` maps data rows by header for agent-friendly lookup. For example, a strategy table with `device`, `dj_gl_fdc_izi`, `00B`, `00A`, `001`, `002`, `003`, and `099` columns will expose each row as an object with those exact keys after merged cells are expanded.

For long pages, read the full document like this:

1. Call `wiki_get_page(page_id, body_format="markdown")`, or `body_format="agent_json"` when table accuracy is important for data analysis.
2. If `isTruncated` is `true`, call `wiki_get_page_body_chunk(page_id, body_format="markdown", offset=<returnedLength>)` for additional Markdown body text. `agent_json` is not supported by the chunk tool; table extraction is returned by `wiki_get_page`.
3. Continue with the returned `nextOffset` while `hasMore` is `true`.
4. If Markdown conversion looks suspicious, call `wiki_get_page(page_id, body_format="storage")` to inspect the original Confluence storage body.

## Safety

The agent is not given update or delete tools in v1. Even if `wiki_get_page_permissions` reports `update` or `delete`, those operations are only informational until explicit tools are designed and enabled later.

`wiki_create_page` is still a write operation. Use it only when the user has clearly specified the target `space_key`, title, and optional `parent_page_id`.
