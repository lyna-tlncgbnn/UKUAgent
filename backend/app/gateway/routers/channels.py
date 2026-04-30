"""Gateway router for IM channel management."""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from app.channels.manager import WECOM_THREAD_TITLE
from app.channels.store import ChannelStore
from app.gateway.auth import require_business_store, require_current_user
from app.gateway.deps import get_checkpointer, get_store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/channels", tags=["channels"])


class ChannelStatusResponse(BaseModel):
    service_running: bool
    channels: dict[str, dict]


class ChannelRestartResponse(BaseModel):
    success: bool
    message: str


class WecomThreadResponse(BaseModel):
    thread_id: str
    title: str = WECOM_THREAD_TITLE


class WecomThreadClearResponse(BaseModel):
    success: bool
    thread_id: str
    title: str = WECOM_THREAD_TITLE


def _get_channel_store() -> ChannelStore:
    from app.channels.service import get_channel_service

    service = get_channel_service()
    if service is not None:
        return service.store
    return ChannelStore()


async def _write_empty_checkpoint(checkpointer: Any, thread_id: str, *, title: str = WECOM_THREAD_TITLE) -> None:
    from langgraph.checkpoint.base import empty_checkpoint

    now = time.time()
    config = {"configurable": {"thread_id": thread_id, "checkpoint_ns": ""}}
    metadata = {
        "step": -1,
        "source": "input",
        "writes": None,
        "parents": {},
        "created_at": now,
        "updated_at": now,
        "source_channel": "wecom",
    }
    checkpoint = empty_checkpoint()
    checkpoint.setdefault("channel_values", {})["title"] = title
    await checkpointer.aput(config, checkpoint, metadata, {})


async def _upsert_wecom_store_record(store: Any, thread_id: str) -> None:
    from app.gateway.routers.threads import _store_upsert

    if store is None:
        return
    await _store_upsert(
        store,
        thread_id,
        metadata={"source": "wecom"},
        values={"title": WECOM_THREAD_TITLE},
    )


@router.get("/", response_model=ChannelStatusResponse)
async def get_channels_status() -> ChannelStatusResponse:
    """Get the status of all IM channels."""
    from app.channels.service import get_channel_service

    service = get_channel_service()
    if service is None:
        return ChannelStatusResponse(service_running=False, channels={})
    status = service.get_status()
    return ChannelStatusResponse(**status)


@router.post("/{name}/restart", response_model=ChannelRestartResponse)
async def restart_channel(name: str) -> ChannelRestartResponse:
    """Restart a specific IM channel."""
    from app.channels.service import get_channel_service

    service = get_channel_service()
    if service is None:
        raise HTTPException(status_code=503, detail="Channel service is not running")

    success = await service.restart_channel(name)
    if success:
        logger.info("Channel %s restarted successfully", name)
        return ChannelRestartResponse(success=True, message=f"Channel {name} restarted successfully")
    else:
        logger.warning("Failed to restart channel %s", name)
        return ChannelRestartResponse(success=False, message=f"Failed to restart channel {name}")


@router.get("/wecom/thread", response_model=WecomThreadResponse)
async def get_or_create_wecom_thread(request: Request) -> WecomThreadResponse:
    """Return the current user's fixed WeCom conversation thread."""

    current_user = require_current_user(request)
    business_store = require_business_store(request)
    store = get_store(request)
    checkpointer = get_checkpointer(request)
    user_record = await business_store.get_user(current_user.id)
    if user_record is None or not user_record.wecom_userid:
        raise HTTPException(status_code=400, detail="WeCom user ID is not bound to this account.")

    existing = await business_store.get_thread_for_user_by_source(current_user.id, "wecom")
    channel_store = _get_channel_store()
    if existing is not None:
        checkpoint_tuple = await checkpointer.aget_tuple({"configurable": {"thread_id": existing.id, "checkpoint_ns": ""}})
        if checkpoint_tuple is None:
            await _write_empty_checkpoint(checkpointer, existing.id)
        await _upsert_wecom_store_record(store, existing.id)
        channel_store.set_thread_id("wecom", f"user:{user_record.wecom_userid}", existing.id, user_id=user_record.wecom_userid)
        return WecomThreadResponse(thread_id=existing.id)

    thread_id = str(uuid.uuid4())
    await _write_empty_checkpoint(checkpointer, thread_id)
    await _upsert_wecom_store_record(store, thread_id)
    await business_store.create_thread(
        thread_id,
        user_id=current_user.id,
        title=WECOM_THREAD_TITLE,
        source="wecom",
        source_user_id=user_record.wecom_userid,
    )
    channel_store.set_thread_id("wecom", f"user:{user_record.wecom_userid}", thread_id, user_id=user_record.wecom_userid)
    return WecomThreadResponse(thread_id=thread_id)


@router.post("/wecom/thread/clear", response_model=WecomThreadClearResponse)
async def clear_wecom_thread(request: Request) -> WecomThreadClearResponse:
    """Clear the current user's fixed WeCom thread while preserving its identity."""

    current_user = require_current_user(request)
    business_store = require_business_store(request)
    store = get_store(request)
    checkpointer = get_checkpointer(request)
    existing = await business_store.get_thread_for_user_by_source(current_user.id, "wecom")
    if existing is None:
        raise HTTPException(status_code=404, detail="WeCom thread not found.")

    if hasattr(checkpointer, "adelete_thread"):
        await checkpointer.adelete_thread(existing.id)

    from app.gateway.routers.threads import _delete_thread_data

    _delete_thread_data(existing.id)
    await business_store.delete_thread_files(existing.id, user_id=current_user.id)
    await _write_empty_checkpoint(checkpointer, existing.id)
    await _upsert_wecom_store_record(store, existing.id)
    return WecomThreadClearResponse(success=True, thread_id=existing.id)


@router.get("/wecom/callback")
async def verify_wecom_callback(
    msg_signature: str,
    timestamp: str,
    nonce: str,
    echostr: str,
) -> PlainTextResponse:
    """Verify the WeCom callback URL."""
    from app.channels.service import get_channel_service

    service = get_channel_service()
    if service is None:
        raise HTTPException(status_code=503, detail="Channel service is not running")

    channel = service.get_channel("wecom")
    if channel is None:
        raise HTTPException(status_code=404, detail="WeCom channel is not enabled")

    try:
        plain = await channel.verify_callback_url(
            signature=msg_signature,
            timestamp=timestamp,
            nonce=nonce,
            echostr=echostr,
        )
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return PlainTextResponse(plain)


@router.post("/wecom/callback")
async def receive_wecom_callback(
    request: Request,
    msg_signature: str,
    timestamp: str,
    nonce: str,
) -> PlainTextResponse:
    """Receive WeCom callback messages and enqueue them for ChannelManager."""
    from app.channels.service import get_channel_service

    service = get_channel_service()
    if service is None:
        raise HTTPException(status_code=503, detail="Channel service is not running")

    channel = service.get_channel("wecom")
    if channel is None:
        raise HTTPException(status_code=404, detail="WeCom channel is not enabled")

    body = await request.body()
    try:
        await channel.handle_callback(
            signature=msg_signature,
            timestamp=timestamp,
            nonce=nonce,
            body=body,
        )
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return PlainTextResponse("success")
