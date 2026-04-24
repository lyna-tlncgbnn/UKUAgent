# Step 06D - Upload Closure

## Goal
Restore image and file upload in the multi-user workspace flow without relaxing thread owner checks.

## What Changed
- Upload authorization continues to use `thread_id -> owner` validation. We did not reintroduce anonymous uploads.
- New-thread send flow was aligned so that the app gets a real `thread_id` first, then uploads files, then submits the message.
- Frontend upload requests continue to use `/api/backend/api/threads/{thread_id}/uploads`.
- The trusted frontend proxy still forwards the logged-in session identity to gateway, so upload and owner checks stay in the same user context.
- Existing `thread_files` metadata recording from Step 5 remains in place.

## Interfaces
- `POST /api/threads/{thread_id}/uploads`
- `GET /api/threads/{thread_id}/uploads/list`
- `DELETE /api/threads/{thread_id}/uploads/{filename}`
- `GET /api/threads/{thread_id}/artifacts/{artifact_path:path}`

## Verification
- Upload succeeds for authenticated users after a real thread is established.
- Uploaded files continue to be recorded in `thread_files`.
- Artifact access still requires the current user to own the thread.

## Known Limits
- If an old frontend instance is still running stale code, upload requests can still fail until the frontend is reloaded.
- Error presentation is still mostly based on backend `detail` text rather than fully split user-facing states.

## Update - First Image Preview In New Thread
- Root cause: the first uploaded image in a brand new chat could render as `not found` even though the upload itself succeeded.
- The upload API was already writing the file into the real thread, but the message rendering layer was still reading the route param `thread_id` directly.
- On `/workspace/chats/new`, that route param is still `new`, so the first preview URL was incorrectly built as `/api/backend/api/threads/new/artifacts/...`.
- After switching away and back, the route had already been replaced with the real thread id, so the same image started working.
- Fix: `MessageList` now passes the real runtime `threadId` into `MessageListItem`, and `MessageListItem` / `MessageContent` use that value for `resolveArtifactURL(...)` instead of calling `useParams()`.
- Result: first-upload image preview in a new thread now resolves against the real thread id immediately.
