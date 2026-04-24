"""Tests for trusted auth header resolution in the gateway."""

from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException
from starlette.requests import Request
from starlette.datastructures import Headers

from app.gateway.auth import (
    AUTH_PROXY_SECRET_HEADER,
    AUTH_USER_EMAIL_HEADER,
    AUTH_USER_ID_HEADER,
    AUTH_USER_NAME_HEADER,
    AUTH_USER_ROLE_HEADER,
    AuthenticatedUser,
    build_authenticated_user_from_headers,
    require_owned_thread,
    sync_authenticated_user,
)


def test_build_authenticated_user_from_headers_returns_none_without_user_id():
    headers = Headers({})
    assert build_authenticated_user_from_headers(headers, "secret") is None


def test_build_authenticated_user_from_headers_parses_trusted_headers():
    headers = Headers(
        {
            AUTH_PROXY_SECRET_HEADER: "secret",
            AUTH_USER_ID_HEADER: "user-1",
            AUTH_USER_EMAIL_HEADER: "user1@example.com",
            AUTH_USER_NAME_HEADER: "User One",
            AUTH_USER_ROLE_HEADER: "admin",
        }
    )

    user = build_authenticated_user_from_headers(headers, "secret")

    assert user == AuthenticatedUser(
        id="user-1",
        email="user1@example.com",
        name="User One",
        role="admin",
    )


def test_build_authenticated_user_from_headers_rejects_invalid_secret():
    headers = Headers(
        {
            AUTH_PROXY_SECRET_HEADER: "wrong",
            AUTH_USER_ID_HEADER: "user-1",
        }
    )

    with pytest.raises(Exception):
        build_authenticated_user_from_headers(headers, "secret")


def test_sync_authenticated_user_persists_to_store():
    class FakeStore:
        def __init__(self) -> None:
            self.calls: list[dict] = []

        async def upsert_user(self, user_id: str, *, email: str | None, name: str, role):
            self.calls.append(
                {
                    "user_id": user_id,
                    "email": email,
                    "name": name,
                    "role": role.value,
                }
            )

    store = FakeStore()
    user = AuthenticatedUser(
        id="user-1",
        email="user1@example.com",
        name="User One",
        role="admin",
    )

    asyncio.run(sync_authenticated_user(store, user))

    assert store.calls == [
        {
            "user_id": "user-1",
            "email": "user1@example.com",
            "name": "User One",
            "role": "admin",
        }
    ]


def _make_request(*, user=None, business_store=None) -> Request:
    app = type("App", (), {"state": type("AppState", (), {"business_store": business_store})()})()
    scope = {
        "type": "http",
        "headers": [],
        "app": app,
        "state": {},
    }
    request = Request(scope)
    if user is not None:
        request.state.current_user = user
    return request


def test_require_owned_thread_rejects_unauthenticated_request():
    class FakeBusinessStore:
        async def get_thread(self, thread_id: str):
            return None

    request = _make_request(business_store=FakeBusinessStore())

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(require_owned_thread(request, "thread-1"))

    assert exc_info.value.status_code == 401


def test_require_owned_thread_rejects_non_owner():
    class FakeBusinessStore:
        async def get_thread(self, thread_id: str):
            return type("ThreadRecord", (), {"id": thread_id, "user_id": "other-user"})()

    request = _make_request(
        user=AuthenticatedUser(id="user-1", email=None, name="User One", role="member"),
        business_store=FakeBusinessStore(),
    )

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(require_owned_thread(request, "thread-1"))

    assert exc_info.value.status_code == 404


def test_require_owned_thread_allows_missing_when_requested():
    class FakeBusinessStore:
        async def get_thread(self, thread_id: str):
            return None

    request = _make_request(
        user=AuthenticatedUser(id="user-1", email=None, name="User One", role="member"),
        business_store=FakeBusinessStore(),
    )

    result = asyncio.run(require_owned_thread(request, "thread-1", allow_missing=True))

    assert result is None
