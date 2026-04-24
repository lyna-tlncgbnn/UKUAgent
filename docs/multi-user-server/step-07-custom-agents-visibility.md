# Step 07 - Custom Agents Visibility

Last updated: 2026-04-24

## Goal

Migrate custom agents from the old global filesystem CRUD model to a
multi-user model with:

- `private`
- `org_shared`

while keeping the existing DeerFlow runtime path working.

## What Changed

### 1. Business-store-backed agent ownership

The `agents` and `agent_content` business tables are now used as the main
ownership and visibility source for custom agents.

Implemented behavior:

- every agent has an `owner_user_id`
- every agent has a `visibility`
- agents are loaded for the current user as:
  - owned agents
  - organization-shared agents

### 2. Filesystem mirror kept for runtime compatibility

The current runtime still reads agent config and SOUL from the existing
filesystem layout under:

- `backend/.deer-flow/agents/<slug>/config.yaml`
- `backend/.deer-flow/agents/<slug>/SOUL.md`

To avoid rewriting the runtime in one step, the API now writes both:

- business storage as the ownership truth
- filesystem mirror as runtime compatibility

### 3. Agent config loading now prefers business storage

`deerflow.config.agents_config` now reads the business store first for:

- `load_agent_config(...)`
- `load_agent_soul(...)`
- `list_custom_agents()`

This keeps runtime prompt injection and assistant discovery aligned with the
multi-user model.

### 4. Gateway agents API now enforces owner/shared rules

`/api/agents*` no longer lists or mutates global filesystem agents directly.

New rules:

- list: returns current user's owned agents + org-shared agents
- get: owner can access private/shared; others can access shared only
- create: defaults to `private`, can choose `org_shared`
- update: owner only
- delete: owner only

### 5. Agent run path now validates access

Starting a run with a custom agent slug now checks:

- agent exists
- current user owns it, or
- the agent is `org_shared`

This prevents direct use of another user's private agent by manually
supplying an assistant id.

### 6. Frontend agent gallery now reflects ownership and visibility

The workspace agents page is now grouped into:

- My agents
- Shared agents

Each card now shows:

- visibility badge
- model badge when present
- delete action only for owners

### 7. New-agent flow can set visibility

The conversational new-agent page now lets the user choose:

- Private
- Org shared

That visibility is forwarded through runtime context and used by
`setup_agent` when persisting the agent.

### 8. Agent bootstrap now preserves ownership through the runtime path

The LangGraph SDK now defaults to the Next.js backend proxy for the
Gateway-backed runtime so authenticated user context reaches bootstrap runs.
`setup_agent` also has
an extra fallback: when `user_id` is missing in runtime context, it tries to
resolve the owner from the bootstrap thread before persisting the new agent.

For agents created during the broken window, the agents API now reconciles
filesystem-only agent mirrors back into the business store when it can safely
recover ownership.

### 9. Agent chat now uses the custom assistant id instead of the default assistant

Agent chat pages now pass the agent slug as `assistantId` into the LangGraph
SDK stream hook. This matters because the Gateway only auto-injects
`configurable.agent_name` when `assistant_id != "lead_agent"`. Before this
fix, agent chats were still running as the default `lead_agent`, so the
runtime loaded the default DeerFlow system prompt instead of the custom
agent's `SOUL.md` and config.

## Files Changed

Backend:

- `backend/app/persistence/store.py`
- `backend/app/gateway/auth.py`
- `backend/app/gateway/routers/agents.py`
- `backend/app/gateway/routers/assistants_compat.py`
- `backend/app/gateway/services.py`
- `backend/packages/harness/deerflow/config/agents_config.py`
- `backend/packages/harness/deerflow/tools/builtins/setup_agent_tool.py`

Frontend:

- `frontend/src/core/agents/types.ts`
- `frontend/src/core/agents/api.ts`
- `frontend/src/core/agents/hooks.ts`
- `frontend/src/core/threads/types.ts`
- `frontend/src/core/threads/hooks.ts`
- `frontend/src/components/workspace/agents/agent-gallery.tsx`
- `frontend/src/components/workspace/agents/agent-card.tsx`
- `frontend/src/app/workspace/agents/new/page.tsx`
- `frontend/src/app/workspace/agents/[agent_name]/chats/[thread_id]/page.tsx`
- `frontend/src/core/i18n/locales/types.ts`
- `frontend/src/core/i18n/locales/zh-CN.ts`
- `frontend/src/core/i18n/locales/en-US.ts`

## Verification

Focused verification completed:

- Python AST parse for changed backend files: `python-syntax-ok`
- frontend changed files readable and wired consistently: `frontend-read-ok`
- reference scan confirmed new visibility / slug fields are used in the
  expected UI paths

## Known Limits

- Runtime still keeps a filesystem mirror for custom agents.
- There is not yet a dedicated edit screen for agent visibility/settings.
- MCP filtering by role is still pending as Step 08.
