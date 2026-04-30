from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from croniter import croniter

from app.persistence import (
    BusinessStore,
    ScheduledTaskConcurrencyPolicy,
    ScheduledTaskRecord,
    ScheduledTaskRunRecord,
    ScheduledTaskRunStatus,
    ScheduledTaskScheduleType,
    ScheduledTaskStatus,
    ScheduledTaskThreadPolicy,
    ScheduledTaskTriggerType,
)
from app.scheduler.schemas import ScheduledTaskCreateRequest, ScheduledTaskUpdateRequest

DEFAULT_TIMEZONE = "Asia/Shanghai"
DEFAULT_NOTIFICATION_CONFIG = {
    "enabled": True,
    "channel": "wecom",
    "on": ["success", "error"],
    "include_assets": True,
}


class SchedulerValidationError(ValueError):
    """Raised when a scheduled task definition is invalid."""


def utc_now() -> datetime:
    return datetime.now(UTC)


def _coerce_tz(timezone: str | None) -> ZoneInfo:
    try:
        return ZoneInfo(timezone or DEFAULT_TIMEZONE)
    except ZoneInfoNotFoundError as exc:
        raise SchedulerValidationError(f"Unknown timezone: {timezone}") from exc


def _ensure_aware(value: datetime, timezone: str) -> datetime:
    tz = _coerce_tz(timezone)
    if value.tzinfo is None:
        value = value.replace(tzinfo=tz)
    return value.astimezone(UTC)


def with_default_notification_metadata(metadata: dict | None) -> dict:
    """Merge the default owner-only WeCom notification policy into task metadata."""

    result = dict(metadata or {})
    notification = result.get("notification")
    if isinstance(notification, dict):
        result["notification"] = {**DEFAULT_NOTIFICATION_CONFIG, **notification}
    else:
        result["notification"] = dict(DEFAULT_NOTIFICATION_CONFIG)
    return result


def compute_next_run_at(
    *,
    schedule_type: ScheduledTaskScheduleType,
    timezone: str,
    cron_expr: str | None,
    interval_seconds: int | None,
    run_at: datetime | None,
    base_time: datetime | None = None,
) -> datetime | None:
    """Compute the next UTC run time for a task definition."""

    now = base_time or utc_now()
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    now = now.astimezone(UTC)

    if schedule_type == ScheduledTaskScheduleType.ONCE:
        if run_at is None:
            raise SchedulerValidationError("run_at is required for once scheduled tasks.")
        return _ensure_aware(run_at, timezone)

    if schedule_type == ScheduledTaskScheduleType.INTERVAL:
        if interval_seconds is None or interval_seconds < 60:
            raise SchedulerValidationError("interval_seconds must be at least 60 for interval scheduled tasks.")
        return now + timedelta(seconds=interval_seconds)

    if schedule_type == ScheduledTaskScheduleType.CRON:
        if not cron_expr:
            raise SchedulerValidationError("cron_expr is required for cron scheduled tasks.")
        tz = _coerce_tz(timezone)
        local_base = now.astimezone(tz)
        try:
            next_local = croniter(cron_expr, local_base).get_next(datetime)
        except Exception as exc:
            raise SchedulerValidationError(f"Invalid cron expression: {cron_expr}") from exc
        if next_local.tzinfo is None:
            next_local = next_local.replace(tzinfo=tz)
        return next_local.astimezone(UTC)

    raise SchedulerValidationError(f"Unsupported schedule_type: {schedule_type}")


