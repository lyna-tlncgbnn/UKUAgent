from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.gateway.routers import agents


def _build_agents_app():
    app = FastAPI()

    @app.middleware("http")
    async def inject_user(request, call_next):
        request.state.current_user = type("User", (), {"id": "user-1"})()
        return await call_next(request)

    app.include_router(agents.router)
    return app


def test_get_user_profile_reads_current_user_profile():
    app = _build_agents_app()

    with patch("app.gateway.routers.agents.get_user_profile_markdown", return_value="# Profile") as get_profile:
        with TestClient(app) as client:
            response = client.get("/api/user-profile")

    assert response.status_code == 200
    get_profile.assert_called_once_with("user-1")
    assert response.json() == {"content": "# Profile"}


def test_put_user_profile_updates_current_user_profile():
    app = _build_agents_app()

    with patch("app.gateway.routers.agents.update_user_profile_markdown", return_value=True) as update_profile:
        with TestClient(app) as client:
            response = client.put("/api/user-profile", json={"content": "# Updated"})

    assert response.status_code == 200
    update_profile.assert_called_once_with("user-1", "# Updated")
    assert response.json() == {"content": "# Updated"}
