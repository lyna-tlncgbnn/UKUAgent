# Step 07 - WeCom Result Notifications

## Goal

Push scheduled task results back to the task owner in Enterprise WeChat private
chat, instead of leaving results only in the execution thread.

## What Changed

- Added owner-only notification metadata defaults for scheduled tasks:
  `notification.enabled=true`, `channel=wecom`, `on=["success", "error"]`,
  and `include_assets=true`.
- Added run-level notification observability:
  `notification_status`, `notification_error`, and `notified_at`.
- Added a scheduler notification service that:
  - extracts the latest assistant summary from the final checkpoint,
  - reads generated assets associated with the run,
  - resolves the task owner through `users.wecom_userid`,
  - sends a WeCom Markdown message to `user:{wecom_userid}`,
  - records sent, skipped, or error state on the run.
- Wired `SchedulerRunner` to notify after success or error without changing the
  underlying run status when notification delivery fails.
- Updated the conversation `create_scheduled_task` tool so tasks created from
  web chat or WeCom chat carry the same default notification policy.

## Runtime Behavior

- Web-created, conversation-created, and WeCom-created scheduled tasks all use
  the same Gateway task creation path, so they share the same notification
  defaults.
- Existing tasks with no `notification` metadata also use the default WeCom
  owner notification behavior.
- If the owner has no `wecom_userid`, or the WeCom channel is not running, the
  run is marked `notification_status=skipped`.
- If WeCom sending fails, the run is marked `notification_status=error` and
  `notification_error` stores the failure reason.
- Skipped executions caused by concurrency protection are not pushed.

## Interfaces

- `ScheduledTask.metadata.notification` controls notification behavior:

```json
{
  "enabled": true,
  "channel": "wecom",
  "on": ["success", "error"],
  "include_assets": true
}
```

- `ScheduledTaskRunResponse` now includes:

```text
notification_status
notification_error
notified_at
```

- `create_scheduled_task` includes `notify: bool = True`. It should be set to
  `false` only when the user explicitly asks not to receive run notifications.

## Verification

- Store tests cover default notification metadata and run notification fields.
- Scheduler notification tests cover summary extraction, message formatting,
  owner-only WeCom delivery, generated asset listing, and skip behavior when the
  owner has no WeCom binding.

## Known Limits

- First version supports only Enterprise WeChat private messages.
- Result files are listed by name, not uploaded as WeCom attachments.
- The notification message omits a frontend deep link until a public workspace
  base URL is configured.
