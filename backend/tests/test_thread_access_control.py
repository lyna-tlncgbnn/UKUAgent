from __future__ import annotations

from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.gateway.routers import runs, suggestions, thread_runs


class FakeBusinessStore:
    def __init__(self, thread_owner_map=None):
        self.thread_owner_map = thread_owner_map or {}

    async def get_thread(self, thread_id: str):
        user_id = self.thread_owner_map.get(thread_id)
        if user_id is None:
            return None
        return type("ThreadRecord", (), {"id": thread_id, "user_id": user_id})()


def _build_app(router, *, user_id: str | None = None, business_store=None):
    app = FastAPI()
    if user_id is not None:
        @app.middleware("http")
        async def inject_user(request, call_next):
            request.state.current_user = type("User", (), {"id": user_id})()
            return await call_next(request)
    app.state.business_store = business_store
    app.include_router(router)
    return app


def test_thread_runs_create_run_rejects_non_owner():
    app = _build_app(
        thread_runs.router,
        user_id="user-1",
        business_store=FakeBusinessStore({"thread-a": "other-user"}),
    )

    with TestClient(app) as client:
        response = client.post("/api/threads/thread-a/runs", json={})

    assert response.status_code == 404


def test_stateless_runs_stream_rejects_existing_thread_of_other_user():
    app = _build_app(
        runs.router,
        user_id="user-1",
        business_store=FakeBusinessStore({"thread-a": "other-user"}),
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/runs/stream",
            json={"config": {"configurable": {"thread_id": "thread-a"}}},
        )

    assert response.status_code == 404


def test_stateless_runs_stream_allows_new_thread_for_authenticated_user():
    async def fake_start_run(body, thread_id, request):
        return type(
            "RunRecord",
            (),
            {
                "run_id": "run-1",
                "thread_id": thread_id,
                "assistant_id": None,
                "status": type("Status", (), {"value": "running"})(),
                "metadata": {},
                "kwargs": {},
                "multitask_strategy": "reject",
                "created_at": "",
                "updated_at": "",
                "task": None,
                "on_disconnect": None,
            },
        )()

    async def fake_sse_consumer(bridge, record, request, run_mgr):
        if False:
            yield None
        return

    app = _build_app(
        runs.router,
        user_id="user-1",
        business_store=FakeBusinessStore(),
    )
    app.state.stream_bridge = object()
    app.state.run_manager = object()

    with (
        patch.object(runs, "start_run", fake_start_run),
        patch.object(runs, "sse_consumer", fake_sse_consumer),
    ):
        with TestClient(app) as client:
            response = client.post("/api/runs/stream", json={})

    assert response.status_code == 200


def test_suggestions_route_rejects_non_owner():
    app = _build_app(
        suggestions.router,
        user_id="user-1",
        business_store=FakeBusinessStore({"thread-a": "other-user"}),
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/threads/thread-a/suggestions",
            json={"messages": [{"role": "user", "content": "Hi"}]},
        )

    assert response.status_code == 404
