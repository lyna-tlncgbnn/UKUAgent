# Step 05 - Conversation Tools

## Goal

Allow users to manage scheduled tasks from normal conversations while keeping
the harness/app dependency boundary intact.

## What Changed

- Added built-in scheduled task tools in the harness layer.
- Tools read `user_id` from LangGraph `ToolRuntime.context`, falling back to
  `ToolRuntime.config.configurable.user_id`.
- `run_agent` now forwards `configurable.user_id` into runtime context.
- Tools call the Gateway scheduled task API with trusted internal auth headers
  instead of importing the app layer.
- Docker deployments set `DEER_FLOW_SCHEDULER_GATEWAY_URL` for the LangGraph
  service, and tools fall back to `http://gateway:8001` when the default local
  address is unreachable.
- `create_scheduled_task` supports `delay_seconds` for relative one-time
  reminders, so prompts like "in two minutes" are resolved by the tool runtime
  instead of by model-generated absolute timestamps.
- Tool responses include local display helpers such as `run_at_local` and
  `next_run_at_local` for the task timezone.
- The lead-agent prompt now includes `current_datetime` with `Asia/Shanghai`
  timezone so absolute time reasoning has hour/minute context.
- Added tools for create, list, pause, resume, delete, and run-now.

## Interfaces

- `create_scheduled_task`
- `list_scheduled_tasks`
- `pause_scheduled_task`
- `resume_scheduled_task`
- `delete_scheduled_task`
- `run_scheduled_task_now`

## Verification

- Harness boundary test confirms the new tool file does not introduce an app
  import.
- Existing boundary test still reports a pre-existing unrelated violation in
  `agents/memory/storage.py`.

## Known Limits

- The "confirm before create" behavior is expressed in the tool description and
  agent instructions, not enforced by a separate confirmation token.
- The tools use `DEER_FLOW_SCHEDULER_GATEWAY_URL` when set, otherwise they try
  local Gateway first and the Docker service name as a fallback.
