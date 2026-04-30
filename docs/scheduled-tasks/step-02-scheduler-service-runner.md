# Step 02 - Scheduler Service And Runner

## Goal

Add the service layer that validates schedules and the Gateway-local background
runner that triggers due tasks.

## What Changed

- Added `backend/app/scheduler` with service, schemas, and runner modules.
- `SchedulerService` now validates `once`, `interval`, and `cron` schedules.
- `compute_next_run_at` calculates the next UTC fire time using each task's
  timezone.
- `SchedulerRunner` starts during Gateway lifespan when business storage is
  available.
- The runner polls every five seconds, locks due tasks lightly, and launches
  task execution in background asyncio tasks.
- The runner extracts the final assistant summary from the checkpoint and
  triggers owner-only WeCom result notification after success or error.
- First-version concurrency behavior is `skip` when a task already has a queued
  or running execution.

## Interfaces

- `SchedulerService.create_task`
- `SchedulerService.update_task`
- `SchedulerService.pause_task`
- `SchedulerService.resume_task`
- `SchedulerService.disable_task`
- `SchedulerRunner.start`
- `SchedulerRunner.stop`
- `SchedulerRunner.run_now`

## Verification

- Schedule calculation is covered by backend tests for one-time, interval, and
  cron schedules.
- Gateway app import was verified after adding the runner startup hook.

## Known Limits

- Runner locking is intentionally light and suitable for one Gateway instance.
- Future multi-instance deployment should harden claiming with database-specific
  row locking.
- Notification failures are recorded on the run and do not change the scheduled
  task run status.
