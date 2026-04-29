# Step 01 - Persistence Foundation

## Goal

Add durable business-storage tables for scheduled task definitions and their
execution history.

## What Changed

- Added scheduled task enums and SQLAlchemy models in the business persistence
  layer.
- Added `scheduled_tasks` for task definitions, timing rules, status, last
  result fields, and future lock columns.
- Added `scheduled_task_runs` for every scheduled, manual, or conversation
  triggered execution.
- Extended `BusinessStore` with task CRUD, run record CRUD, due-task lookup,
  and running-run detection helpers.
- Added `croniter` to backend dependencies because schedule calculation depends
  on cron expressions.

## Interfaces

- `BusinessStore.create_scheduled_task`
- `BusinessStore.list_scheduled_tasks_for_user`
- `BusinessStore.update_scheduled_task`
- `BusinessStore.list_due_scheduled_tasks`
- `BusinessStore.create_scheduled_task_run`
- `BusinessStore.list_scheduled_task_runs`

## Verification

- Added backend tests for task creation, user-scoped listing, task status
  updates, run record creation, run listing, and schedule calculation.
- Verified `backend/tests/test_business_storage.py` passes.

## Known Limits

- New tables are created by `Base.metadata.create_all` when
  `business_storage.auto_create_tables` is enabled.
- No Alembic migration was added in this step.
