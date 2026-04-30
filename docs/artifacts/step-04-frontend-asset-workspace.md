# Step 04 - Frontend Asset Workspace

## Goal

Add a first-class workspace page for browsing, previewing, downloading, and
sharing assets.

## What Changed

- Added `/workspace/files`.
- Added a Files sidebar item.
- Added frontend asset API/types/hooks under `frontend/src/core/assets`.
- Added a file workspace with:
  - My files
  - Organization shared
  - Recent generated
  - Task outputs
  - Trash
- Asset rows now open a dedicated preview dialog instead of rendering a fixed
  right-side detail pane.
- Each asset row has a three-dot actions menu for preview, source navigation,
  download, publish/unpublish, soft delete, and restore.
- Markdown assets are fetched as text and rendered with the same Streamdown
  Markdown renderer used by chat artifacts. Other browser-previewable assets
  still render in the dialog through image or iframe previews.

## Thread Panel Compatibility

The existing chat artifact panel now prefers thread assets from `/api/assets`
when available. Older threads that only have `thread.values.artifacts` still use
the previous path-list fallback.
