from __future__ import annotations

import mimetypes
import uuid
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel, Field

from app.gateway.asset_utils import checksum_file, export_virtual_path, record_thread_output_assets, resolve_asset_storage_path
from app.gateway.auth import require_business_store, require_current_user, require_owned_thread
from app.gateway.routers.artifacts import (
    ACTIVE_CONTENT_MIME_TYPES,
    _build_attachment_headers,
    _build_content_disposition,
    is_text_file_by_content,
)
from app.persistence import AssetKind, AssetRecord, AssetStatus, AssetVisibility, UserRole
from deerflow.config.paths import get_paths

router = APIRouter(prefix="/api/assets", tags=["assets"])


class AssetResponse(BaseModel):
    id: str
    owner_user_id: str
    filename: str
    display_name: str
    kind: str
    mime_type: str | None = None
    size_bytes: int | None = None
    storage_uri: str
    checksum: str | None = None
    visibility: str
    status: str
    thread_id: str | None = None
    run_id: str | None = None
    task_id: str | None = None
    agent_id: str | None = None
    message_id: str | None = None
    tool_call_id: str | None = None
    source_asset_id: str | None = None
    version_group_id: str | None = None
    version_number: int
    metadata: dict = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None

    @classmethod
    def from_record(cls, record: AssetRecord) -> "AssetResponse":
        return cls(
            id=record.id,
            owner_user_id=record.owner_user_id,
            filename=record.filename,
            display_name=record.display_name,
            kind=record.kind.value,
            mime_type=record.mime_type,
            size_bytes=record.size_bytes,
            storage_uri=record.storage_uri,
            checksum=record.checksum,
            visibility=record.visibility.value,
            status=record.status.value,
            thread_id=record.thread_id,
            run_id=record.run_id,
            task_id=record.task_id,
            agent_id=record.agent_id,
            message_id=record.message_id,
            tool_call_id=record.tool_call_id,
            source_asset_id=record.source_asset_id,
            version_group_id=record.version_group_id,
            version_number=record.version_number,
            metadata=record.asset_metadata or {},
            created_at=record.created_at,
            updated_at=record.updated_at,
            deleted_at=record.deleted_at,
        )


class AssetListResponse(BaseModel):
    assets: list[AssetResponse]
    next_cursor: str | None = None


class AssetUpdateRequest(BaseModel):
    display_name: str | None = None
    metadata: dict | None = None
    status: Literal["active", "archived"] | None = None


class AssetExportRequest(BaseModel):
    thread_id: str | None = None
    task_id: str | None = None
    asset_ids: list[str] = Field(default_factory=list)


def _parse_kind(value: str | None) -> AssetKind | None:
    if value is None:
        return None
    try:
        return AssetKind(value)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"Invalid asset kind: {value}") from exc


async def _reconcile_output_assets_for_thread(request: Request, thread_id: str) -> None:
    store = require_business_store(request)
    user = require_current_user(request)
    await record_thread_output_assets(
        store,
        owner_user_id=user.id,
        thread_id=thread_id,
        metadata={"source": "outputs_scan"},
    )


async def _reconcile_output_assets_for_user(request: Request) -> None:
    store = require_business_store(request)
    user = require_current_user(request)
    threads = await store.list_threads_for_user(user.id)
    for thread in threads:
        await record_thread_output_assets(
            store,
            owner_user_id=user.id,
            thread_id=thread.id,
            metadata={"source": "outputs_scan"},
        )


def _is_admin(user) -> bool:
    return getattr(user, "role", None) == UserRole.ADMIN.value


def _can_view(asset: AssetRecord, user) -> bool:
    return asset.owner_user_id == user.id or asset.visibility == AssetVisibility.ORG_SHARED or _is_admin(user)


def _can_manage(asset: AssetRecord, user) -> bool:
    return asset.owner_user_id == user.id or _is_admin(user)


async def _get_visible_asset(request: Request, asset_id: str, *, include_deleted: bool = False) -> AssetRecord:
    store = require_business_store(request)
    user = require_current_user(request)
    asset = await store.get_asset(asset_id)
    if asset is None or not _can_view(asset, user):
        raise HTTPException(status_code=404, detail=f"Asset {asset_id} not found")
    if asset.status == AssetStatus.DELETED:
        if not include_deleted or not _can_manage(asset, user):
            raise HTTPException(status_code=404, detail=f"Asset {asset_id} not found")
    return asset


