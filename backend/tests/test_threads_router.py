import sys
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.gateway.routers import threads
from deerflow.config.paths import Paths


class FakeBusinessStore:
    def __init__(self, thread_owner_map=None):
        self.thread_owner_map = thread_owner_map or {}
        self.calls = []

    async def get_thread(self, thread_id: str):
        user_id = self.thread_owner_map.get(thread_id)
        if user_id is None:
            return None
        return type("ThreadRecord", (), {"id": thread_id, "user_id": user_id})()

    async def create_thread(self, thread_id, *, user_id, title=None, source="web", source_user_id=None):
        self.thread_owner_map[thread_id] = user_id
        self.calls.append(
            {
                "thread_id": thread_id,
                "user_id": user_id,
                "title": title,
                "source": source,
                "source_user_id": source_user_id,
            }
        )

    async def list_threads_for_user(self, user_id):
        return [
            type("ThreadRecord", (), {"id": thread_id})()
            for thread_id, owner_id in self.thread_owner_map.items()
            if owner_id == user_id
        ]


def _build_thread_app(*, user_id: str | None = None, business_store=None):
    app = FastAPI()
    if user_id is not None:
        @app.middleware("http")
        async def inject_user(request, call_next):
            request.state.current_user = type("User", (), {"id": user_id})()
            return await call_next(request)
    if business_store is not None:
        app.state.business_store = business_store
    app.include_router(threads.router)
    return app


def test_delete_thread_data_removes_thread_directory(tmp_path):
    paths = Paths(tmp_path)
    thread_dir = paths.thread_dir("thread-cleanup")
    workspace = paths.sandbox_work_dir("thread-cleanup")
    uploads = paths.sandbox_uploads_dir("thread-cleanup")
    outputs = paths.sandbox_outputs_dir("thread-cleanup")

    for directory in [workspace, uploads, outputs]:
        directory.mkdir(parents=True, exist_ok=True)
    (workspace / "notes.txt").write_text("hello", encoding="utf-8")
    (uploads / "report.pdf").write_bytes(b"pdf")
    (outputs / "result.json").write_text("{}", encoding="utf-8")

    assert thread_dir.exists()

    response = threads._delete_thread_data("thread-cleanup", paths=paths)

    assert response.success is True
    assert not thread_dir.exists()


def test_delete_thread_data_is_idempotent_for_missing_directory(tmp_path):
    paths = Paths(tmp_path)

    response = threads._delete_thread_data("missing-thread", paths=paths)

    assert response.success is True
    assert not paths.thread_dir("missing-thread").exists()


def test_delete_thread_data_rejects_invalid_thread_id(tmp_path):
    paths = Paths(tmp_path)

    with pytest.raises(HTTPException) as exc_info:
        threads._delete_thread_data("../escape", paths=paths)

    assert exc_info.value.status_code == 422
    assert "Invalid thread_id" in exc_info.value.detail


def test_delete_thread_route_cleans_thread_directory(tmp_path):
    paths = Paths(tmp_path)
    thread_dir = paths.thread_dir("thread-route")
    paths.sandbox_work_dir("thread-route").mkdir(parents=True, exist_ok=True)
    (paths.sandbox_work_dir("thread-route") / "notes.txt").write_text("hello", encoding="utf-8")

    app = _build_thread_app(
        user_id="user-1",
        business_store=FakeBusinessStore({"thread-route": "user-1"}),
    )

    with patch("app.gateway.routers.threads.get_paths", return_value=paths):
        with TestClient(app) as client:
            response = client.delete("/api/threads/thread-route")

    assert response.status_code == 200
    assert response.json() == {"success": True, "message": "Deleted local thread data for thread-route"}
    assert not thread_dir.exists()


def test_delete_thread_route_rejects_invalid_thread_id(tmp_path):
    paths = Paths(tmp_path)

    app = _build_thread_app(
        user_id="user-1",
        business_store=FakeBusinessStore(),
    )

    with patch("app.gateway.routers.threads.get_paths", return_value=paths):
        with TestClient(app) as client:
            response = client.delete("/api/threads/../escape")

    assert response.status_code == 404


def test_delete_thread_route_returns_422_for_route_safe_invalid_id(tmp_path):
    paths = Paths(tmp_path)

    app = _build_thread_app(
        user_id="user-1",
        business_store=FakeBusinessStore({"thread.with.dot": "user-1"}),
    )

    with patch("app.gateway.routers.threads.get_paths", return_value=paths):
        with TestClient(app) as client:
            response = client.delete("/api/threads/thread.with.dot")

    assert response.status_code == 422
    assert "Invalid thread_id" in response.json()["detail"]


