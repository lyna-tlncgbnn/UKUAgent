# Step 03 - Run Pipeline Reuse

## Goal

Make scheduled executions use the same run pipeline as normal Gateway HTTP
runs.

## What Changed

- Extracted request-independent `start_agent_run` from the existing Gateway run
  service.
- HTTP run endpoints still call `start_run`, which now delegates to
  `start_agent_run`.
- Scheduler-triggered tasks call `start_agent_run` directly with the task owner,
  assistant, prompt, metadata, and generated thread ID.
- Scheduled executions upsert ownership records in the business store, but do
  not add their threads to the normal recent-chat listing store.
- The LangGraph runtime context now carries `user_id` so tools can identify the
  authenticated owner during scheduled or web runs.
- Scheduled-task detail views read execution conversations from the Gateway
  thread state endpoint instead of the LangGraph Server thread API.

## Interfaces

- `app.gateway.services.start_agent_run`
- Existing `/api/threads/{thread_id}/runs*` behavior remains unchanged.

## Verification

- Gateway app import was verified after refactoring.
- Existing business storage tests continue to pass.

## Known Limits

- Scheduled executions currently wait for the background run task to finish
  inside the scheduler task.
- Run status remains in the existing in-memory `RunManager`; durable execution
  history is stored separately in `scheduled_task_runs`.
