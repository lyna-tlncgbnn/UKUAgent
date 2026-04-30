"""Upload router for handling file uploads."""

import logging
import os
import stat
import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from pydantic import BaseModel

from app.gateway.asset_utils import record_thread_asset
from app.gateway.auth import get_optional_current_user, require_owned_thread
from app.gateway.deps import get_business_store
from app.persistence import AssetKind, ThreadFileKind
from deerflow.config.paths import get_paths
from deerflow.sandbox.sandbox_provider import get_sandbox_provider
from deerflow.uploads.manager import (
    PathTraversalError,
    delete_file_safe,
    enrich_file_listing,
    ensure_uploads_dir,
    get_uploads_dir,
    list_files_in_dir,
    normalize_filename,
    upload_artifact_url,
    upload_virtual_path,
)
from deerflow.utils.file_conversion import CONVERTIBLE_EXTENSIONS, convert_file_to_markdown

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/threads/{thread_id}/uploads", tags=["uploads"])


class UploadResponse(BaseModel):
    """Response model for file upload."""

    success: bool
    files: list[dict[str, str]]
    message: str


def _make_file_sandbox_writable(file_path: os.PathLike[str] | str) -> None:
    """Ensure uploaded files remain writable when mounted into non-local sandboxes.

    In AIO sandbox mode, the gateway writes the authoritative host-side file
    first, then the sandbox runtime may rewrite the same mounted path. Granting
    world-writable access here prevents permission mismatches between the
    gateway user and the sandbox runtime user.
    """
    file_stat = os.lstat(file_path)
    if stat.S_ISLNK(file_stat.st_mode):
        logger.warning("Skipping sandbox chmod for symlinked upload path: %s", file_path)
        return

    writable_mode = stat.S_IMODE(file_stat.st_mode) | stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH
    chmod_kwargs = {"follow_symlinks": False} if os.chmod in os.supports_follow_symlinks else {}
    os.chmod(file_path, writable_mode, **chmod_kwargs)


