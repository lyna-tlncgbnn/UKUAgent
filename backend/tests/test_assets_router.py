from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.gateway.routers.assets as assets_router
from app.persistence import AssetKind, AssetStatus, AssetVisibility


def _local_temp_file(name: str) -> Path:
    root = Path(__file__).resolve().parents[2] / ".tmp" / "test-assets-router"
    root.mkdir(parents=True, exist_ok=True)
    return root / f"{uuid4().hex}-{name}"


def _asset(**overrides):
    now = datetime(2026, 4, 30, tzinfo=UTC)
    data = {
        "id": "asset-1",
        "owner_user_id": "owner",
        "filename": "note.txt",
        "display_name": "note.txt",
        "kind": AssetKind.UPLOAD,
        "mime_type": "text/plain",
        "size_bytes": 5,
        "storage_uri": "/mnt/user-data/uploads/note.txt",
        "checksum": None,
        "visibility": AssetVisibility.PRIVATE,
        "status": AssetStatus.ACTIVE,
        "thread_id": "thread-1",
        "run_id": None,
        "task_id": None,
        "agent_id": None,
        "message_id": None,
        "tool_call_id": None,
        "source_asset_id": None,
        "version_group_id": "asset-1",
        "version_number": 1,
        "asset_metadata": {},
        "created_at": now,
        "updated_at": now,
        "deleted_at": None,
    }
    data.update(overrides)
    return SimpleNamespace(**data)


class FakeStore:
    def __init__(self, asset):
        self.asset = asset

    async def get_asset(self, asset_id: str):
        return self.asset if asset_id == self.asset.id else None

    async def update_asset(self, asset_id: str, **kwargs):
        if asset_id != self.asset.id:
            return None
        for key, value in kwargs.items():
            if value is not None and hasattr(self.asset, key):
                setattr(self.asset, key, value)
        return self.asset


def _make_app(asset, *, user_id="owner", role="member"):
    app = FastAPI()

    @app.middleware("http")
    async def inject_user(request, call_next):
        request.state.current_user = SimpleNamespace(id=user_id, role=role)
        return await call_next(request)

    app.state.business_store = FakeStore(asset)
    app.include_router(assets_router.router)
    return app


def test_private_asset_content_rejects_non_owner(monkeypatch):
    file_path = _local_temp_file("note.txt")
    file_path.write_text("hello", encoding="utf-8")
    monkeypatch.setattr(assets_router, "resolve_asset_storage_path", lambda _asset: file_path)

    with TestClient(_make_app(_asset(), user_id="viewer")) as client:
        response = client.get("/api/assets/asset-1/content")

    assert response.status_code == 404


def test_org_shared_asset_content_allows_authenticated_user(monkeypatch):
    file_path = _local_temp_file("note.txt")
    file_path.write_text("hello", encoding="utf-8")
    monkeypatch.setattr(assets_router, "resolve_asset_storage_path", lambda _asset: file_path)

    with TestClient(_make_app(_asset(visibility=AssetVisibility.ORG_SHARED), user_id="viewer")) as client:
        response = client.get("/api/assets/asset-1/content")

    assert response.status_code == 200
    assert response.text == "hello"


def test_owner_can_publish_asset():
    asset = _asset()
    with TestClient(_make_app(asset, user_id="owner")) as client:
        response = client.post("/api/assets/asset-1/publish")

    assert response.status_code == 200
    assert response.json()["visibility"] == "org_shared"


def test_non_owner_cannot_publish_private_asset():
    with TestClient(_make_app(_asset(), user_id="viewer")) as client:
        response = client.post("/api/assets/asset-1/publish")

    assert response.status_code == 404
