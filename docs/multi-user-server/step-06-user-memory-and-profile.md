# Step 06 - User Memory And Profile

## Goal

Move runtime memory and user profile handling from single global files into
per-user storage.

Before this step:

- memory APIs were still reading and writing a global `memory.json`
- user profile APIs were still reading and writing a global `USER.md`
- prompt injection still loaded global memory/profile context
- background memory updates still had no concept of `user_id`

This step changes the runtime source of truth for authenticated web users to
per-user business storage, without attempting any legacy data migration.

## What Changed

### 1. Added per-user memory/profile persistence helpers

Updated backend file:

- `backend/packages/harness/deerflow/agents/memory/storage.py`

New business-storage helpers added:

- `load_user_memory_from_business_store(user_id)`
- `save_user_memory_to_business_store(user_id, memory_data)`
- `load_user_profile_from_business_store(user_id)`
- `save_user_profile_to_business_store(user_id, profile_markdown)`

Implementation notes:

- these helpers use the configured `business_storage.connection_string`
- async URLs are converted to sync SQLAlchemy URLs for prompt injection and
  background memory update paths
- when `business_storage` is disabled, they fall back to the existing single-user
  file-based behavior so local dev mode remains usable

### 2. Memory updater APIs now support `user_id`

Updated backend file:

- `backend/packages/harness/deerflow/agents/memory/updater.py`

The following functions now accept a `user_id` override:

- `get_memory_data(...)`
- `reload_memory_data(...)`
- `import_memory_data(...)`
- `clear_memory_data(...)`
- `create_memory_fact(...)`
- `delete_memory_fact(...)`
- `update_memory_fact(...)`
- `update_memory_from_conversation(...)`
- `MemoryUpdater.update_memory(...)`

Behavior:

- if `user_id` is provided, memory reads/writes go to per-user business storage
- if `user_id` is absent, the previous file/per-agent behavior still applies

Also added:

- `get_user_profile_markdown(user_id)`
- `update_user_profile_markdown(user_id, content)`

### 3. Background memory queue now tracks which user owns the conversation

Updated backend files:

- `backend/packages/harness/deerflow/agents/memory/queue.py`
- `backend/packages/harness/deerflow/agents/middlewares/memory_middleware.py`

Changes:

- `ConversationContext` now includes `user_id`
- the queue carries `user_id` into `MemoryUpdater.update_memory(...)`
- `MemoryMiddleware` now captures `user_id` from runtime/configurable context

This matters because delayed memory summarization must update the correct user's
long-term memory rather than a shared global structure.

### 4. Run config now carries `user_id`

Updated backend file:

- `backend/app/gateway/services.py`

`build_run_config(...)` now accepts `user_id`, and `start_run(...)` injects the
current authenticated user's ID into `configurable.user_id`.

This is the bridge that lets downstream runtime components know which user's
memory/profile should be loaded during a run.

### 5. Lead-agent prompt injection now uses per-user profile + memory

Updated backend files:

- `backend/packages/harness/deerflow/agents/lead_agent/agent.py`
- `backend/packages/harness/deerflow/agents/lead_agent/prompt.py`

Changes:

- `make_lead_agent(...)` now reads `user_id` from the runtime config
- `MemoryMiddleware` is instantiated with that `user_id`
- `apply_prompt_template(...)` now accepts `user_id`
- prompt injection now supports:
  - per-user memory context
  - per-user profile markdown context

Prompt composition is now aligned with the multi-user design:

1. platform/system prompt
2. agent SOUL
3. current user's profile markdown
4. current user's memory context

This removes the old global profile/memory leakage from authenticated web runs.

### 6. Memory API is now current-user scoped

Updated backend file:

- `backend/app/gateway/routers/memory.py`

The memory routes now require an authenticated user and operate on
`user_id=current_user.id`:

- `GET /api/memory`
- `POST /api/memory/reload`
- `DELETE /api/memory`
- `POST /api/memory/facts`
- `DELETE /api/memory/facts/{fact_id}`
- `PATCH /api/memory/facts/{fact_id}`
- `GET /api/memory/export`
- `POST /api/memory/import`
- `GET /api/memory/status`

