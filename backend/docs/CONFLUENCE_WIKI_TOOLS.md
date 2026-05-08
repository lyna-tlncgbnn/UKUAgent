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
- `wiki_get_page(page_id)`: reads a page by `pageId` and returns metadata, version, current operations, and a Confluence `body.storage` preview.
- `wiki_get_page_permissions(page_id)`: returns current account operations and page restrictions.
- `wiki_list_children(page_id, limit=25)`: lists direct child pages under a page.
- `wiki_create_page(space_key, title, storage_body, parent_page_id=None)`: creates a new page using Confluence storage HTML. It refuses to create a duplicate page with the same title in the target space.

Use `pageId` as the stable identifier. Page titles are not unique across spaces or parent pages.

## Safety

The agent is not given update or delete tools in v1. Even if `wiki_get_page_permissions` reports `update` or `delete`, those operations are only informational until explicit tools are designed and enabled later.

`wiki_create_page` is still a write operation. Use it only when the user has clearly specified the target `space_key`, title, and optional `parent_page_id`.
