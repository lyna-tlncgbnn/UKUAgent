# Step 05 - Version Export Retention

## Goal

Add the first version/export/retention semantics without introducing object
storage or hard-delete automation.

## What Changed

- Assets include `version_group_id` and `version_number`.
- `POST /api/assets/export` creates a ZIP asset from selected assets, a task, or
  a thread.
- Deletion is soft deletion with `status=deleted` and `deleted_at`.
- Trash can restore assets by setting status back to active.
- Thread and scheduled task deletion preserve organization-shared asset files.

## Retention Rules

- Private assets tied to deleted threads/tasks are soft-deleted.
- Organization-shared assets are retained and detached from deleted source
  tasks/threads where needed.
- No automatic physical cleanup job is enabled in this version.