The memory config endpoint remains config-oriented and does not change storage.

### 7. Existing user-profile route now writes per-user profile data

Updated backend file:

- `backend/app/gateway/routers/agents.py`

The existing routes:

- `GET /api/user-profile`
- `PUT /api/user-profile`

now:

- require authentication
- read/write the current user's `user_profile_md`
- stop using the global `USER.md` as the primary source of truth for authenticated flows

Because `storage.py` provides a compatibility fallback, local single-user mode
without `business_storage` still continues to function.

### 8. Added more lazy imports to reduce test-time dependency drag

Updated backend files:

- `backend/packages/harness/deerflow/agents/__init__.py`
- `backend/packages/harness/deerflow/agents/lead_agent/__init__.py`
- `backend/packages/harness/deerflow/subagents/__init__.py`

These were changed to lazy export modules so memory- and prompt-level tests can
import the relevant code paths without eagerly pulling in heavy optional runtime
dependencies.

## Why This Step Matters

This is the step where “multi-user” stops being mostly about thread ownership
and starts affecting personalization and memory.

After this step:

- user A's memory facts are stored separately from user B's
- user A's profile markdown is stored separately from user B's
- prompt injection uses the current user's memory/profile
- background memory summarization writes back to the correct user

That removes one of the highest-risk cross-user leakage points in the system.

## Intentional Non-Goals For Step 06

This step does **not** yet:

- migrate historical global `memory.json` or `USER.md`
- move custom agents to business-owned records
- add MCP role filtering
- backfill old file metadata

Those belong to later steps.

## Tests Added Or Updated

Updated files:

- `backend/tests/test_memory_router.py`
- `backend/tests/test_memory_updater.py`
- `backend/tests/test_gateway_services.py`
- `backend/tests/test_lead_agent_prompt.py`
- `backend/tests/test_custom_agent.py`

New file:

- `backend/tests/test_user_profile_router.py`

Coverage added in this step:

- memory router now passes `user_id` into per-user memory operations
- user-profile router now reads/writes the authenticated user's profile
- updater helpers route to business-backed user memory/profile when `user_id` is present
- run config now includes `configurable.user_id`
- prompt template can include per-user profile context

## Validation Notes

Validation completed in this environment:

1. syntax compilation for all changed Python files
2. focused manual execution of:
   - per-user memory helper tests
   - memory router tests
   - user-profile router tests
   - run-config `user_id` propagation
   - prompt-template per-user profile injection

Results observed:

- `syntax-ok`
- `manual-step6-memory-tests-ok`
- `manual-step6-run-config-ok`
- `manual-step6-prompt-test-ok`

As in earlier steps, full `pytest` is still constrained by this machine's
optional dependency and temp-directory environment issues. The logic added in
this step was validated with focused direct execution instead.

## Files Added Or Updated

- `backend/packages/harness/deerflow/agents/memory/storage.py`
- `backend/packages/harness/deerflow/agents/memory/updater.py`
- `backend/packages/harness/deerflow/agents/memory/queue.py`
- `backend/packages/harness/deerflow/agents/middlewares/memory_middleware.py`
- `backend/packages/harness/deerflow/agents/lead_agent/agent.py`
- `backend/packages/harness/deerflow/agents/lead_agent/prompt.py`
- `backend/packages/harness/deerflow/agents/__init__.py`
- `backend/packages/harness/deerflow/agents/lead_agent/__init__.py`
- `backend/packages/harness/deerflow/subagents/__init__.py`
- `backend/app/gateway/services.py`
- `backend/app/gateway/routers/memory.py`
- `backend/app/gateway/routers/agents.py`
- `backend/tests/test_memory_router.py`
- `backend/tests/test_memory_updater.py`
- `backend/tests/test_user_profile_router.py`
- `backend/tests/test_gateway_services.py`
- `backend/tests/test_lead_agent_prompt.py`
- `backend/tests/test_custom_agent.py`
