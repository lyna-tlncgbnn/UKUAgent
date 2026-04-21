"""Gateway router for IM channel management."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/channels", tags=["channels"])


class ChannelStatusResponse(BaseModel):
    service_running: bool
    channels: dict[str, dict]


class ChannelRestartResponse(BaseModel):
    success: bool
    message: str


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
