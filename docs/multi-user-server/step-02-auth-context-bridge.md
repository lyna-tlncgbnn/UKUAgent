# Step 02 - Auth Context Bridge

## Goal

Bridge the existing frontend `better-auth` login state into the Python gateway
so later ownership rules can rely on a stable `current_user` request context.

This step intentionally focuses on **identity plumbing**, not yet on full
authorization enforcement for every API route.

## What Changed

### 1. Gateway now understands trusted forwarded auth headers

New file:

- `backend/app/gateway/auth.py`

This module adds:

- a normalized `AuthenticatedUser` model
- trusted auth header names
- parsing logic for forwarded user headers
- proxy-secret validation
- optional sync into the business metadata store
- request helpers:
  - `get_optional_current_user(...)`
  - `require_current_user(...)`

### 2. Gateway now attaches `current_user` on every request

Updated file:

- `backend/app/gateway/app.py`

A middleware now:

1. reads the trusted forwarded auth headers
2. validates the shared proxy secret
3. resolves the authenticated user
4. stores the result on `request.state.current_user`
5. persists the user into the business store when enabled

At this step the user context is available for later route-level ownership
checks, but routes are not yet globally switched to hard auth enforcement.

### 3. Added gateway auth proxy secret config

Updated file:

- `backend/app/gateway/config.py`

New config field:

- `auth_proxy_secret`

Environment variable:

- `DEER_FLOW_AUTH_PROXY_SECRET`

Current default:

- `deerflow-dev-auth-proxy-secret`

This is acceptable for local development only. It should be overridden in any
shared or production deployment.

### 4. Frontend now uses a unified backend proxy route

New file:

- `frontend/src/app/api/backend/[...path]/route.ts`

This route:

- receives browser requests for gateway APIs
- reads the current Better Auth session on the server
- forwards trusted user headers to the Python gateway
- forwards the request body and response transparently

### 5. Frontend backend base URL now defaults to `/api/backend`

Updated file:

- `frontend/src/core/config/index.ts`

This means the frontend no longer defaults to direct browser-to-gateway calls
for custom gateway endpoints. Instead it goes through the Next.js server first,
which is where Better Auth session resolution happens.

## Why This Step Matters

Before this step:

- Better Auth only existed inside Next.js
- Python gateway knew nothing about the logged-in user
- later ownership checks would have no stable identity source

After this step:

- Next.js can translate session state into trusted user headers
- gateway can resolve `current_user`
- business storage can already start learning known users

This creates the identity boundary needed for:

- thread ownership
- user-scoped memory
- private/shared agents
- MCP role filtering

## Intentional Non-Goals For Step 02

This step does **not** yet:

- require auth on every gateway route
- attach ownership checks to thread APIs
- protect uploads/artifacts by user
- migrate memory reads to user-scoped storage
- migrate agents CRUD to owner-aware storage

Those behaviors will be added in later steps once ownership metadata is wired.

## Files Added Or Updated

- `backend/app/gateway/config.py`
- `backend/app/gateway/auth.py`
- `backend/app/gateway/app.py`
- `backend/tests/test_gateway_auth.py`
- `frontend/src/app/api/backend/[...path]/route.ts`
- `frontend/src/core/config/index.ts`
