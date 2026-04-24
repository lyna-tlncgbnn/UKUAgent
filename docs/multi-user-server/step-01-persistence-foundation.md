# Step 01 - Persistence Foundation

## Goal

Lay down the first server-side foundation for the multi-user version without
changing existing thread, agent, or UI behavior yet.

This step only introduces a dedicated **business metadata storage layer** that
will later hold:

- users
- thread ownership metadata
- file ownership metadata
- user memory/profile data
- custom agent ownership and visibility metadata
- MCP access rules

## What Changed

### 1. Added business storage configuration

New config model:

- `backend/packages/harness/deerflow/config/business_storage_config.py`

New root config section in `AppConfig`:

- `business_storage`

Example values were added to:

- `config.example.yaml`
- `config.yaml` (commented example)

Supported connection strings:

- `sqlite+aiosqlite:///./.deer-flow/business.db`
- `postgresql+psycopg://user:password@host:5432/dbname`

### 2. Added a business persistence package

New package:

- `backend/app/persistence`

It contains:

- SQLAlchemy models
- async store wrapper
- startup factory

The business tables introduced in this step are:

- `users`
- `threads`
- `thread_files`
- `user_memory`
- `agents`
- `agent_content`
- `mcp_access_rules`

### 3. Wired the business store into gateway startup

Updated file:

- `backend/app/gateway/deps.py`

Gateway runtime now initializes an optional `business_store` and exposes it on
`app.state`, similar to the existing `checkpointer` and `store`.

At this step it is only **available**, not yet deeply integrated into request
authorization or ownership checks.

### 4. Added backend tests

New test file:

- `backend/tests/test_business_storage.py`

Covered scenarios:

- create/update user metadata
- create thread ownership metadata
- write/read user memory metadata
- record thread file metadata
- list accessible agents for owner vs non-owner

## Intentional Non-Goals For Step 01

This step does **not** yet:

- enforce login in gateway
- bind current web session to `user_id`
- restrict thread APIs by owner
- replace global memory runtime reads
- migrate custom agent CRUD to the new tables
- filter MCPs by role

Those changes will build on top of this foundation in later steps.

## Why This Step Exists

The existing project already has:

- LangGraph `checkpointer`
- LangGraph `store`
- file-based `.deer-flow` runtime data

But none of those structures are a complete place to store multi-user business
ownership metadata.

This step keeps LangGraph runtime state where it already belongs, while adding a
separate persistence layer for **application-level ownership and access data**.

## Suggested Config For Local Verification

```yaml
checkpointer:
  enabled: true
  type: sqlite
  connection_string: checkpoints.db

business_storage:
  enabled: true
  connection_string: sqlite+aiosqlite:///./.deer-flow/business.db
  auto_create_tables: true
  echo: false
```

## Suggested Config For Server Deployment

```yaml
business_storage:
  enabled: true
  connection_string: postgresql+psycopg://user:password@localhost:5432/deerflow
  auto_create_tables: true
  echo: false
```

## Files Added Or Updated

- `backend/pyproject.toml`
- `backend/packages/harness/deerflow/config/business_storage_config.py`
- `backend/packages/harness/deerflow/config/app_config.py`
- `backend/app/persistence/__init__.py`
- `backend/app/persistence/models.py`
- `backend/app/persistence/store.py`
- `backend/app/gateway/deps.py`
- `backend/tests/test_business_storage.py`
- `config.example.yaml`
- `config.yaml`

## Post Fix Note (2026-04-24)

Two runtime issues were later traced back to the checkpointer being left
disabled in the active `config.yaml`:

- gateway-created threads existed only in gateway memory
- LangGraph server used a separate in-memory saver/store

That split caused transient `404 Thread ... not found` errors because the UI
creates thread metadata through gateway, then immediately asks LangGraph for
history/state on the same thread id. Without a shared persistent checkpointer,
the two processes do not see the same thread universe.

It also caused old conversations to disappear after restart, because both the
gateway store and the LangGraph saver were process-local memory backends.

The active local config was corrected to:

```yaml
checkpointer:
  type: sqlite
  connection_string: checkpoints.db
```

With that in place, gateway and LangGraph share the same sqlite-backed thread
state and store backend, which is the minimum required baseline for stable
multi-user testing.
