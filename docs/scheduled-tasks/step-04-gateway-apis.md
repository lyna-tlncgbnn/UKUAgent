# Step 04 - Gateway APIs

## Goal

Expose user-owned scheduled task management through authenticated Gateway
endpoints.

## What Changed

- Added `backend/app/gateway/routers/scheduled_tasks.py`.
- Mounted the router in the FastAPI app under `/api/scheduled-tasks`.
- All routes require the current authenticated user and business storage.
- Task reads, updates, pause/resume, delete, run-now, and run history are scoped
  to the current user.
- Delete uses soft deletion by setting task status to `disabled`.

## Interfaces

- `GET /api/scheduled-tasks`
- `POST /api/scheduled-tasks`
- `GET /api/scheduled-tasks/{task_id}`
- `PUT /api/scheduled-tasks/{task_id}`
- `DELETE /api/scheduled-tasks/{task_id}`
- `POST /api/scheduled-tasks/{task_id}/pause`
- `POST /api/scheduled-tasks/{task_id}/resume`
- `POST /api/scheduled-tasks/{task_id}/run-now`
- `GET /api/scheduled-tasks/{task_id}/runs`
- `GET /api/scheduled-tasks/{task_id}/runs/{task_run_id}`

## Verification

- Gateway app import succeeds with the new router mounted.
- Business-store tests verify the persistence methods used by these endpoints.

## Known Limits

- `run-now` requires the Gateway-local scheduler runner to be available.
- API tests for every route are not yet exhaustive; the core persistence and
  schedule behavior are covered first.
