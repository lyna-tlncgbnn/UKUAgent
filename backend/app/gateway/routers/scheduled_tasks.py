from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response

from app.gateway.auth import require_business_store, require_current_user
from app.gateway.deps import get_checkpointer, get_store
from app.gateway.routers.threads import THREADS_NS, _delete_thread_data
from app.persistence import ScheduledTaskTriggerType
from app.persistence import AssetVisibility
from app.scheduler import SchedulerService
from app.scheduler.schemas import (
    ScheduledTaskCreateRequest,
    ScheduledTaskResponse,
    ScheduledTaskRunResponse,
    ScheduledTaskUpdateRequest,
)
from app.scheduler.service import SchedulerValidationError

router = APIRouter(prefix="/api/scheduled-tasks", tags=["scheduled-tasks"])


async def _get_owned_task(request: Request, task_id: str):
    store = require_business_store(request)
    current_user = require_current_user(request)
    task = await store.get_scheduled_task_for_user(task_id, current_user.id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Scheduled task {task_id} not found")
    return task


def _service(request: Request) -> SchedulerService:
    return SchedulerService(require_business_store(request))


def _validation_error(exc: SchedulerValidationError) -> HTTPException:
    return HTTPException(status_code=422, detail=str(exc))


async def _delete_scheduled_task_threads(request: Request, *, user_id: str, thread_ids: set[str]) -> None:
    if not thread_ids:
        return

    business_store = require_business_store(request)
    store = get_store(request)
    checkpointer = get_checkpointer(request)

    for thread_id in thread_ids:
        preserve_files = False
        try:
            shared_assets = await business_store.list_assets(thread_id=thread_id, visibility=AssetVisibility.ORG_SHARED, limit=1)
            preserve_files = bool(shared_assets)
        except Exception:
            pass

        try:
            await business_store.delete_thread(thread_id, user_id=user_id)
        except Exception:
            pass

        if store is not None:
            try:
                await store.adelete(THREADS_NS, thread_id)
            except Exception:
                pass

        if checkpointer is not None and hasattr(checkpointer, "adelete_thread"):
            try:
                await checkpointer.adelete_thread(thread_id)
            except Exception:
                pass

        if not preserve_files:
            try:
                _delete_thread_data(thread_id)
            except Exception:
                pass


@router.get("", response_model=list[ScheduledTaskResponse])
async def list_scheduled_tasks(request: Request) -> list[ScheduledTaskResponse]:
    store = require_business_store(request)
    current_user = require_current_user(request)
    records = await store.list_scheduled_tasks_for_user(current_user.id)
    return [ScheduledTaskResponse.from_record(record) for record in records]


@router.post("", response_model=ScheduledTaskResponse, status_code=201)
async def create_scheduled_task(payload: ScheduledTaskCreateRequest, request: Request) -> ScheduledTaskResponse:
    current_user = require_current_user(request)
    try:
        record = await _service(request).create_task(current_user.id, payload)
    except SchedulerValidationError as exc:
        raise _validation_error(exc) from exc
    return ScheduledTaskResponse.from_record(record)


@router.get("/{task_id}", response_model=ScheduledTaskResponse)
async def get_scheduled_task(task_id: str, request: Request) -> ScheduledTaskResponse:
    task = await _get_owned_task(request, task_id)
    return ScheduledTaskResponse.from_record(task)


@router.put("/{task_id}", response_model=ScheduledTaskResponse)
async def update_scheduled_task(task_id: str, payload: ScheduledTaskUpdateRequest, request: Request) -> ScheduledTaskResponse:
    task = await _get_owned_task(request, task_id)
    try:
        updated = await _service(request).update_task(task, payload)
    except SchedulerValidationError as exc:
        raise _validation_error(exc) from exc
    return ScheduledTaskResponse.from_record(updated)


@router.delete("/{task_id}", status_code=204)
async def delete_scheduled_task(task_id: str, request: Request) -> Response:
    store = require_business_store(request)
    current_user = require_current_user(request)
    task = await store.get_scheduled_task_for_user(task_id, current_user.id)
    if task is None:
        return Response(status_code=204)
    await store.soft_delete_private_assets_for_task(task.id, user_id=task.user_id)
    await store.detach_shared_assets_for_task(task.id, user_id=task.user_id)
    runs = await store.list_scheduled_task_runs(task_id=task.id, user_id=task.user_id)
    thread_ids = {run.thread_id for run in runs if run.thread_id}
    if task.thread_id:
        thread_ids.add(task.thread_id)
    try:
        await _service(request).delete_task(task)
    except SchedulerValidationError as exc:
        raise _validation_error(exc) from exc
    await _delete_scheduled_task_threads(request, user_id=task.user_id, thread_ids=thread_ids)
    return Response(status_code=204)


@router.post("/{task_id}/pause", response_model=ScheduledTaskResponse)
async def pause_scheduled_task(task_id: str, request: Request) -> ScheduledTaskResponse:
    task = await _get_owned_task(request, task_id)
    try:
        updated = await _service(request).pause_task(task)
    except SchedulerValidationError as exc:
        raise _validation_error(exc) from exc
    return ScheduledTaskResponse.from_record(updated)


@router.post("/{task_id}/resume", response_model=ScheduledTaskResponse)
async def resume_scheduled_task(task_id: str, request: Request) -> ScheduledTaskResponse:
    task = await _get_owned_task(request, task_id)
    try:
        updated = await _service(request).resume_task(task)
    except SchedulerValidationError as exc:
        raise _validation_error(exc) from exc
    return ScheduledTaskResponse.from_record(updated)


@router.post("/{task_id}/run-now", response_model=ScheduledTaskRunResponse)
async def run_scheduled_task_now(task_id: str, request: Request) -> ScheduledTaskRunResponse:
    task = await _get_owned_task(request, task_id)
    runner = getattr(request.app.state, "scheduler_runner", None)
    if runner is None:
        raise HTTPException(status_code=503, detail="Scheduled task runner not available")
    record = await runner.run_now(task, trigger_type=ScheduledTaskTriggerType.MANUAL)
    return ScheduledTaskRunResponse.from_record(record)


@router.get("/{task_id}/runs", response_model=list[ScheduledTaskRunResponse])
async def list_scheduled_task_runs(task_id: str, request: Request) -> list[ScheduledTaskRunResponse]:
    task = await _get_owned_task(request, task_id)
    records = await require_business_store(request).list_scheduled_task_runs(task_id=task.id, user_id=task.user_id)
    return [ScheduledTaskRunResponse.from_record(record) for record in records]


@router.get("/{task_id}/runs/{task_run_id}", response_model=ScheduledTaskRunResponse)
async def get_scheduled_task_run(task_id: str, task_run_id: str, request: Request) -> ScheduledTaskRunResponse:
    task = await _get_owned_task(request, task_id)
    record = await require_business_store(request).get_scheduled_task_run_for_user(task_run_id, task_id=task.id, user_id=task.user_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Scheduled task run {task_run_id} not found")
    return ScheduledTaskRunResponse.from_record(record)
