# Artifact Asset Catalog

Last updated: 2026-04-30

## Purpose

This workstream upgrades thread-local artifacts into a user-owned asset catalog
for internal company use.

The catalog introduces:

- a private "my files" space for each user
- an organization-shared space for files explicitly published internally
- durable metadata for uploads, converted files, generated artifacts, and export
  packages
- compatibility with the existing thread artifact panel and artifact URLs

## Current Status

Completed:

- Step 01: asset metadata foundation
- Step 02: upload/conversion/generated asset recording
- Step 03: Assets API
- Step 04: frontend asset workspace
- Step 05: version/export/retention first pass

## Runtime Decisions

- Organization sharing is represented by `visibility=org_shared`; no anonymous
  public access is introduced.
- Files remain in their existing thread-backed filesystem locations.
- The shared space is a metadata query, not a physical shared directory.
- Asset deletion is soft deletion in this version.
- Existing `/api/threads/{thread_id}/artifacts/{path}` URLs remain available
  for backward compatibility.

## Step Documents

- [Step 01 - Asset Metadata Foundation](step-01-asset-metadata-foundation.md)
- [Step 02 - Record Upload And Generated Assets](step-02-record-upload-and-generated-assets.md)
- [Step 03 - Assets API](step-03-assets-api.md)
- [Step 04 - Frontend Asset Workspace](step-04-frontend-asset-workspace.md)
- [Step 05 - Version Export Retention](step-05-version-export-retention.md)
