# Step 03 - Thread Ownership And Search

## Goal

Make thread ownership real for logged-in web users, and make the “recent chats”
list come from an ownership-aware backend search instead of the raw LangGraph
thread listing.

This step is the first point where multi-user data boundaries start affecting
actual product behavior.

## What Changed

### 1. New web threads are now created through the gateway first

Updated frontend files:

- `frontend/src/core/threads/api.ts`
- `frontend/src/core/threads/hooks.ts`

When the user sends the first message in a new conversation, the frontend now:

1. calls `POST /api/threads` through the authenticated backend proxy
2. receives a real `thread_id`
3. uses that `thread_id` for uploads and LangGraph streaming

This replaces the earlier implicit “let LangGraph create the thread on demand”
behavior for the web path.

That change is important because the gateway thread creation path is where we
can attach `user_id` ownership metadata.

### 2. Thread creation now writes ownership metadata to business storage

Updated backend file:

- `backend/app/gateway/routers/threads.py`

When a logged-in web user creates a thread through the gateway, the router now
also writes a business thread record:

- `thread_id`
- `user_id`
- `title` (if present)
- `source = "web"`

This means new web threads now have a stable ownership record in the business
database layer introduced in Step 01.

### 3. Run startup also refreshes thread ownership metadata

Updated backend file:

- `backend/app/gateway/services.py`

When a run starts through gateway-backed flows, the service now also upserts the
thread into business storage when `current_user` is present.

This keeps thread ownership metadata fresh even in flows that do not come
through the explicit thread creation endpoint.

### 4. Recent thread search now uses the gateway and filters by owner

Updated frontend file:

- `frontend/src/core/threads/hooks.ts`

The `useThreads()` hook no longer uses the raw LangGraph SDK `threads.search`
path for the recent chat list. It now calls:

- `POST /api/threads/search`

through the backend proxy.

Updated backend file:

- `backend/app/gateway/routers/threads.py`

When a logged-in user is present and business storage is enabled, thread search
now filters results to only those `thread_id`s owned by the current user.

### 5. Thread rename now goes through the gateway state endpoint

Updated frontend file:

- `frontend/src/core/threads/hooks.ts`

Rename previously updated LangGraph state directly through the SDK, which meant
the gateway-side searchable thread metadata could drift from the actual thread
title. It now uses:

- `POST /api/threads/{thread_id}/state`

so gateway-managed thread search state stays in sync.

## Why This Step Matters

After Step 02, the gateway knew who the current user was.

But the product still had a gap:

- thread creation for web users could happen outside the ownership-aware path
- recent chat listing still came from raw LangGraph thread search

That meant there was no reliable way to show “only my threads”.

After this step:

- new web threads are created through an ownership-aware gateway path
- thread ownership is stored in business metadata
- recent chats are sourced from an ownership-aware search route

This creates the first working end-user boundary for multi-user conversations.

## Intentional Non-Goals For Step 03

This step does **not** yet:

- block non-owners from reading arbitrary thread state/history by `thread_id`
- protect uploads or artifacts by ownership
- migrate old legacy threads into user ownership automatically
- protect agent execution by owner checks

Those are the next steps.

## Tests Added

Updated file:

- `backend/tests/test_threads_router.py`

New coverage in this step:

- thread creation writes business ownership metadata
- thread search only returns owned threads when a logged-in user is present

## Files Added Or Updated

- `backend/app/gateway/services.py`
- `backend/app/gateway/routers/threads.py`
- `backend/tests/test_threads_router.py`
- `frontend/src/core/threads/api.ts`
- `frontend/src/core/threads/hooks.ts`
