# Step 03 - Assets API

## Goal

Expose asset catalog operations through authenticated Gateway APIs.

## Interfaces

- `GET /api/assets`
- `GET /api/assets/{asset_id}`
- `GET /api/assets/{asset_id}/content`
- `PATCH /api/assets/{asset_id}`
- `POST /api/assets/{asset_id}/publish`
- `POST /api/assets/{asset_id}/unpublish`
- `DELETE /api/assets/{asset_id}`
- `POST /api/assets/export`

## Access Rules

- Private assets are visible to the owner and admins.
- Organization-shared assets are visible to all authenticated users.
- Update, publish, unpublish, and delete are limited to the owner or admins.
- Thread and task filtered queries first validate ownership of that thread/task.

## Compatibility

The existing thread artifact path API remains available. Asset content serving
reuses the same active-content protections: HTML, XHTML, and SVG are downloaded
as attachments instead of being executed inline in the application origin.
