"""Tests for the multi-user business storage foundation."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest

import deerflow.config.app_config as app_config_module
from app.persistence import (
    AgentVisibility,
    ScheduledTaskRunStatus,
    ScheduledTaskScheduleType,
    ScheduledTaskStatus,
    ScheduledTaskTriggerType,
    ThreadFileKind,
    UserRole,
)
from app.persistence.store import create_business_store
from app.scheduler.schemas import ScheduledTaskCreateRequest, ScheduledTaskResponse
from app.scheduler.service import SchedulerService, compute_next_run_at
from deerflow.config.app_config import AppConfig, reset_app_config, set_app_config


@pytest.fixture(autouse=True)
def reset_config_state():
    reset_app_config()
    yield
    reset_app_config()
    app_config_module._app_config = None


def _make_test_config() -> AppConfig:
    return AppConfig.model_validate(
        {
            "sandbox": {"use": "deerflow.sandbox.local:LocalSandboxProvider"},
            "business_storage": {
                "enabled": True,
                "connection_string": "sqlite+aiosqlite:///:memory:",
                "auto_create_tables": True,
                "echo": False,
            },
        }
    )


def test_business_store_round_trips_user_thread_memory_and_file():
    async def run_test():
        set_app_config(_make_test_config())

        async with create_business_store() as store:
            assert store is not None

            user = await store.upsert_user("user-1", email="user1@example.com", name="User One")
            assert user.id == "user-1"
            assert user.role.value == "member"

            thread = await store.create_thread("thread-1", user_id="user-1", title="Test Thread")
            assert thread.id == "thread-1"
            assert thread.user_id == "user-1"

            memory = await store.upsert_user_memory("user-1", memory_json={"facts": ["foo"]}, user_profile_md="# User One")
            assert memory.memory_json == {"facts": ["foo"]}
            assert memory.user_profile_md == "# User One"

            file_record = await store.record_thread_file(
                "file-1",
                thread_id="thread-1",
                user_id="user-1",
                kind=ThreadFileKind.UPLOAD,
                filename="test.txt",
                storage_path="/tmp/test.txt",
                mime_type="text/plain",
                size_bytes=12,
            )
            assert file_record.thread_id == "thread-1"
            assert file_record.kind is ThreadFileKind.UPLOAD

            fetched_user = await store.get_user("user-1")
            fetched_thread = await store.get_thread("thread-1")
            fetched_memory = await store.get_user_memory("user-1")
            listed_threads = await store.list_threads_for_user("user-1")
            listed_files = await store.list_thread_files(thread_id="thread-1", kind=ThreadFileKind.UPLOAD)
            deleted_count = await store.delete_thread_file_by_path(thread_id="thread-1", storage_path="/tmp/test.txt")
            remaining_files = await store.list_thread_files(thread_id="thread-1", kind=ThreadFileKind.UPLOAD)

            assert fetched_user is not None
            assert fetched_thread is not None
            assert fetched_memory is not None
            assert [item.id for item in listed_threads] == ["thread-1"]
            assert [item.id for item in listed_files] == ["file-1"]
            assert deleted_count == 1
            assert remaining_files == []

    asyncio.run(run_test())


def test_business_store_lists_private_and_shared_agents_for_viewer():
    async def run_test():
        set_app_config(_make_test_config())

        async with create_business_store() as store:
            assert store is not None

            await store.upsert_user("owner", email="owner@example.com", name="Owner", role=UserRole.ADMIN)
            await store.upsert_user("viewer", email="viewer@example.com", name="Viewer")

            await store.create_agent(
                "agent-private",
                owner_user_id="owner",
                name="Owner Private",
                slug="owner-private",
                description="private",
                model="test-model",
                tool_groups=["web"],
                visibility=AgentVisibility.PRIVATE,
                soul_md="private soul",
                config_json={"foo": "bar"},
            )
            await store.create_agent(
                "agent-shared",
                owner_user_id="owner",
                name="Owner Shared",
                slug="owner-shared",
                description="shared",
                model="test-model",
                tool_groups=["web"],
                visibility=AgentVisibility.ORG_SHARED,
                soul_md="shared soul",
                config_json={"foo": "bar"},
            )

            owner_agents = await store.list_accessible_agents("owner")
            viewer_agents = await store.list_accessible_agents("viewer")

            assert {agent.slug for agent in owner_agents} == {"owner-private", "owner-shared"}
            assert {agent.slug for agent in viewer_agents} == {"owner-shared"}

    asyncio.run(run_test())


def test_business_store_round_trips_scheduled_tasks_and_runs():
    async def run_test():
        set_app_config(_make_test_config())

        async with create_business_store() as store:
            assert store is not None
            await store.upsert_user("user-1", email="user1@example.com", name="User One")

            service = SchedulerService(store)
            task = await service.create_task(
                "user-1",
                ScheduledTaskCreateRequest(
                    title="Daily report",
                    assistant_id="lead_agent",
                    prompt="Create a daily report",
                    schedule_type=ScheduledTaskScheduleType.CRON,
                    timezone="Asia/Shanghai",
                    cron_expr="0 9 * * *",
                ),
            )

            assert task.user_id == "user-1"
            assert task.status is ScheduledTaskStatus.ACTIVE
            assert task.next_run_at is not None

            listed = await store.list_scheduled_tasks_for_user("user-1")
            assert [item.id for item in listed] == [task.id]
            assert await store.list_scheduled_tasks_for_user("user-2") == []

            run_record = await service.create_run_record(
                task,
                status=ScheduledTaskRunStatus.RUNNING,
                trigger_type=ScheduledTaskTriggerType.MANUAL,
                scheduled_for=task.next_run_at,
                thread_id="thread-1",
                run_id="run-1",
            )
            assert run_record.task_id == task.id
            assert run_record.status is ScheduledTaskRunStatus.RUNNING

            runs = await store.list_scheduled_task_runs(task_id=task.id, user_id="user-1")
            assert [item.id for item in runs] == [run_record.id]
            assert await store.list_scheduled_task_runs(task_id=task.id, user_id="user-2") == []

            updated = await store.update_scheduled_task(task.id, user_id="user-1", status=ScheduledTaskStatus.PAUSED)
            assert updated is not None
            assert updated.status is ScheduledTaskStatus.PAUSED
            assert await store.update_scheduled_task(task.id, user_id="user-2", status=ScheduledTaskStatus.DISABLED) is None

    asyncio.run(run_test())


def test_compute_next_run_at_supports_once_interval_and_cron():
    base = datetime(2026, 4, 29, 0, 0, tzinfo=UTC)

    once = compute_next_run_at(
        schedule_type=ScheduledTaskScheduleType.ONCE,
        timezone="Asia/Shanghai",
        cron_expr=None,
        interval_seconds=None,
        run_at=datetime(2026, 4, 30, 9, 0),
        base_time=base,
    )
    assert once == datetime(2026, 4, 30, 1, 0, tzinfo=UTC)

    interval = compute_next_run_at(
        schedule_type=ScheduledTaskScheduleType.INTERVAL,
        timezone="Asia/Shanghai",
        cron_expr=None,
        interval_seconds=3600,
        run_at=None,
        base_time=base,
    )
    assert interval == datetime(2026, 4, 29, 1, 0, tzinfo=UTC)

    cron = compute_next_run_at(
        schedule_type=ScheduledTaskScheduleType.CRON,
        timezone="Asia/Shanghai",
        cron_expr="0 9 * * *",
        interval_seconds=None,
        run_at=None,
        base_time=base,
    )
    assert cron == datetime(2026, 4, 29, 1, 0, tzinfo=UTC)


def test_scheduled_task_response_marks_sqlite_datetimes_as_utc():
    async def run_test():
        set_app_config(_make_test_config())

        async with create_business_store() as store:
            assert store is not None
            await store.upsert_user("user-1", email="user1@example.com", name="User One")

            service = SchedulerService(store)
            task = await service.create_task(
                "user-1",
                ScheduledTaskCreateRequest(
                    title="Drink water",
                    assistant_id="lead_agent",
                    prompt="Remind me to drink water",
                    schedule_type=ScheduledTaskScheduleType.ONCE,
                    timezone="Asia/Shanghai",
                    run_at=datetime(2026, 4, 29, 18, 4),
                ),
            )

            response = ScheduledTaskResponse.from_record(task)
            assert response.run_at is not None
            assert response.next_run_at is not None
            assert response.run_at.tzinfo is UTC
            assert response.next_run_at.tzinfo is UTC

    asyncio.run(run_test())
