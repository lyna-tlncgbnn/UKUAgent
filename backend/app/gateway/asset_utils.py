from __future__ import annotations

import hashlib
import mimetypes
import uuid
from pathlib import Path

from app.persistence import AssetKind, AssetRecord, BusinessStore
from deerflow.config.paths import VIRTUAL_PATH_PREFIX, get_paths
from app.gateway.path_utils import resolve_thread_virtual_path


def checksum_file(path: Path) -> str | None:
    try:
        digest = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return None


def resolve_asset_storage_path(asset: AssetRecord) -> Path:
    storage_uri = asset.storage_uri
    if storage_uri.startswith("/mnt/"):
        if not asset.thread_id:
            raise ValueError("Asset has a virtual storage path but no thread_id.")
        return resolve_thread_virtual_path(asset.thread_id, storage_uri)
    return Path(storage_uri)


async def record_thread_asset(
    store: BusinessStore,
    *,
    owner_user_id: str,
    thread_id: str,
    storage_uri: str,
    kind: AssetKind,
    filename: str | None = None,
    display_name: str | None = None,
    mime_type: str | None = None,
    size_bytes: int | None = None,
    run_id: str | None = None,
    task_id: str | None = None,
    agent_id: str | None = None,
    message_id: str | None = None,
    tool_call_id: str | None = None,
    source_asset_id: str | None = None,
    metadata: dict | None = None,
) -> AssetRecord:
    actual_path = resolve_thread_virtual_path(thread_id, storage_uri) if storage_uri.startswith("/mnt/") else Path(storage_uri)
    filename = filename or actual_path.name
    detected_mime, _ = mimetypes.guess_type(actual_path)
    try:
        actual_size = actual_path.stat().st_size
    except OSError:
        actual_size = None

    return await store.upsert_asset_by_storage_uri(
        str(uuid.uuid4()),
        owner_user_id=owner_user_id,
        filename=filename,
        display_name=display_name or filename,
        kind=kind,
        storage_uri=storage_uri,
        thread_id=thread_id,
        mime_type=mime_type or detected_mime,
        size_bytes=size_bytes if size_bytes is not None else actual_size,
        checksum=checksum_file(actual_path),
        run_id=run_id,
        task_id=task_id,
        agent_id=agent_id,
        message_id=message_id,
        tool_call_id=tool_call_id,
        source_asset_id=source_asset_id,
        metadata=metadata,
    )


async def record_thread_output_assets(
    store: BusinessStore,
    *,
    owner_user_id: str,
    thread_id: str,
    run_id: str | None = None,
    task_id: str | None = None,
    agent_id: str | None = None,
    metadata: dict | None = None,
) -> list[AssetRecord]:
    outputs_dir = get_paths().sandbox_outputs_dir(thread_id)
    if not outputs_dir.exists():
        return []

    records: list[AssetRecord] = []
    for actual_path in sorted(path for path in outputs_dir.rglob("*") if path.is_file()):
        relative_path = actual_path.relative_to(outputs_dir).as_posix()
        if relative_path == "export" or relative_path.startswith("export/"):
            continue
        storage_uri = f"{VIRTUAL_PATH_PREFIX}/outputs/{relative_path}"
        records.append(
            await record_thread_asset(
                store,
                owner_user_id=owner_user_id,
                thread_id=thread_id,
                storage_uri=storage_uri,
                kind=AssetKind.GENERATED,
                run_id=run_id,
                task_id=task_id,
                agent_id=agent_id,
                metadata=metadata or {"source": "outputs_scan"},
            )
        )
    return records


def export_virtual_path(filename: str) -> str:
    return f"{VIRTUAL_PATH_PREFIX}/outputs/export/{filename}"
