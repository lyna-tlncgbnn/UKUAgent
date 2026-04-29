from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.persistence import (
    ScheduledTaskConcurrencyPolicy,
    ScheduledTaskRecord,
    ScheduledTaskRunRecord,
    ScheduledTaskRunStatus,
    ScheduledTaskScheduleType,
    ScheduledTaskStatus,
    ScheduledTaskThreadPolicy,
    ScheduledTaskTriggerType,
)


class ScheduledTaskCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    assistant_id: str = Field(default="lead_agent", min_length=1, max_length=255)
    prompt: str = Field(min_length=1)
    schedule_type: ScheduledTaskScheduleType
    timezone: str = "Asia/Shanghai"
    cron_expr: str | None = None
    interval_seconds: int | None = Field(default=None, ge=60)
    run_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ScheduledTaskUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    assistant_id: str | None = Field(default=None, min_length=1, max_length=255)
    prompt: str | None = Field(default=None, min_length=1)
    schedule_type: ScheduledTaskScheduleType | None = None
    timezone: str | None = None
    cron_expr: str | None = None
    interval_seconds: int | None = Field(default=None, ge=60)
    run_at: datetime | None = None
    metadata: dict[str, Any] | None = None


class ScheduledTaskResponse(BaseModel):
    id: str
    user_id: str
    title: str
    description: str | None
    assistant_id: str
    prompt: str
    schedule_type: str
    timezone: str
    cron_expr: str | None
    interval_seconds: int | None
    run_at: datetime | None
    next_run_at: datetime | None
    status: str
    concurrency_policy: str
    thread_policy: str
    thread_id: str | None
    last_run_at: datetime | None
    last_success_at: datetime | None
    last_error: str | None
    failure_count: int
    metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_record(cls, record: ScheduledTaskRecord) -> ScheduledTaskResponse:
        return cls(
            id=record.id,
            user_id=record.user_id,
            title=record.title,
            description=record.description,
            assistant_id=record.assistant_id,
            prompt=record.prompt,
            schedule_type=record.schedule_type.value,
            timezone=record.timezone,
            cron_expr=record.cron_expr,
            interval_seconds=record.interval_seconds,
            run_at=_as_utc(record.run_at),
            next_run_at=_as_utc(record.next_run_at),
            status=record.status.value,
            concurrency_policy=record.concurrency_policy.value,
            thread_policy=record.thread_policy.value,
            thread_id=record.thread_id,
            last_run_at=_as_utc(record.last_run_at),
            last_success_at=_as_utc(record.last_success_at),
            last_error=record.last_error,
            failure_count=record.failure_count,
            metadata=record.task_metadata,
            created_at=_as_utc(record.created_at),
            updated_at=_as_utc(record.updated_at),
        )


class ScheduledTaskRunResponse(BaseModel):
    id: str
    task_id: str
    user_id: str
    thread_id: str | None
    run_id: str | None
    scheduled_for: datetime | None
    started_at: datetime | None
    finished_at: datetime | None
    status: str
    trigger_type: str
    error: str | None
    result_summary: str | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_record(cls, record: ScheduledTaskRunRecord) -> ScheduledTaskRunResponse:
        return cls(
            id=record.id,
            task_id=record.task_id,
            user_id=record.user_id,
            thread_id=record.thread_id,
            run_id=record.run_id,
            scheduled_for=_as_utc(record.scheduled_for),
            started_at=_as_utc(record.started_at),
            finished_at=_as_utc(record.finished_at),
            status=record.status.value,
            trigger_type=record.trigger_type.value,
            error=record.error,
            result_summary=record.result_summary,
            created_at=_as_utc(record.created_at),
            updated_at=_as_utc(record.updated_at),
        )


ScheduleTypeLiteral = Literal["once", "interval", "cron"]


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC)

__all__ = [
    "ScheduledTaskConcurrencyPolicy",
    "ScheduledTaskCreateRequest",
    "ScheduledTaskRecord",
    "ScheduledTaskResponse",
    "ScheduledTaskRunResponse",
    "ScheduledTaskRunStatus",
    "ScheduledTaskScheduleType",
    "ScheduledTaskStatus",
    "ScheduledTaskThreadPolicy",
    "ScheduledTaskTriggerType",
    "ScheduledTaskUpdateRequest",
]