@router.post("", response_model=UploadResponse)
async def upload_files(
    thread_id: str,
    request: Request = None,
    files: list[UploadFile] = File(...),
) -> UploadResponse:
    """Upload multiple files to a thread's uploads directory."""
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    business_store = None
    current_user = None
    if request is not None:
        await require_owned_thread(request, thread_id)
        business_store = get_business_store(request)
        current_user = get_optional_current_user(request)

    try:
        uploads_dir = ensure_uploads_dir(thread_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    sandbox_uploads = get_paths().sandbox_uploads_dir(thread_id)
    uploaded_files = []

    sandbox_provider = get_sandbox_provider()
    sandbox_id = sandbox_provider.acquire(thread_id)
    sandbox = sandbox_provider.get(sandbox_id)

    for file in files:
        if not file.filename:
            continue

        try:
            safe_filename = normalize_filename(file.filename)
        except ValueError:
            logger.warning(f"Skipping file with unsafe filename: {file.filename!r}")
            continue

        try:
            content = await file.read()
            file_path = uploads_dir / safe_filename
            file_path.write_bytes(content)

            virtual_path = upload_virtual_path(safe_filename)

            if sandbox_id != "local":
                _make_file_sandbox_writable(file_path)
                sandbox.update_file(virtual_path, content)

            file_info = {
                "filename": safe_filename,
                "size": str(len(content)),
                "path": str(sandbox_uploads / safe_filename),
                "virtual_path": virtual_path,
                "artifact_url": upload_artifact_url(thread_id, safe_filename),
            }

            logger.info(f"Saved file: {safe_filename} ({len(content)} bytes) to {file_info['path']}")

            if business_store is not None and current_user is not None:
                await business_store.record_thread_file(
                    str(uuid.uuid4()),
                    thread_id=thread_id,
                    user_id=current_user.id,
                    kind=ThreadFileKind.UPLOAD,
                    filename=safe_filename,
                    storage_path=str(sandbox_uploads / safe_filename),
                    mime_type=file.content_type,
                    size_bytes=len(content),
                )
                uploaded_asset = await record_thread_asset(
                    business_store,
                    owner_user_id=current_user.id,
                    thread_id=thread_id,
                    storage_uri=virtual_path,
                    kind=AssetKind.UPLOAD,
                    filename=safe_filename,
                    mime_type=file.content_type,
                    size_bytes=len(content),
                    metadata={"source": "upload"},
                )
            else:
                uploaded_asset = None

            file_ext = file_path.suffix.lower()
            if file_ext in CONVERTIBLE_EXTENSIONS:
                md_path = await convert_file_to_markdown(file_path)
                if md_path:
                    md_virtual_path = upload_virtual_path(md_path.name)

                    if sandbox_id != "local":
                        _make_file_sandbox_writable(md_path)
                        sandbox.update_file(md_virtual_path, md_path.read_bytes())

                    file_info["markdown_file"] = md_path.name
                    file_info["markdown_path"] = str(sandbox_uploads / md_path.name)
                    file_info["markdown_virtual_path"] = md_virtual_path
                    file_info["markdown_artifact_url"] = upload_artifact_url(thread_id, md_path.name)

                    if business_store is not None and current_user is not None:
                        markdown_bytes = md_path.read_bytes()
                        await business_store.record_thread_file(
                            str(uuid.uuid4()),
                            thread_id=thread_id,
                            user_id=current_user.id,
                            kind=ThreadFileKind.ARTIFACT,
                            filename=md_path.name,
                            storage_path=str(sandbox_uploads / md_path.name),
                            mime_type="text/markdown",
                            size_bytes=len(markdown_bytes),
                        )
                        await record_thread_asset(
                            business_store,
                            owner_user_id=current_user.id,
                            thread_id=thread_id,
                            storage_uri=md_virtual_path,
                            kind=AssetKind.CONVERTED,
                            filename=md_path.name,
                            mime_type="text/markdown",
                            size_bytes=len(markdown_bytes),
                            source_asset_id=uploaded_asset.id if uploaded_asset is not None else None,
                            metadata={"source": "upload_conversion", "source_filename": safe_filename},
                        )

            uploaded_files.append(file_info)

        except Exception as e:
            logger.error(f"Failed to upload {file.filename}: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to upload {file.filename}: {str(e)}")

    return UploadResponse(
        success=True,
        files=uploaded_files,
        message=f"Successfully uploaded {len(uploaded_files)} file(s)",
    )


@router.get("/list", response_model=dict)
async def list_uploaded_files(thread_id: str, request: Request = None) -> dict:
    """List all files in a thread's uploads directory."""
    if request is not None:
        await require_owned_thread(request, thread_id)
    try:
        uploads_dir = get_uploads_dir(thread_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    result = list_files_in_dir(uploads_dir)
    enrich_file_listing(result, thread_id)

    # Gateway additionally includes the sandbox-relative path.
    sandbox_uploads = get_paths().sandbox_uploads_dir(thread_id)
    for f in result["files"]:
        f["path"] = str(sandbox_uploads / f["filename"])

    return result


@router.delete("/{filename}")
async def delete_uploaded_file(thread_id: str, filename: str, request: Request = None) -> dict:
    """Delete a file from a thread's uploads directory."""
    business_store = None
    if request is not None:
        await require_owned_thread(request, thread_id)
        business_store = get_business_store(request)

    try:
        uploads_dir = get_uploads_dir(thread_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    try:
        result = delete_file_safe(uploads_dir, filename, convertible_extensions=CONVERTIBLE_EXTENSIONS)
        if business_store is not None:
            sandbox_uploads = get_paths().sandbox_uploads_dir(thread_id)
            deleted_paths = [
                str(sandbox_uploads / filename),
                str(sandbox_uploads / Path(filename).with_suffix(".md").name),
            ]
            for storage_path in deleted_paths:
                await business_store.delete_thread_file_by_path(thread_id=thread_id, storage_path=storage_path)
        return result
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"File not found: {filename}")
    except PathTraversalError:
        raise HTTPException(status_code=400, detail="Invalid path")
    except Exception as e:
        logger.error(f"Failed to delete {filename}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete {filename}: {str(e)}")
