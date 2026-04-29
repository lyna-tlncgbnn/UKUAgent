# Step 06 - Frontend UI

## Goal

Add a first-class workspace UI for scheduled task management and history
inspection.

## What Changed

- Added a "Scheduled tasks" sidebar entry between Agents and Recent chats.
- Added scheduled task API, hooks, and TypeScript types under
  `frontend/src/core/scheduled-tasks`.
- Added `/workspace/scheduled-tasks` list page with task cards.
- Added `/workspace/scheduled-tasks/[task_id]` detail page with task metadata,
  latest execution state, and run history.
- Execution records with `thread_id` link into the existing chat route so the
  normal conversation UI displays task results.
- Added Chinese and English sidebar translations.
- Chat submissions now include the authenticated `user_id` in LangGraph
  `context` so conversation tools can create tasks for the current user without
  violating LangGraph's `context`/`configurable` exclusivity rule.
- Task cards and history rows format timestamps with each task's configured
  timezone instead of relying on the browser's implicit timezone parser.
- Execution history rows now select an execution inside the scheduled-task
  detail page and render its Gateway thread messages inline, rather than
  navigating to `/workspace/chats/[thread_id]`.

## Interfaces

- `/workspace/scheduled-tasks`
- `/workspace/scheduled-tasks/[task_id]`
- Chat jump target:
  `/workspace/chats/[thread_id]?source=scheduled-task&task_id=...&task_run_id=...`

## Verification

- Frontend typecheck was run inside the frontend container.
- The scheduled-task UI type-only import issue was fixed.
- Conversation-created scheduled tasks were fixed by propagating the current
  auth user into LangGraph runtime data.
- Backend scheduled-task responses normalize SQLite datetimes as UTC before
  serialization, preventing the frontend from treating UTC values as local
  wall-clock times.
- Recent chats no longer include `scheduled_task` source threads.

## Known Limits

- The first UI version supports creation, pause/resume, immediate run, soft
  delete, and history navigation; inline editing can be expanded later.