class SchedulerService:
    """Business service for scheduled task definitions and run records."""

    def __init__(self, store: BusinessStore) -> None:
        self.store = store

    async def create_task(
        self,
        user_id: str,
        payload: ScheduledTaskCreateRequest,
        *,
        trigger_type: ScheduledTaskTriggerType | None = None,
    ) -> ScheduledTaskRecord:
        next_run_at = compute_next_run_at(
            schedule_type=payload.schedule_type,
            timezone=payload.timezone,
            cron_expr=payload.cron_expr,
            interval_seconds=payload.interval_seconds,
            run_at=payload.run_at,
        )
        return await self.store.create_scheduled_task(
            str(uuid.uuid4()),
            user_id=user_id,
            title=payload.title.strip(),
            description=payload.description,
            assistant_id=payload.assistant_id,
            prompt=payload.prompt,
            schedule_type=payload.schedule_type,
            timezone=payload.timezone or DEFAULT_TIMEZONE,
            cron_expr=payload.cron_expr,
            interval_seconds=payload.interval_seconds,
            run_at=_ensure_aware(payload.run_at, payload.timezone) if payload.run_at else None,
            next_run_at=next_run_at,
            status=ScheduledTaskStatus.ACTIVE,
            concurrency_policy=ScheduledTaskConcurrencyPolicy.SKIP,
            thread_policy=ScheduledTaskThreadPolicy.NEW_THREAD_EACH_RUN,
            metadata=with_default_notification_metadata({**payload.metadata, **({"created_by": trigger_type.value} if trigger_type else {})}),
        )

    async def update_task(
        self,
        task: ScheduledTaskRecord,
        payload: ScheduledTaskUpdateRequest,
    ) -> ScheduledTaskRecord:
        schedule_type = payload.schedule_type or task.schedule_type
        timezone = payload.timezone or task.timezone
        cron_expr = payload.cron_expr if payload.cron_expr is not None else task.cron_expr
        interval_seconds = payload.interval_seconds if payload.interval_seconds is not None else task.interval_seconds
        run_at = payload.run_at if payload.run_at is not None else task.run_at
        next_run_at = compute_next_run_at(
            schedule_type=schedule_type,
            timezone=timezone,
            cron_expr=cron_expr,
            interval_seconds=interval_seconds,
            run_at=run_at,
        )
        updated = await self.store.update_scheduled_task(
            task.id,
            user_id=task.user_id,
            title=payload.title.strip() if payload.title is not None else task.title,
            description=payload.description if payload.description is not None else task.description,
            assistant_id=payload.assistant_id or task.assistant_id,
            prompt=payload.prompt if payload.prompt is not None else task.prompt,
            schedule_type=schedule_type,
            timezone=timezone,
            cron_expr=cron_expr,
            interval_seconds=interval_seconds,
            run_at=_ensure_aware(run_at, timezone) if run_at else None,
            next_run_at=next_run_at,
            status=ScheduledTaskStatus.ACTIVE if task.status == ScheduledTaskStatus.COMPLETED else task.status,
            metadata=with_default_notification_metadata(payload.metadata) if payload.metadata is not None else task.task_metadata,
        )
        if updated is None:
            raise SchedulerValidationError("Scheduled task not found.")
        return updated

    async def pause_task(self, task: ScheduledTaskRecord) -> ScheduledTaskRecord:
        updated = await self.store.update_scheduled_task(task.id, user_id=task.user_id, status=ScheduledTaskStatus.PAUSED)
        if updated is None:
            raise SchedulerValidationError("Scheduled task not found.")
        return updated

    async def resume_task(self, task: ScheduledTaskRecord) -> ScheduledTaskRecord:
        next_run_at = compute_next_run_at(
            schedule_type=task.schedule_type,
            timezone=task.timezone,
            cron_expr=task.cron_expr,
            interval_seconds=task.interval_seconds,
            run_at=task.run_at,
        )
        updated = await self.store.update_scheduled_task(
            task.id,
            user_id=task.user_id,
            status=ScheduledTaskStatus.ACTIVE,
            next_run_at=next_run_at,
            last_error=None,
        )
        if updated is None:
            raise SchedulerValidationError("Scheduled task not found.")
        return updated

    async def disable_task(self, task: ScheduledTaskRecord) -> ScheduledTaskRecord:
        updated = await self.store.update_scheduled_task(task.id, user_id=task.user_id, status=ScheduledTaskStatus.DISABLED, next_run_at=None)
        if updated is None:
            raise SchedulerValidationError("Scheduled task not found.")
        return updated

    async def delete_task(self, task: ScheduledTaskRecord) -> None:
        deleted = await self.store.delete_scheduled_task(task.id, user_id=task.user_id)
        if not deleted:
            raise SchedulerValidationError("Scheduled task not found.")

    async def create_run_record(
        self,
        task: ScheduledTaskRecord,
        *,
        status: ScheduledTaskRunStatus,
        trigger_type: ScheduledTaskTriggerType,
        scheduled_for: datetime | None,
        thread_id: str | None = None,
        run_id: str | None = None,
        error: str | None = None,
    ) -> ScheduledTaskRunRecord:
        now = utc_now()
        return await self.store.create_scheduled_task_run(
            str(uuid.uuid4()),
            task_id=task.id,
            user_id=task.user_id,
            thread_id=thread_id,
            run_id=run_id,
            scheduled_for=scheduled_for,
            started_at=now if status == ScheduledTaskRunStatus.RUNNING else None,
            finished_at=now if status in {ScheduledTaskRunStatus.SKIPPED, ScheduledTaskRunStatus.ERROR, ScheduledTaskRunStatus.SUCCESS} else None,
            status=status,
            trigger_type=trigger_type,
            error=error,
        )

    async def record_success(self, task: ScheduledTaskRecord, run_record: ScheduledTaskRunRecord, *, result_summary: str | None = None) -> ScheduledTaskRunRecord | None:
        now = utc_now()
        updated_run = await self.store.update_scheduled_task_run(
            run_record.id,
            status=ScheduledTaskRunStatus.SUCCESS,
            finished_at=now,
            error=None,
            result_summary=result_summary,
        )
        next_run_at = None
        next_status = task.status
        if task.schedule_type == ScheduledTaskScheduleType.ONCE:
            next_status = ScheduledTaskStatus.COMPLETED
        else:
            next_run_at = compute_next_run_at(
                schedule_type=task.schedule_type,
                timezone=task.timezone,
                cron_expr=task.cron_expr,
                interval_seconds=task.interval_seconds,
                run_at=task.run_at,
                base_time=now,
            )
        await self.store.update_scheduled_task(
            task.id,
            last_run_at=run_record.started_at or now,
            last_success_at=now,
            last_error=None,
            failure_count=0,
            next_run_at=next_run_at,
            status=next_status,
            locked_at=None,
            locked_until=None,
            locked_by=None,
        )
        return updated_run

    async def record_error(self, task: ScheduledTaskRecord, run_record: ScheduledTaskRunRecord, error: str) -> ScheduledTaskRunRecord | None:
        now = utc_now()
        updated_run = await self.store.update_scheduled_task_run(
            run_record.id,
            status=ScheduledTaskRunStatus.ERROR,
            finished_at=now,
            error=error,
        )
        next_run_at = None
        if task.schedule_type != ScheduledTaskScheduleType.ONCE:
            next_run_at = compute_next_run_at(
                schedule_type=task.schedule_type,
                timezone=task.timezone,
                cron_expr=task.cron_expr,
                interval_seconds=task.interval_seconds,
                run_at=task.run_at,
                base_time=now,
            )
        await self.store.update_scheduled_task(
            task.id,
            last_run_at=run_record.started_at or now,
            last_error=error,
            failure_count=task.failure_count + 1,
            next_run_at=next_run_at,
            locked_at=None,
            locked_until=None,
            locked_by=None,
        )
        return updated_run
