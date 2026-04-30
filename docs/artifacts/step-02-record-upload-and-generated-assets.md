# Step 02 - Record Upload And Generated Assets

## Goal

Make uploads, converted files, and generated artifacts visible in the asset
catalog without breaking existing thread artifact behavior.

## What Changed

- Uploads now create `AssetKind.UPLOAD` asset records.
- Markdown companions created from convertible uploads now create
  `AssetKind.CONVERTED` records linked to the original upload through
  `source_asset_id`.
- Completed agent runs reconcile the final thread `artifacts` state into
  `AssetKind.GENERATED` records.
- Existing `present_files` behavior is unchanged: it still updates thread state
  for the current artifact panel.

## Runtime Notes

Generated asset reconciliation is best-effort and runs after the agent task
finishes. Duplicate `thread_id + storage_uri` pairs are not duplicated; missing
run/task/agent source fields are filled when possible.