async def _get_manageable_asset(request: Request, asset_id: str, *, include_deleted: bool = False) -> AssetRecord:
    asset = await _get_visible_asset(request, asset_id, include_deleted=include_deleted)
    user = require_current_user(request)
    if not _can_manage(asset, user):
        raise HTTPException(status_code=403, detail="Only the asset owner or an admin can manage this asset.")
    return asset


def _serve_asset_file(asset: AssetRecord, *, download: bool) -> Response:
    actual_path = resolve_asset_storage_path(asset)
    if not actual_path.exists() or not actual_path.is_file():
        raise HTTPException(status_code=404, detail=f"Asset file not found: {asset.id}")
    mime_type = asset.mime_type or mimetypes.guess_type(actual_path)[0]
    filename = asset.display_name or actual_path.name

    if download or mime_type in ACTIVE_CONTENT_MIME_TYPES:
        return FileResponse(path=actual_path, filename=filename, media_type=mime_type, headers=_build_attachment_headers(filename))
    if mime_type and mime_type.startswith("text/"):
        return PlainTextResponse(content=actual_path.read_text(encoding="utf-8"), media_type=mime_type)
    if is_text_file_by_content(actual_path):
        return PlainTextResponse(content=actual_path.read_text(encoding="utf-8"), media_type=mime_type or "text/plain")
    return Response(content=actual_path.read_bytes(), media_type=mime_type, headers={"Content-Disposition": _build_content_disposition("inline", filename)})


@router.get("", response_model=AssetListResponse)
async def list_assets(
    request: Request,
    space: Literal["mine", "org_shared", "thread", "task", "trash"] = Query(default="mine"),
    thread_id: str | None = None,
    task_id: str | None = None,
    kind: str | None = None,
    q: str | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    cursor: str | None = None,
) -> AssetListResponse:
    store = require_business_store(request)
    user = require_current_user(request)
    offset = int(cursor or "0")
    asset_kind = _parse_kind(kind)

    if space == "thread":
        if not thread_id:
            raise HTTPException(status_code=422, detail="thread_id is required for thread space")
        await require_owned_thread(request, thread_id)
        await _reconcile_output_assets_for_thread(request, thread_id)
        records = await store.list_assets(thread_id=thread_id, kind=asset_kind, q=q, limit=limit + 1, offset=offset)
    elif space == "task":
        if not task_id:
            raise HTTPException(status_code=422, detail="task_id is required for task space")
        task = await store.get_scheduled_task_for_user(task_id, user.id)
        if task is None:
            raise HTTPException(status_code=404, detail=f"Scheduled task {task_id} not found")
        records = await store.list_assets(task_id=task_id, kind=asset_kind, q=q, limit=limit + 1, offset=offset)
    elif space == "org_shared":
        records = await store.list_assets(visibility=AssetVisibility.ORG_SHARED, kind=asset_kind, q=q, limit=limit + 1, offset=offset)
    elif space == "trash":
        records = await store.list_assets(owner_user_id=user.id, status=AssetStatus.DELETED, kind=asset_kind, q=q, limit=limit + 1, offset=offset)
    else:
        await _reconcile_output_assets_for_user(request)
        records = await store.list_assets(owner_user_id=user.id, kind=asset_kind, q=q, limit=limit + 1, offset=offset)

    page = records[:limit]
    next_cursor = str(offset + limit) if len(records) > limit else None
    return AssetListResponse(assets=[AssetResponse.from_record(record) for record in page], next_cursor=next_cursor)


@router.get("/{asset_id}", response_model=AssetResponse)
async def get_asset(asset_id: str, request: Request) -> AssetResponse:
    return AssetResponse.from_record(await _get_visible_asset(request, asset_id))


@router.get("/{asset_id}/content")
async def get_asset_content(asset_id: str, request: Request, download: bool = False) -> Response:
    asset = await _get_visible_asset(request, asset_id, include_deleted=True)
    return _serve_asset_file(asset, download=download)