def test_delete_thread_data_returns_generic_500_error(tmp_path):
    paths = Paths(tmp_path)

    with (
        patch.object(paths, "delete_thread_dir", side_effect=OSError("/secret/path")),
        patch.object(threads.logger, "exception") as log_exception,
    ):
        with pytest.raises(HTTPException) as exc_info:
            threads._delete_thread_data("thread-cleanup", paths=paths)

    assert exc_info.value.status_code == 500
    assert exc_info.value.detail == "Failed to delete local thread data."
    assert "/secret/path" not in exc_info.value.detail
    log_exception.assert_called_once_with("Failed to delete thread data for %s", "thread-cleanup")


def test_create_thread_persists_business_thread_metadata():
    class FakeStore:
        def __init__(self):
            self.records = {}

        async def aget(self, namespace, key):
            value = self.records.get(key)
            if value is None:
                return None
            return type("Item", (), {"value": value})()

        async def aput(self, namespace, key, value):
            self.records[key] = value

    class FakeCheckpointer:
        async def aput(self, config, checkpoint, metadata, versions):
            return {"configurable": {"thread_id": config["configurable"]["thread_id"], "checkpoint_id": "cp-1"}}

    app = _build_thread_app(user_id="user-1", business_store=FakeBusinessStore())
    app.state.store = FakeStore()
    app.state.checkpointer = FakeCheckpointer()

    mock_checkpoint_module = MagicMock()
    mock_checkpoint_module.empty_checkpoint.return_value = {}

    with patch.dict(sys.modules, {"langgraph.checkpoint.base": mock_checkpoint_module}):
        with TestClient(app) as client:
            response = client.post("/api/threads", json={"metadata": {"title": "Owned Thread"}})

    assert response.status_code == 200
    assert app.state.business_store.calls == [
        {
            "thread_id": response.json()["thread_id"],
            "user_id": "user-1",
            "title": "Owned Thread",
            "source": "web",
            "source_user_id": None,
        }
    ]


def test_search_threads_returns_only_owned_threads():
    class FakeStore:
        def __init__(self):
            self.records = {
                "thread-a": {
                    "thread_id": "thread-a",
                    "status": "idle",
                    "created_at": 1,
                    "updated_at": 5,
                    "metadata": {},
                    "values": {"title": "A"},
                },
                "thread-b": {
                    "thread_id": "thread-b",
                    "status": "idle",
                    "created_at": 2,
                    "updated_at": 6,
                    "metadata": {},
                    "values": {"title": "B"},
                },
            }

        async def asearch(self, namespace, limit=10000):
            return [type("Item", (), {"value": value})() for value in self.records.values()]

    class FakeCheckpointer:
        async def alist(self, config, limit=None):
            if False:
                yield None
            return

    app = _build_thread_app(
        user_id="user-1",
        business_store=FakeBusinessStore({"thread-b": "user-1"}),
    )
    app.state.store = FakeStore()
    app.state.checkpointer = FakeCheckpointer()

    with TestClient(app) as client:
        response = client.post("/api/threads/search", json={})

    assert response.status_code == 200
    assert [item["thread_id"] for item in response.json()] == ["thread-b"]


def test_search_threads_requires_authenticated_user():
    class FakeStore:
        async def asearch(self, namespace, limit=10000):
            return []

    class FakeCheckpointer:
        async def alist(self, config, limit=None):
            if False:
                yield None
            return

    app = _build_thread_app(business_store=FakeBusinessStore())
    app.state.store = FakeStore()
    app.state.checkpointer = FakeCheckpointer()

    with TestClient(app) as client:
        response = client.post("/api/threads/search", json={})

    assert response.status_code == 401


def test_get_thread_rejects_non_owner():
    class FakeStore:
        async def aget(self, namespace, key):
            return type(
                "Item",
                (),
                {
                    "value": {
                        "thread_id": key,
                        "status": "idle",
                        "created_at": 1,
                        "updated_at": 1,
                        "metadata": {},
                    }
                },
            )()

    class FakeCheckpointer:
        async def aget_tuple(self, config):
            return type(
                "Tuple",
                (),
                {
                    "checkpoint": {"channel_values": {}},
                    "metadata": {"created_at": 1, "updated_at": 1},
                    "config": {"configurable": {"checkpoint_id": "cp-1"}},
                },
            )()

    app = _build_thread_app(
        user_id="user-1",
        business_store=FakeBusinessStore({"thread-a": "other-user"}),
    )
    app.state.store = FakeStore()
    app.state.checkpointer = FakeCheckpointer()

    with TestClient(app) as client:
        response = client.get("/api/threads/thread-a")

    assert response.status_code == 404
