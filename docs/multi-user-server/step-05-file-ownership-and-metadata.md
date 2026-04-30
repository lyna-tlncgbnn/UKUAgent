# Step 05 - File Ownership And Metadata

## Goal

Extend multi-user isolation from thread execution into thread-scoped file
access.

After Step 04, thread reads, state, history, and runs were protected, but file
routes still had a gap:

- uploads could still be accessed directly by thread ID
- artifact download/preview could still be accessed directly by thread ID
- uploaded file metadata was not yet being recorded into business storage

This step closes those file-boundary gaps and starts persisting thread file
metadata in the business database.

## What Changed

### 1. Added thread file metadata query/delete support in business storage

Updated backend file:

- `backend/app/persistence/store.py`

New methods added:

- `list_thread_files(thread_id, kind=None)`
- `delete_thread_file_by_path(thread_id, storage_path)`

These methods are the minimum needed to start managing `thread_files` as a real
owned business record instead of leaving file ownership implied only by the
filesystem layout.

### 2. Upload routes now require thread ownership

Updated backend file:

- `backend/app/gateway/routers/uploads.py`

The following upload routes now require the current user to own the target
thread when called over HTTP:

- `POST /api/threads/{thread_id}/uploads`
- `GET /api/threads/{thread_id}/uploads/list`
- `DELETE /api/threads/{thread_id}/uploads/{filename}`

Implementation notes:

- the router now calls `require_owned_thread(request, thread_id)` when a request
  context is present
- direct function-level unit tests can still call the route handlers without a
  FastAPI `Request`, which keeps the existing low-level tests usable

This means upload management now follows the same ownership boundary already
used by thread state and run routes.

### 3. Uploads now record `thread_files` business metadata

Updated backend file:

- `backend/app/gateway/routers/uploads.py`

When an authenticated owner uploads a file, the router now records a
`thread_files` row containing:

- `thread_id`
- `user_id`
- `kind`
- `filename`
- `storage_path`
- `mime_type`
- `size_bytes`

For the initial implementation:

- the original uploaded file is recorded as `ThreadFileKind.UPLOAD`
- markdown conversion companions produced during upload are recorded as
  `ThreadFileKind.ARTIFACT`

This is the first point where thread file ownership is no longer just “a file
exists under this thread directory”, but also a persistent business record.

### 4. Upload delete now removes matching file metadata

Updated backend file:

- `backend/app/gateway/routers/uploads.py`

When an uploaded file is deleted, the router now also removes matching
`thread_files` rows for:

- the original uploaded file path
- the generated `.md` companion path

This keeps the business metadata layer from drifting when users remove upload
artifacts.

### 5. Artifact access now requires thread ownership

Updated backend file:

- `backend/app/gateway/routers/artifacts.py`

The artifact route:

- `GET /api/threads/{thread_id}/artifacts/{path:path}`

now requires the current user to own the target thread before any virtual path
resolution or file serving occurs.

That protection applies to:

- normal output files
- uploaded files served through artifact URLs
- files extracted from `.skill` archives

This closes an important gap: even if a caller guessed a valid artifact URL,
they can no longer read another user's files without owning the thread.

## Why This Step Matters

Multi-user isolation is incomplete if thread messages are protected but thread
files are not.

After this step:

- upload management is owner-checked
- artifact download/preview is owner-checked
- uploaded file metadata begins to persist in the business store

This creates the first durable ownership bridge between:

- thread ID
- filesystem paths
- business metadata

## Follow-up: Asset Catalog

The later Artifact Asset Catalog workstream keeps `thread_files` as a
compatibility record but introduces `assets` as the primary user-facing file
metadata model.

In the new model:

- uploaded files are recorded as `AssetKind.UPLOAD`
- markdown conversion companions are recorded as `AssetKind.CONVERTED`
- files presented by agents are reconciled as `AssetKind.GENERATED`
- organization sharing is controlled by asset `visibility`, not by moving files
  into a shared directory

## Intentional Non-Goals For Step 05

This step does **not** yet:

- move file storage from disk to object storage
- make file listings come primarily from business storage
- backfill legacy thread files into `thread_files`
- record every output artifact generated elsewhere in the system
- move memory/profile off global runtime files

Those come in later steps.

## Tests Added Or Updated

Updated files:

- `backend/tests/test_business_storage.py`
- `backend/tests/test_uploads_router.py`
- `backend/tests/test_artifacts_router.py`

Coverage added in this step:

- business storage can now list and delete `thread_files`
- upload route rejects non-owners
- upload route records file metadata for owned threads
- upload delete route removes business metadata entries
- artifact route rejects non-owners

## Validation Notes

Validation completed in this environment:

1. syntax compilation for all changed Python files
2. focused route-level manual verification for:
   - upload rejection for non-owners
   - upload metadata recording for owners
   - upload metadata cleanup on delete
   - artifact rejection for non-owners

Result:

- `syntax-ok`
- `manual-step5-route-tests-ok`

Known local environment limitation:

- the business storage integration test still cannot execute fully on this
  machine because `aiosqlite` is not installed in the current Python runtime

That limitation is environmental rather than a logic failure in the Step 05
changes.

## Files Added Or Updated

- `backend/app/persistence/store.py`
- `backend/app/gateway/routers/uploads.py`
- `backend/app/gateway/routers/artifacts.py`
- `backend/tests/test_business_storage.py`
- `backend/tests/test_uploads_router.py`
- `backend/tests/test_artifacts_router.py`