@router.patch("/{asset_id}", response_model=AssetResponse)
async def update_asset(asset_id: str, payload: AssetUpdateRequest, request: Request) -> AssetResponse:
    asset = await _get_manageable_asset(request, asset_id, include_deleted=True)
    status = AssetStatus(payload.status) if payload.status else None
    updated = await require_business_store(request).update_asset(
        asset.id,
        display_name=payload.display_name,
        status=status,
        metadata=payload.metadata,
    )
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Asset {asset_id} not found")
    return AssetResponse.from_record(updated)


@router.post("/{asset_id}/publish", response_model=AssetResponse)
async def publish_asset(asset_id: str, request: Request) -> AssetResponse:
    asset = await _get_manageable_asset(request, asset_id)
    updated = await require_business_store(request).update_asset(asset.id, visibility=AssetVisibility.ORG_SHARED)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Asset {asset_id} not found")
    return AssetResponse.from_record(updated)


@router.post("/{asset_id}/unpublish", response_model=AssetResponse)
async def unpublish_asset(asset_id: str, request: Request) -> AssetResponse:
    asset = await _get_manageable_asset(request, asset_id)
    updated = await require_business_store(request).update_asset(asset.id, visibility=AssetVisibility.PRIVATE)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Asset {asset_id} not found")
    return AssetResponse.from_record(updated)


@router.delete("/{asset_id}", response_model=AssetResponse)
async def delete_asset(asset_id: str, request: Request) -> AssetResponse:
    asset = await _get_manageable_asset(request, asset_id)
    updated = await require_business_store(request).soft_delete_asset(asset.id)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Asset {asset_id} not found")
    return AssetResponse.from_record(updated)


@router.post("/export", response_model=AssetResponse)
async def export_assets(payload: AssetExportRequest, request: Request) -> AssetResponse:
    store = require_business_store(request)
    user = require_current_user(request)
    records: list[AssetRecord] = []
    for asset_id in payload.asset_ids:
        asset = await _get_visible_asset(request, asset_id)
        records.append(asset)

    thread_id = payload.thread_id or (records[0].thread_id if records else None)
    if payload.task_id:
        task = await store.get_scheduled_task_for_user(payload.task_id, user.id)
        if task is None:
            raise HTTPException(status_code=404, detail=f"Scheduled task {payload.task_id} not found")
        thread_id = thread_id or task.thread_id
        task_assets = await store.list_assets(task_id=payload.task_id, owner_user_id=user.id, limit=1000)
        existing_ids = {asset.id for asset in records}
        records.extend(asset for asset in task_assets if asset.id not in existing_ids)
    if thread_id:
        await require_owned_thread(request, thread_id)
    else:
        raise HTTPException(status_code=422, detail="Export requires thread_id, task_id with a thread, or at least one thread-bound asset.")
    if not records:
        records = await store.list_assets(thread_id=thread_id, owner_user_id=user.id, limit=1000)
    if not records:
        raise HTTPException(status_code=422, detail="No assets available to export.")

    export_dir = get_paths().sandbox_outputs_dir(thread_id) / "export"
    export_dir.mkdir(parents=True, exist_ok=True)
    filename = f"assets-{uuid.uuid4().hex[:8]}.zip"
    export_path = export_dir / filename
    with zipfile.ZipFile(export_path, "w", zipfile.ZIP_DEFLATED) as zf:
        used_names: set[str] = set()
        for asset in records:
            source = resolve_asset_storage_path(asset)
            if not source.is_file():
                continue
            arcname = asset.filename
            if arcname in used_names:
                arcname = f"{asset.id}-{arcname}"
            used_names.add(arcname)
            zf.write(source, arcname=arcname)

    virtual_path = export_virtual_path(filename)
    record = await store.create_asset(
        str(uuid.uuid4()),
        owner_user_id=user.id,
        filename=filename,
        display_name=filename,
        kind=AssetKind.EXPORT,
        storage_uri=virtual_path,
        thread_id=thread_id,
        task_id=payload.task_id,
        mime_type="application/zip",
        size_bytes=export_path.stat().st_size,
        checksum=checksum_file(export_path),
        metadata={"asset_ids": [asset.id for asset in records]},
    )
    return AssetResponse.from_record(record)
