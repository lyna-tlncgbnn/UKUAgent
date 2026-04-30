from __future__ import annotations

import asyncio
import logging
import socket
import uuid
from datetime import timedelta

from fastapi import FastAPI

from app.gateway.services import start_agent_run
from app.persistence import (
    ScheduledTaskRecord,
    ScheduledTaskRunStatus,
    ScheduledTaskStatus,
    ScheduledTaskTriggerType,
)
from app.scheduler.notifications import extract_run_summary, notify_scheduled_task_run
from app.scheduler.service import SchedulerService, utc_now

logger = logging.getLogger(__name__)


class SchedulerRunner:
    """Gateway-local background runner for due scheduled tasks."""

    def __init__(self, app: FastAPI, *, poll_interval_seconds: float = 5.0) -> None:
        self.app = app
        self.poll_interval_seconds = poll_interval_seconds
        self.runner_id = f"{socket.gethostname()}:{uuid.uuid4()}"
        self._task: asyncio.Task | None = None
        self._stopping = asyncio.Event()

    @property
    def service(self) -> SchedulerService | None:
        business_store = getattr(self.app.state, "business_store", None)
        if business_store is None:
            return None
        return SchedulerService(business_store)

    async def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        if self.service is None:
            logger.info("Scheduler runner not started: business store unavailable")
            return
        self._stopping.clear()
        self._task = asyncio.create_task(self._loop())
        logger.info("Scheduler runner started (runner_id=%s)", self.runner_id)

    async def stop(self) -> None:
        self._stopping.set()
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("Scheduler runner stopped")

    async def run_now(self, task: ScheduledTaskRecord, *, trigger_type: ScheduledTaskTriggerType = ScheduledTaskTriggerType.MANUAL):
        service = self.service
        if service is None:
            raise RuntimeError("Scheduler service is not available.")
        return await self._execute_task(service, task, trigger_type=trigger_type, scheduled_for=utc_now())

    async def _loop(self) -> None:
        while not self._stopping.is_set():
            try:
                await self._tick()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Scheduler tick failed")
            try:
                await asyncio.wait_for(self._stopping.wait(), timeout=self.poll_interval_seconds)
            except TimeoutError:
                continue

    async def _tick(self) -> None:
        service = self.service
        if service is None:
            return

        now = utc_now()
        due_tasks = await service.store.list_due_scheduled_tasks(now, limit=25)
        for task in due_tasks:
            locked = await service.store.update_scheduled_task(
                task.id,
                locked_at=now,
                locked_until=now + timedelta(minutes=5),
                locked_by=self.runner_id,
            )
            if locked is None or locked.status != ScheduledTaskStatus.ACTIVE:
                continue
            asyncio.create_task(self._execute_task(service, locked, trigger_type=ScheduledTaskTriggerType.SCHEDULE, scheduled_for=task.next_run_at))

    async def _execute_task(
        self,
        service: SchedulerService,
        task: ScheduledTaskRecord,
        *,
        trigger_type: ScheduledTaskTriggerType,
        scheduled_for,
    ):
        if await service.store.has_running_scheduled_task_run(task.id):
            run_record = await service.create_run_record(
                task,
                status=ScheduledTaskRunStatus.SKIPPED,
                trigger_type=trigger_type,
                scheduled_for=scheduled_for,
                error="Previous scheduled task run is still active.",
            )
            await service.store.update_scheduled_task(
                task.id,
                locked_at=None,
                locked_until=None,
                locked_by=None,
                last_error=run_record.error,
            )
            return run_record

        thread_id = task.thread_id or str(uuid.uuid4())
        run_record = await service.create_run_record(
            task,
            status=ScheduledTaskRunStatus.RUNNING,
            trigger_type=trigger_type,
            scheduled_for=scheduled_for,
            thread_id=thread_id,
        )

        try:
            record = await start_agent_run(
                bridge=self.app.state.stream_bridge,
                run_mgr=self.app.state.run_manager,
                checkpointer=self.app.state.checkpointer,
                store=getattr(self.app.state, "store", None),
                business_store=self.app.state.business_store,
                user_id=task.user_id,
                thread_id=thread_id,
                assistant_id=task.assistant_id,
                graph_input_raw={"messages": [{"role": "human", "content": task.prompt}]},
                request_config=None,
                metadata={
                    "title": task.title,
                    "source": "scheduled-task",
                    "scheduled_task_id": task.id,
                    "scheduled_task_run_id": run_record.id,
                },
                stream_mode=["values"],
                stream_subgraphs=False,
                on_disconnect="continue",
                multitask_strategy="reject",
                source="scheduled_task",
            )
            updated_run = await service.store.update_scheduled_task_run(run_record.id, run_id=record.run_id)
            if updated_run is not None:
                run_record = updated_run
            if record.task is not None:
                try:
                    await record.task
                except asyncio.CancelledError:
                    pass
            if record.error:
                raise RuntimeError(record.error)
            summary = await extract_run_summary(self.app.state.checkpointer, thread_id)
            updated_run = await service.record_success(task, run_record, result_summary=summary)
            if updated_run is not None:
                run_record = updated_run
            await self._notify_run(service, task, run_record, ScheduledTaskRunStatus.SUCCESS, summary=summary)
        except Exception as exc:
            logger.exception("Scheduled task %s failed", task.id)
            updated_run = await service.record_error(task, run_record, str(exc))
            if updated_run is not None:
                run_record = updated_run
            await self._notify_run(service, task, run_record, ScheduledTaskRunStatus.ERROR, error=str(exc))
        return run_record

    async def _notify_run(
        self,
        service: SchedulerService,
        task: ScheduledTaskRecord,
        run_record,
        status: ScheduledTaskRunStatus,
        *,
        summary: str | None = None,
        error: str | None = None,
    ) -> None:
        try:
            await notify_scheduled_task_run(
                store=service.store,
                task=task,
                run_record=run_record,
                status=status,
                summary=summary,
                error=error,
            )
        except Exception:
            logger.exception("Scheduled task notification failed task=%s run=%s", task.id, run_record.id)
