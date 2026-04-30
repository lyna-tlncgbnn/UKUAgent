from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace

import deerflow.config.app_config as app_config_module
from app.persistence import (
    AssetKind,
    ScheduledTaskRunNotificationStatus,
    ScheduledTaskRunStatus,
    ScheduledTaskScheduleType,
    ScheduledTaskTriggerType,
)
from app.persistence.store import create_business_store
from app.scheduler.notifications import build_wecom_notification_text, extract_response_text_from_values, notify_scheduled_task_run
from app.scheduler.schemas import ScheduledTaskCreateRequest
from app.scheduler.service import SchedulerService
from deerflow.config.app_config import AppConfig, reset_app_config, set_app_config


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


def setup_function():
    reset_app_config()


def teardown_function():
    reset_app_config()
    app_config_module._app_config = None


class DummyWecomChannel:
    def __init__(self) -> None:
        self.messages = []

    async def send(self, msg):
        self.messages.append(msg)


class DummyChannelService:
    def __init__(self, channel):
        self.channel = channel

    def get_channel(self, name: str):
        return self.channel if name == "wecom" else None


def test_extract_response_text_from_values_uses_latest_ai_after_human():
    values = {
        "messages": [
            {"type": "ai", "content": "old"},
            {"type": "human", "content": "run task"},
            {"type": "ai", "content": ""},
            {"type": "ai", "content": [{"type": "text", "text": "latest summary"}]},
        ]
    }

    assert extract_response_text_from_values(values) == "latest summary"


def test_build_wecom_notification_text_includes_summary_error_and_assets():
    task = SimpleNamespace(title="Daily report")
    run = SimpleNamespace(finished_at=datetime(2026, 4, 30, 1, 2, tzinfo=UTC))
    asset = SimpleNamespace(display_name="report.md", filename="report.md")

    text = build_wecom_notification_text(
        task=task,
        run_record=run,
        status=ScheduledTaskRunStatus.ERROR,
        summary="summary",
        error="boom",
        assets=[asset],
    )

    assert "定时任务执行失败" in text
    assert "Daily report" in text
    assert "summary" in text
    assert "boom" in text
    assert "report.md" in text


def test_notify_scheduled_task_run_sends_to_owner_wecom_user(monkeypatch):
    async def run_test():
        set_app_config(_make_test_config())
        channel = DummyWecomChannel()
        monkeypatch.setattr("app.scheduler.notifications.get_channel_service", lambda: DummyChannelService(channel))

        async with create_business_store() as store:
            assert store is not None
            await store.upsert_user("user-1", email="u@example.com", name="User", wecom_userid="wx-user-1")
            await store.create_thread("thread-1", user_id="user-1")

            service = SchedulerService(store)
            task = await service.create_task(
                "user-1",
                ScheduledTaskCreateRequest(
                    title="Daily report",
                    prompt="Create report",
                    schedule_type=ScheduledTaskScheduleType.ONCE,
                    timezone="Asia/Shanghai",
                    run_at=datetime(2026, 5, 1, 9, 0),
                ),
            )
            run_record = await service.create_run_record(
                task,
                status=ScheduledTaskRunStatus.RUNNING,
                trigger_type=ScheduledTaskTriggerType.MANUAL,
                scheduled_for=task.next_run_at,
                thread_id="thread-1",
                run_id="run-1",
            )
            await store.create_asset(
                "asset-1",
                owner_user_id="user-1",
                filename="report.md",
                display_name="Report",
                kind=AssetKind.GENERATED,
                storage_uri="/mnt/user-data/outputs/report.md",
                thread_id="thread-1",
                task_id=task.id,
                run_id="run-1",
            )

            await notify_scheduled_task_run(
                store=store,
                task=task,
                run_record=run_record,
                status=ScheduledTaskRunStatus.SUCCESS,
                summary="Done",
            )

            assert len(channel.messages) == 1
            assert channel.messages[0].chat_id == "user:wx-user-1"
            assert "Done" in channel.messages[0].text
            assert "Report" in channel.messages[0].text

            updated = await store.get_scheduled_task_run_for_user(run_record.id, task_id=task.id, user_id="user-1")
            assert updated is not None
            assert updated.notification_status is ScheduledTaskRunNotificationStatus.SENT
            assert updated.notified_at is not None

    asyncio.run(run_test())


def test_notify_scheduled_task_run_skips_without_wecom_user(monkeypatch):
    async def run_test():
        set_app_config(_make_test_config())
        channel = DummyWecomChannel()
        monkeypatch.setattr("app.scheduler.notifications.get_channel_service", lambda: DummyChannelService(channel))

        async with create_business_store() as store:
            assert store is not None
            await store.upsert_user("user-1", email="u@example.com", name="User")
            service = SchedulerService(store)
            task = await service.create_task(
                "user-1",
                ScheduledTaskCreateRequest(
                    title="Daily report",
                    prompt="Create report",
                    schedule_type=ScheduledTaskScheduleType.ONCE,
                    timezone="Asia/Shanghai",
                    run_at=datetime(2026, 5, 1, 9, 0),
                ),
            )
            run_record = await service.create_run_record(
                task,
                status=ScheduledTaskRunStatus.RUNNING,
                trigger_type=ScheduledTaskTriggerType.MANUAL,
                scheduled_for=task.next_run_at,
                thread_id="thread-1",
            )

            await notify_scheduled_task_run(store=store, task=task, run_record=run_record, status=ScheduledTaskRunStatus.SUCCESS, summary="Done")

            assert channel.messages == []
            updated = await store.get_scheduled_task_run_for_user(run_record.id, task_id=task.id, user_id="user-1")
            assert updated is not None
            assert updated.notification_status is ScheduledTaskRunNotificationStatus.SKIPPED
            assert "WeCom" in (updated.notification_error or "")

    asyncio.run(run_test())
