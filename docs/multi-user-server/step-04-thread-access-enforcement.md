# Step 04 - Thread Access Enforcement

## Goal

Take multi-user isolation from the thread list layer into the actual thread
access layer.

After Step 03, users only saw their own recent chats in the UI, but the backend
still had a gap:

- direct `GET /api/threads/{thread_id}` access was not owner-checked
- thread state and history endpoints were not owner-checked
- run execution endpoints were not owner-checked
- suggestion generation still trusted any caller with a `thread_id`

This step closes that gap for the core thread-scoped routes.

## What Changed

### 1. Added a reusable thread ownership guard

Updated backend file:

- `backend/app/gateway/auth.py`

New helpers added:

- `require_business_store(request)`
- `require_owned_thread(request, thread_id, allow_missing=False)`

Behavior:

- unauthenticated requests now fail with `401`
- requests without business storage fail with `503`
- non-owner access to an existing thread returns `404`
- stateless run routes can optionally allow a missing thread so a logged-in user
  can bootstrap a new thread on first use

This creates one place to enforce thread access rules instead of duplicating the
logic in every router.

### 2. Thread CRUD and state/history routes now require ownership

Updated backend file:

- `backend/app/gateway/routers/threads.py`

The following routes are now protected by owner checks:

- `DELETE /api/threads/{thread_id}`
- `PATCH /api/threads/{thread_id}`
- `GET /api/threads/{thread_id}`
- `GET /api/threads/{thread_id}/state`
- `POST /api/threads/{thread_id}/state`
- `POST /api/threads/{thread_id}/history`

In addition:

- `POST /api/threads` now requires an authenticated user
- `POST /api/threads/search` now requires an authenticated user
- both routes now require the business store to be available

Also fixed an idempotency leak:

- if a caller explicitly provides an existing `thread_id` on create, the router
  now checks business ownership before returning the stored thread record

That prevents a user from probing another user's thread by reusing its ID.

### 3. Thread-scoped run routes now require ownership

Updated backend file:

- `backend/app/gateway/routers/thread_runs.py`

The following routes now require the current user to own the target thread:

- `POST /api/threads/{thread_id}/runs`
- `POST /api/threads/{thread_id}/runs/stream`
- `POST /api/threads/{thread_id}/runs/wait`
- `GET /api/threads/{thread_id}/runs`
- `GET /api/threads/{thread_id}/runs/{run_id}`
- `POST /api/threads/{thread_id}/runs/{run_id}/cancel`
- `GET /api/threads/{thread_id}/runs/{run_id}/join`
- `GET|POST /api/threads/{thread_id}/runs/{run_id}/stream`

This moves run execution from “thread list is filtered” to “thread execution is
actually isolated”.

### 4. Stateless run routes now validate reused thread ownership

Updated backend file:

- `backend/app/gateway/routers/runs.py`

For stateless run entrypoints:

- when `config.configurable.thread_id` is present, the caller must own that
  thread
- when no `thread_id` is present, a logged-in user may still create a new one

This preserves the useful “start a new run without pre-creating a thread”
behavior while preventing reuse of someone else's thread state.

### 5. Suggestions now require thread ownership

Updated backend file:

- `backend/app/gateway/routers/suggestions.py`

The suggestions route:

- `POST /api/threads/{thread_id}/suggestions`

now checks owner access before generating follow-up questions.

To keep unit tests simple, the original suggestion-generation logic was moved
into an internal helper:

- `_generate_suggestions_response(...)`

The route wrapper is now responsible for the ownership check.

## Why This Step Matters

Step 03 solved “which threads appear in the sidebar”.

Step 04 solves the more important problem:

- who can read a thread
- who can inspect its state
- who can fetch its history
- who can execute new runs on it

Without this step, multi-user isolation would still be mostly cosmetic because
anyone who knew or guessed a `thread_id` could still interact with the thread.

After this step, the core thread-scoped execution path is backed by real owner
checks.

## Intentional Non-Goals For Step 04

This step does **not** yet:

- protect uploads and artifacts by ownership
- persist file metadata into the business store
- migrate memory/profile off the global runtime files
- migrate custom agents to owned/shared business records
- enforce MCP role filtering

Those are the next steps.

## Tests Added Or Updated

Updated files:

- `backend/tests/test_gateway_auth.py`
- `backend/tests/test_threads_router.py`
- `backend/tests/test_suggestions_router.py`

New file:

- `backend/tests/test_thread_access_control.py`

Coverage added in this step:

- `require_owned_thread()` rejects unauthenticated and non-owner access
- thread search now requires authentication
- thread detail access rejects non-owners
- thread-scoped run creation rejects non-owners
- stateless run reuse rejects non-owners
- stateless runs still allow creation of a new thread for a logged-in user
- suggestions route rejects non-owners

## Validation Notes

This machine still has local test-environment limitations:

- full `pytest` runs are affected by temp directory permission issues
- some gateway route imports pull optional packages that are not installed in
  the current Python environment

Validation performed for this step:

1. syntax compilation for all changed Python files
2. direct manual execution of the new auth/thread ownership tests that do not
   depend on optional runtime packages
3. focused route-level manual verification for `thread_runs`, `runs`, and
   `suggestions` using lightweight stub modules to isolate the new access
   control logic

## Files Added Or Updated

- `backend/app/gateway/auth.py`
- `backend/app/gateway/routers/threads.py`
- `backend/app/gateway/routers/thread_runs.py`
- `backend/app/gateway/routers/runs.py`
- `backend/app/gateway/routers/suggestions.py`
- `backend/tests/test_gateway_auth.py`
- `backend/tests/test_threads_router.py`
- `backend/tests/test_thread_access_control.py`
- `backend/tests/test_suggestions_router.py`
