from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.channels.message_bus import OutboundMessage
from app.channels.service import get_channel_service
from app.persistence import (
    AssetStatus,
    BusinessStore,
    ScheduledTaskRecord,
    ScheduledTaskRunNotificationStatus,
    ScheduledTaskRunRecord,
    ScheduledTaskRunStatus,
)
from app.scheduler.service import utc_now

logger = logging.getLogger(__name__)

DEFAULT_NOTIFICATION_CONFIG = {
    "enabled": True,
    "channel": "wecom",
    "on": ["success", "error"],
    "include_assets": True,
}
SUMMARY_LIMIT = 1600
ERROR_LIMIT = 800
ASSET_LIMIT = 5


def notification_config(task: ScheduledTaskRecord) -> dict[str, Any]:
    raw = (task.task_metadata or {}).get("notification")
    if isinstance(raw, dict):
        return {**DEFAULT_NOTIFICATION_CONFIG, **raw}
    return dict(DEFAULT_NOTIFICATION_CONFIG)


def notification_event_for_status(status: ScheduledTaskRunStatus) -> str | None:
    if status == ScheduledTaskRunStatus.SUCCESS:
        return "success"
    if status == ScheduledTaskRunStatus.ERROR:
        return "error"
    return None


def is_notification_enabled(task: ScheduledTaskRecord, status: ScheduledTaskRunStatus) -> bool:
    event = notification_event_for_status(status)
    if event is None:
        return False
    config = notification_config(task)
    if config.get("enabled") is False:
        return False
    events = config.get("on") or []
    return isinstance(events, list) and event in events


def extract_response_text_from_values(values: Any) -> str:
    """Extract the last assistant text from a LangGraph state/checkpoint value."""

    messages = values.get("messages", []) if isinstance(values, dict) else values if isinstance(values, list) else []
    for msg in reversed(messages):
        msg_type = _message_field(msg, "type") or _message_field(msg, "role")
        if msg_type == "human":
            break
        if msg_type == "tool" and _message_field(msg, "name") == "ask_clarification":
            content = _content_to_text(_message_field(msg, "content"))
            if content:
                return content
        if msg_type in {"ai", "assistant"}:
            content = _content_to_text(_message_field(msg, "content"))
            if content:
                return content
    return ""


async def extract_run_summary(checkpointer: Any, thread_id: str) -> str | None:
    if checkpointer is None or not thread_id:
        return None
    try:
        ckpt_tuple = await checkpointer.aget_tuple({"configurable": {"thread_id": thread_id, "checkpoint_ns": ""}})
    except Exception:
        logger.debug("Failed to read checkpoint for scheduled task notification summary", exc_info=True)
        return None
    if ckpt_tuple is None:
        return None
    values = ckpt_tuple.checkpoint.get("channel_values", {})
    summary = extract_response_text_from_values(values).strip()
    return _truncate(summary, SUMMARY_LIMIT) if summary else None


