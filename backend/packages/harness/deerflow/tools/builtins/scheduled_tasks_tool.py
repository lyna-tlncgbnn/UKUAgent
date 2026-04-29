from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Any, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx
from langchain_core.tools import tool
from langgraph.prebuilt import ToolRuntime

DEFAULT_GATEWAY_URL = "http://localhost:8001"
DOCKER_GATEWAY_URL = "http://gateway:8001"
DEFAULT_AUTH_PROXY_SECRET = "deerflow-dev-auth-proxy-secret"
DEFAULT_TIMEZONE = "Asia/Shanghai"


def _gateway_url() -> str:
    return (
        os.getenv("DEER_FLOW_SCHEDULER_GATEWAY_URL")
        or os.getenv("DEER_FLOW_INTERNAL_GATEWAY_BASE_URL")
        or os.getenv("DEER_FLOW_CHANNELS_GATEWAY_URL")
        or DEFAULT_GATEWAY_URL
    ).rstrip("/")


def _headers(runtime: ToolRuntime) -> dict[str, str]:
    user_id = runtime.context.get("user_id") if runtime.context else None
    if not user_id and runtime.config:
        user_id = runtime.config.get("configurable", {}).get("user_id")
    if not user_id:
        raise ValueError("Cannot manage scheduled tasks without an authenticated user_id.")
    return {
        "content-type": "application/json",
        "x-deerflow-auth-proxy-secret": os.getenv("DEER_FLOW_AUTH_PROXY_SECRET", DEFAULT_AUTH_PROXY_SECRET),
        "x-deerflow-auth-user-id": str(user_id),
        "x-deerflow-auth-user-name": str(user_id),
        "x-deerflow-auth-user-role": "member",
    }


def _request(method: str, path: str, runtime: ToolRuntime, json: dict[str, Any] | None = None) -> Any:
    headers = _headers(runtime)
    urls = [_gateway_url()]
    if urls[0] != DOCKER_GATEWAY_URL:
        urls.append(DOCKER_GATEWAY_URL)

    last_error: Exception | None = None
    response: httpx.Response | None = None
    with httpx.Client(timeout=20) as client:
        for base_url in urls:
            try:
                response = client.request(method, f"{base_url}{path}", headers=headers, json=json)
                break
            except httpx.RequestError as exc:
                last_error = exc
                continue
    if response is None:
        raise ValueError(f"Could not reach scheduled task API: {last_error}")
    if response.status_code >= 400:
        detail = response.json().get("detail") if response.headers.get("content-type", "").startswith("application/json") else response.text
        raise ValueError(detail or f"Scheduled task API failed with status {response.status_code}")
    if response.status_code == 204:
        return None
    return _decorate_task_times(response.json())


def _zoneinfo(timezone: str | None) -> ZoneInfo:
    try:
        return ZoneInfo(timezone or DEFAULT_TIMEZONE)
    except ZoneInfoNotFoundError:
        return ZoneInfo(DEFAULT_TIMEZONE)


def _run_at_from_delay(delay_seconds: int, timezone: str | None) -> str:
    if delay_seconds < 1:
        raise ValueError("delay_seconds must be at least 1 for relative one-time scheduled tasks.")
    return (datetime.now(_zoneinfo(timezone)) + timedelta(seconds=delay_seconds)).isoformat()


def _parse_datetime(value: str) -> datetime | None:
    try:
        normalized = value.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=ZoneInfo("UTC"))
    return parsed


def _format_local_datetime(value: str | None, timezone: str | None) -> str | None:
    if not value:
        return None
    parsed = _parse_datetime(value)
    if parsed is None:
        return None
    return parsed.astimezone(_zoneinfo(timezone)).strftime("%Y-%m-%d %H:%M")


def _decorate_one_task(task: dict[str, Any]) -> dict[str, Any]:
    timezone = task.get("timezone") if isinstance(task.get("timezone"), str) else DEFAULT_TIMEZONE
    task["run_at_local"] = _format_local_datetime(task.get("run_at"), timezone)
    task["next_run_at_local"] = _format_local_datetime(task.get("next_run_at"), timezone)
    return task


def _decorate_task_times(payload: Any) -> Any:
    if isinstance(payload, list):
        return [_decorate_one_task(item) if isinstance(item, dict) and "schedule_type" in item else item for item in payload]
    if isinstance(payload, dict) and "schedule_type" in payload:
        return _decorate_one_task(payload)
    return payload


@tool
def create_scheduled_task(
    title: str,
    prompt: str,
    schedule_type: Literal["once", "interval", "cron"],
    runtime: ToolRuntime,
    timezone: str = "Asia/Shanghai",
    assistant_id: str = "lead_agent",
    description: str | None = None,
    cron_expr: str | None = None,
    interval_seconds: int | None = None,
    run_at: str | None = None,
    delay_seconds: int | None = None,
) -> dict[str, Any]:
    """Create a scheduled agent task after the user has explicitly confirmed it.

    Use this only after confirming the task title, schedule, timezone, and prompt
    with the user. For relative one-time reminders such as "in 2 minutes", use
    schedule_type="once" with delay_seconds instead of calculating run_at
    yourself. For absolute one-time schedules provide run_at as an ISO datetime
    string, preferably with an explicit timezone offset. For cron schedules
    provide cron_expr. For interval schedules provide interval_seconds.
    """

    if schedule_type == "once" and delay_seconds is not None:
        run_at = _run_at_from_delay(delay_seconds, timezone)

    payload = {
        "title": title,
        "description": description,
        "assistant_id": assistant_id,
        "prompt": prompt,
        "schedule_type": schedule_type,
        "timezone": timezone,
        "cron_expr": cron_expr,
        "interval_seconds": interval_seconds,
        "run_at": run_at,
        "metadata": {"created_from": "conversation_tool"},
    }
    return _request("POST", "/api/scheduled-tasks", runtime, json=payload)


@tool
def list_scheduled_tasks(runtime: ToolRuntime) -> list[dict[str, Any]]:
    """List the current user's scheduled tasks."""

    return _request("GET", "/api/scheduled-tasks", runtime)


@tool
def pause_scheduled_task(task_id: str, runtime: ToolRuntime) -> dict[str, Any]:
    """Pause one of the current user's scheduled tasks."""

    return _request("POST", f"/api/scheduled-tasks/{task_id}/pause", runtime)


@tool
def resume_scheduled_task(task_id: str, runtime: ToolRuntime) -> dict[str, Any]:
    """Resume one of the current user's paused scheduled tasks."""

    return _request("POST", f"/api/scheduled-tasks/{task_id}/resume", runtime)


@tool
def delete_scheduled_task(task_id: str, runtime: ToolRuntime) -> dict[str, Any]:
    """Disable one of the current user's scheduled tasks while keeping its run history."""

    return _request("DELETE", f"/api/scheduled-tasks/{task_id}", runtime)


@tool
def run_scheduled_task_now(task_id: str, runtime: ToolRuntime) -> dict[str, Any]:
    """Trigger one of the current user's scheduled tasks immediately."""

    return _request("POST", f"/api/scheduled-tasks/{task_id}/run-now", runtime)
