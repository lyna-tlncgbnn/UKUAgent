# Step 01 - Asset Metadata Foundation

## Goal

Introduce a first-class business metadata model for user-owned and
organization-shared files.

## What Changed

- Added `AssetRecord` and supporting enums:
  - `AssetKind`
  - `AssetVisibility`
  - `AssetStatus`
- Added business-store methods for creating, listing, updating, publishing,
  unpublishing, and soft-deleting assets.
- Kept `thread_files` as a compatibility record for existing upload behavior.

## Storage Model

Assets store file identity, ownership, source links, sharing state, status,
version fields, and a storage URI. The initial storage URI remains compatible
with the existing thread filesystem and virtual sandbox paths.

## Intentional Boundaries

- No object storage migration in this step.
- No team-level ACL UI in this step.
- `restricted` visibility is reserved for future team/user ACL work.