async def notify_scheduled_task_run(
    *,
    store: BusinessStore,
    task: ScheduledTaskRecord,
    run_record: ScheduledTaskRunRecord,
    status: ScheduledTaskRunStatus,
    summary: str | None = None,
    error: str | None = None,
) -> None:
    if not is_notification_enabled(task, status):
        await _mark_notification(store, run_record.id, ScheduledTaskRunNotificationStatus.SKIPPED, "Notification disabled for this run status.")
        return

    config = notification_config(task)
    if config.get("channel") != "wecom":
        await _mark_notification(store, run_record.id, ScheduledTaskRunNotificationStatus.SKIPPED, "Only WeCom notifications are supported.")
        return

    user = await store.get_user(task.user_id)
    if user is None or not user.wecom_userid:
        await _mark_notification(store, run_record.id, ScheduledTaskRunNotificationStatus.SKIPPED, "Task owner has no bound WeCom user ID.")
        return

    channel_service = get_channel_service()
    channel = channel_service.get_channel("wecom") if channel_service is not None else None
    if channel is None:
        await _mark_notification(store, run_record.id, ScheduledTaskRunNotificationStatus.SKIPPED, "WeCom channel is not running.")
        return

    assets = []
    if config.get("include_assets") is not False:
        assets = await _list_run_assets(store, task, run_record)

    text = build_wecom_notification_text(task=task, run_record=run_record, status=status, summary=summary, error=error, assets=assets)
    try:
        await channel.send(
            OutboundMessage(
                channel_name="wecom",
                chat_id=f"user:{user.wecom_userid}",
                thread_id=run_record.thread_id or task.thread_id or task.id,
                text=text,
                is_final=True,
                metadata={
                    "source": "scheduled-task-notification",
                    "scheduled_task_id": task.id,
                    "scheduled_task_run_id": run_record.id,
                },
            )
        )
    except Exception as exc:
        logger.exception("Failed to send scheduled task WeCom notification task=%s run=%s", task.id, run_record.id)
        await _mark_notification(store, run_record.id, ScheduledTaskRunNotificationStatus.ERROR, str(exc))
        return

    await _mark_notification(store, run_record.id, ScheduledTaskRunNotificationStatus.SENT, None, notified_at=utc_now())


def build_wecom_notification_text(
    *,
    task: ScheduledTaskRecord,
    run_record: ScheduledTaskRunRecord,
    status: ScheduledTaskRunStatus,
    summary: str | None,
    error: str | None,
    assets: list[Any] | None = None,
) -> str:
    status_text = "成功" if status == ScheduledTaskRunStatus.SUCCESS else "失败"
    finished_at = _format_dt(run_record.finished_at, getattr(task, "timezone", None))
    lines = [
        f"## 定时任务执行{status_text}",
        f"**任务**：{task.title}",
        f"**状态**：{status.value}",
    ]
    if finished_at:
        lines.append(f"**完成时间**：{finished_at}")
    if summary:
        lines.extend(["", "**结果摘要**", _truncate(summary.strip(), SUMMARY_LIMIT)])
    if error:
        lines.extend(["", "**错误信息**", _truncate(error.strip(), ERROR_LIMIT)])
    asset_lines = _format_asset_lines(assets or [])
    if asset_lines:
        lines.extend(["", "**生成文件**", *asset_lines])
    return "\n".join(lines)


async def _list_run_assets(store: BusinessStore, task: ScheduledTaskRecord, run_record: ScheduledTaskRunRecord) -> list[Any]:
    if run_record.run_id:
        assets = await store.list_assets(owner_user_id=task.user_id, task_id=task.id, run_id=run_record.run_id, status=AssetStatus.ACTIVE, limit=ASSET_LIMIT)
        if assets:
            return assets
    return await store.list_assets(owner_user_id=task.user_id, task_id=task.id, status=AssetStatus.ACTIVE, limit=ASSET_LIMIT)


async def _mark_notification(
    store: BusinessStore,
    run_record_id: str,
    status: ScheduledTaskRunNotificationStatus,
    error: str | None,
    *,
    notified_at: datetime | None = None,
) -> None:
    await store.update_scheduled_task_run(
        run_record_id,
        notification_status=status,
        notification_error=error,
        notified_at=notified_at,
    )


def _message_field(message: Any, key: str) -> Any:
    if isinstance(message, dict):
        return message.get(key)
    return getattr(message, key, None)


def _content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item["text"])
        return "\n".join(parts)
    return ""


def _format_asset_lines(assets: list[Any]) -> list[str]:
    lines = []
    for asset in assets[:ASSET_LIMIT]:
        name = getattr(asset, "display_name", None) or getattr(asset, "filename", None)
        if name:
            lines.append(f"- {name}")
    return lines


def _format_dt(value: datetime | None, timezone: str | None = None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    try:
        tz = ZoneInfo(timezone or "Asia/Shanghai")
    except ZoneInfoNotFoundError:
        tz = ZoneInfo("Asia/Shanghai")
    return value.astimezone(tz).strftime("%Y-%m-%d %H:%M:%S %Z")


def _truncate(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[: limit - 3].rstrip() + "..."
