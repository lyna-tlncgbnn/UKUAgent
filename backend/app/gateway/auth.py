from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException, Request, status

from app.persistence import BusinessStore, ThreadRecord, UserRole

logger = logging.getLogger(__name__)

AUTH_PROXY_SECRET_HEADER = "x-deerflow-auth-proxy-secret"
AUTH_USER_ID_HEADER = "x-deerflow-auth-user-id"
AUTH_USER_EMAIL_HEADER = "x-deerflow-auth-user-email"
AUTH_USER_NAME_HEADER = "x-deerflow-auth-user-name"
AUTH_USER_ROLE_HEADER = "x-deerflow-auth-user-role"


@dataclass(slots=True)
class AuthenticatedUser:
    """Authenticated user context derived from the frontend auth proxy."""

    id: str
    email: str | None
    name: str
    role: str


def _normalize_user_role(value: str | None) -> str:
    if value in {UserRole.ADMIN.value, UserRole.MEMBER.value}:
        return value
    return UserRole.MEMBER.value


def build_authenticated_user_from_headers(headers: Any, expected_proxy_secret: str) -> AuthenticatedUser | None:
    """Build an authenticated user from trusted forwarded headers."""

    user_id = headers.get(AUTH_USER_ID_HEADER)
    if not user_id:
        return None

    provided_secret = headers.get(AUTH_PROXY_SECRET_HEADER)
    if provided_secret != expected_proxy_secret:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid auth proxy signature.")

    email = headers.get(AUTH_USER_EMAIL_HEADER)
    name = headers.get(AUTH_USER_NAME_HEADER) or email or user_id
    role = _normalize_user_role(headers.get(AUTH_USER_ROLE_HEADER))
    return AuthenticatedUser(id=user_id, email=email, name=name, role=role)


async def sync_authenticated_user(store: BusinessStore | None, user: AuthenticatedUser | None) -> None:
    """Persist the current user into the business store when available."""

    if store is None or user is None:
        return

    role = UserRole.ADMIN if user.role == UserRole.ADMIN.value else UserRole.MEMBER
    await store.upsert_user(user.id, email=user.email, name=user.name, role=role)


async def resolve_authenticated_user(
    request: Request,
    *,
    expected_proxy_secret: str,
    business_store: BusinessStore | None = None,
) -> AuthenticatedUser | None:
    """Resolve and optionally persist the current authenticated user."""

    try:
        user = build_authenticated_user_from_headers(request.headers, expected_proxy_secret)
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to parse trusted auth headers")
        return None

    await sync_authenticated_user(business_store, user)
    return user


def get_optional_current_user(request: Request) -> AuthenticatedUser | None:
    """Return the current authenticated user if available."""

    return getattr(request.state, "current_user", None)


def require_current_user(request: Request) -> AuthenticatedUser:
    """Require an authenticated user context to be present on the request."""

    user = get_optional_current_user(request)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")
    return user


def require_business_store(request: Request) -> BusinessStore:
    """Require the multi-user business store to be configured."""

    store = getattr(request.app.state, "business_store", None)
    if store is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Business store not available.",
        )
    return store


async def require_owned_thread(
    request: Request,
    thread_id: str,
    *,
    allow_missing: bool = False,
) -> ThreadRecord | None:
    """Require the current user to own the given thread.

    When ``allow_missing`` is true, an unknown thread is treated as creatable by
    the current user and ``None`` is returned. This is used by stateless run
    endpoints that may bootstrap a new thread on first use.
    """

    user = require_current_user(request)
    store = require_business_store(request)
    thread = await store.get_thread(thread_id)
    if thread is None:
        if allow_missing:
            return None
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Thread {thread_id} not found")
    if thread.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Thread {thread_id} not found")
    return thread
