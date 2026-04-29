# Scheduled Tasks Module

Last updated: 2026-04-29

## Purpose

This directory tracks the staged implementation of the scheduled tasks module.

The module adds two ways to create user-owned scheduled agent work:

- manual creation from the workspace UI
- conversational creation through built-in agent tools

Scheduled tasks live in the Gateway/business layer. They trigger normal
DeerFlow runs and bind each execution to a regular thread so the existing chat
UI remains the place to inspect results.

## Current Status

Completed:

- Step 01: persistence foundation
- Step 02: scheduler service and runner
- Step 03: run pipeline reuse
- Step 04: Gateway APIs
- Step 05: conversation tools
- Step 06: frontend UI

## Runtime Decisions

- `croniter` is used for cron calculation.
- Default timezone is `Asia/Shanghai`.
- Each scheduled execution creates a new thread by default.
- First version uses local Gateway polling, not a distributed scheduler.
- Task deletion is soft deletion through `disabled` status.
- Execution history is retained in `scheduled_task_runs`.

## Step Documents

- [Step 01 - Persistence Foundation](step-01-persistence-foundation.md)
- [Step 02 - Scheduler Service Runner](step-02-scheduler-service-runner.md)
- [Step 03 - Run Pipeline Reuse](step-03-run-pipeline-reuse.md)
- [Step 04 - Gateway APIs](step-04-gateway-apis.md)
- [Step 05 - Conversation Tools](step-05-conversation-tools.md)
- [Step 06 - Frontend UI](step-06-frontend-ui.md)

## Known Boundaries

- The runner is intended for a single Gateway instance in this version.
- Lock columns are present for future multi-instance hardening.
- Conversation tools call the Gateway API so the harness layer does not import
  the app layer directly.
