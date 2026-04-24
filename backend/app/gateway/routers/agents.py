"""CRUD API for custom agents."""

from __future__ import annotations

import logging
import re
import shutil
from uuid import uuid4

import yaml
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.gateway.auth import (
    require_accessible_agent,
    require_business_store,
    require_current_user,
)
from app.gateway.deps import get_checkpointer
from app.persistence.models import AgentVisibility
from deerflow.agents.memory.updater import (
    get_user_profile_markdown,
    update_user_profile_markdown,
)
from deerflow.config.agents_config import (
    AgentConfig,
    load_agent_config,
    load_agent_soul,
)
from deerflow.config.paths import get_paths

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["agents"])

AGENT_NAME_PATTERN = re.compile(r"^[A-Za-z0-9-]+$")


class AgentResponse(BaseModel):
    """Response model for a custom agent."""

    name: str = Field(..., description="Display name")
    slug: str = Field(..., description="Stable unique slug used in routes and runtime context")
    description: str = Field(default="", description="Agent description")
    model: str | None = Field(default=None, description="Optional model override")
    tool_groups: list[str] | None = Field(default=None, description="Optional tool group whitelist")
    visibility: AgentVisibility = Field(default=AgentVisibility.PRIVATE, description="Private or org-shared visibility")
    is_owner: bool = Field(default=False, description="Whether the current user owns this agent")
    soul: str | None = Field(default=None, description="SOUL.md content (included on GET /{slug})")


class AgentsListResponse(BaseModel):
    """Response model for listing all accessible agents."""

    agents: list[AgentResponse]


class AgentCreateRequest(BaseModel):
    """Request body for creating a custom agent."""

    name: str = Field(..., description="Agent slug (must match ^[A-Za-z0-9-]+$, stored as lowercase)")
    description: str = Field(default="", description="Agent description")
    model: str | None = Field(default=None, description="Optional model override")
    tool_groups: list[str] | None = Field(default=None, description="Optional tool group whitelist")
    visibility: AgentVisibility = Field(default=AgentVisibility.PRIVATE, description="Private or organization-shared")
    soul: str = Field(default="", description="SOUL.md content")


class AgentUpdateRequest(BaseModel):
    """Request body for updating an existing custom agent."""

    description: str | None = Field(default=None, description="Updated description")
    model: str | None = Field(default=None, description="Updated model override")
    tool_groups: list[str] | None = Field(default=None, description="Updated tool group whitelist")
    visibility: AgentVisibility | None = Field(default=None, description="Updated visibility")
    soul: str | None = Field(default=None, description="Updated SOUL.md content")


class UserProfileResponse(BaseModel):
    """Response model for the current user's profile markdown."""

    content: str | None = Field(default=None, description="Profile markdown content, or null if not yet created")


class UserProfileUpdateRequest(BaseModel):
    """Request body for setting the current user's profile markdown."""

    content: str = Field(default="", description="USER.md content describing the user's background and preferences")


def _validate_agent_name(name: str) -> None:
    if not AGENT_NAME_PATTERN.match(name):
        raise HTTPException(
            status_code=422,
            detail=f"Invalid agent name '{name}'. Must match ^[A-Za-z0-9-]+$ (letters, digits, and hyphens only).",
        )


def _normalize_agent_name(name: str) -> str:
    return name.lower()


def _write_agent_files(
    *,
    slug: str,
    description: str,
    model: str | None,
    tool_groups: list[str] | None,
    soul: str,
) -> None:
    """Write the filesystem mirror consumed by the current runtime."""

    agent_dir = get_paths().agent_dir(slug)
    agent_dir.mkdir(parents=True, exist_ok=True)

    config_data: dict = {"name": slug}
    if description:
        config_data["description"] = description
    if model is not None:
        config_data["model"] = model
    if tool_groups is not None:
        config_data["tool_groups"] = tool_groups

    with open(agent_dir / "config.yaml", "w", encoding="utf-8") as f:
        yaml.dump(config_data, f, default_flow_style=False, allow_unicode=True)
    (agent_dir / "SOUL.md").write_text(soul, encoding="utf-8")


def _build_config_json(
    *,
    slug: str,
    description: str,
    model: str | None,
    tool_groups: list[str] | None,
    visibility: AgentVisibility,
) -> dict:
    payload: dict = {
        "name": slug,
        "description": description,
        "visibility": visibility,
    }
    if model is not None:
        payload["model"] = model
    if tool_groups is not None:
        payload["tool_groups"] = tool_groups
    return payload


async def _reconcile_filesystem_agent(request: Request, slug: str):
    business_store = require_business_store(request)
    record = await business_store.get_agent_by_slug(slug)
    if record is not None:
        return record

    agent_dir = get_paths().agent_dir(slug)
    if not agent_dir.exists():
        return None

    owner_user_id = None
    expected_title = f"生成{slug}智能体SOUL"
    checkpointer = get_checkpointer(request)
    for thread in await business_store.list_threads(limit=100):
        try:
            checkpoint = await checkpointer.aget_tuple({"configurable": {"thread_id": thread.id, "checkpoint_ns": ""}})
        except Exception:
            continue
        if checkpoint is None:
            continue
        title = checkpoint.checkpoint.get("channel_values", {}).get("title")
        if title == expected_title:
            owner_user_id = thread.user_id
            break

    if not owner_user_id:
        return None

    agent_cfg = load_agent_config(slug)
    if agent_cfg is None:
        return None

    return await business_store.create_agent(
        uuid4().hex,
        owner_user_id=owner_user_id,
        name=agent_cfg.name,
        slug=slug,
        description=agent_cfg.description or None,
        model=agent_cfg.model,
        tool_groups=list(agent_cfg.tool_groups or []),
        visibility=agent_cfg.visibility,
        soul_md=load_agent_soul(slug) or "",
        config_json=_build_config_json(
            slug=slug,
            description=agent_cfg.description,
            model=agent_cfg.model,
            tool_groups=agent_cfg.tool_groups,
            visibility=agent_cfg.visibility,
        ),
    )


async def _reconcile_filesystem_agents(request: Request) -> None:
    agents_dir = get_paths().agents_dir
    if not agents_dir.exists():
        return

    for entry in sorted(agents_dir.iterdir()):
        if not entry.is_dir():
            continue
        slug = entry.name
        if not AGENT_NAME_PATTERN.match(slug):
            continue
        try:
            await _reconcile_filesystem_agent(request, slug)
        except Exception:
            logger.warning("Failed to reconcile filesystem agent '%s'", slug, exc_info=True)


def _agent_config_to_response(
    agent_cfg: AgentConfig,
    *,
    slug: str | None = None,
    include_soul: bool = False,
    is_owner: bool = False,
) -> AgentResponse:
    soul: str | None = None
    if include_soul:
        soul = load_agent_soul(slug or agent_cfg.name) or ""

    return AgentResponse(
        name=agent_cfg.name,
        slug=slug or agent_cfg.name,
        description=agent_cfg.description,
        model=agent_cfg.model,
        tool_groups=agent_cfg.tool_groups,
        visibility=agent_cfg.visibility,
        is_owner=is_owner,
        soul=soul,
    )


@router.get(
    "/agents",
    response_model=AgentsListResponse,
    summary="List Accessible Agents",
    description="List all agents visible to the current user (owned + org shared).",
)
async def list_agents(request: Request) -> AgentsListResponse:
    current_user = require_current_user(request)
    business_store = require_business_store(request)

    try:
        await _reconcile_filesystem_agents(request)
        records = await business_store.list_accessible_agents(current_user.id)
        agents = [
            _agent_config_to_response(
                AgentConfig(
                    name=record.name,
                    description=record.description or "",
                    model=record.model,
                    tool_groups=list(record.tool_groups or []),
                    visibility=record.visibility,
                ),
                slug=record.slug,
                is_owner=record.owner_user_id == current_user.id,
            )
            for record in records
        ]
        return AgentsListResponse(agents=agents)
    except Exception as e:
        logger.error("Failed to list agents: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to list agents: {str(e)}")


@router.get(
    "/agents/check",
    summary="Check Agent Slug",
    description="Validate an agent slug and check if it is available.",
)
async def check_agent_name(request: Request, name: str) -> dict:
    require_current_user(request)
    business_store = require_business_store(request)

    _validate_agent_name(name)
    normalized = _normalize_agent_name(name)
    available = await business_store.is_agent_slug_available(normalized) and not get_paths().agent_dir(normalized).exists()
    return {"available": available, "name": normalized}


@router.get(
    "/agents/{name}",
    response_model=AgentResponse,
    summary="Get Agent",
    description="Retrieve details and SOUL.md content for a specific accessible agent.",
)
async def get_agent(request: Request, name: str) -> AgentResponse:
    current_user = require_current_user(request)
    _validate_agent_name(name)
    slug = _normalize_agent_name(name)

    try:
        await _reconcile_filesystem_agent(request, slug)
        agent_record = await require_accessible_agent(request, slug)
        agent_cfg = load_agent_config(slug)
        if agent_cfg is None:
            raise FileNotFoundError(slug)
        return _agent_config_to_response(
            agent_cfg,
            slug=agent_record.slug,
            include_soul=True,
            is_owner=agent_record.owner_user_id == current_user.id,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Agent '{slug}' not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get agent '%s': %s", slug, e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get agent: {str(e)}")


@router.post(
    "/agents",
    response_model=AgentResponse,
    status_code=201,
    summary="Create Agent",
    description="Create a new private or organization-shared agent.",
)
async def create_agent_endpoint(request: Request, payload: AgentCreateRequest) -> AgentResponse:
    current_user = require_current_user(request)
    business_store = require_business_store(request)

    _validate_agent_name(payload.name)
    slug = _normalize_agent_name(payload.name)

    if not await business_store.is_agent_slug_available(slug) or get_paths().agent_dir(slug).exists():
        raise HTTPException(status_code=409, detail=f"Agent '{slug}' already exists")

    agent_dir = get_paths().agent_dir(slug)
    try:
        _write_agent_files(
            slug=slug,
            description=payload.description,
            model=payload.model,
            tool_groups=payload.tool_groups,
            soul=payload.soul,
        )

        await business_store.create_agent(
            uuid4().hex,
            owner_user_id=current_user.id,
            name=payload.name,
            slug=slug,
            description=payload.description or None,
            model=payload.model,
            tool_groups=list(payload.tool_groups or []),
            visibility=payload.visibility,
            soul_md=payload.soul,
            config_json=_build_config_json(
                slug=slug,
                description=payload.description,
                model=payload.model,
                tool_groups=payload.tool_groups,
                visibility=payload.visibility,
            ),
        )

        agent_cfg = load_agent_config(slug)
        if agent_cfg is None:
            raise FileNotFoundError(slug)
        return _agent_config_to_response(agent_cfg, slug=slug, include_soul=True, is_owner=True)
    except HTTPException:
        raise
    except Exception as e:
        if agent_dir.exists():
            shutil.rmtree(agent_dir)
        logger.error("Failed to create agent '%s': %s", slug, e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to create agent: {str(e)}")


@router.put(
    "/agents/{name}",
    response_model=AgentResponse,
    summary="Update Agent",
    description="Update an owned agent's metadata, visibility, and SOUL.",
)
async def update_agent(request: Request, name: str, payload: AgentUpdateRequest) -> AgentResponse:
    current_user = require_current_user(request)
    business_store = require_business_store(request)

    _validate_agent_name(name)
    slug = _normalize_agent_name(name)

    await require_accessible_agent(request, slug, owner_only=True)
    agent_cfg = load_agent_config(slug)
    if agent_cfg is None:
        raise HTTPException(status_code=404, detail=f"Agent '{slug}' not found")

    updated_description = payload.description if payload.description is not None else agent_cfg.description
    updated_model = payload.model if payload.model is not None else agent_cfg.model
    updated_tool_groups = payload.tool_groups if payload.tool_groups is not None else agent_cfg.tool_groups
    updated_visibility = payload.visibility if payload.visibility is not None else agent_cfg.visibility
    updated_soul = payload.soul if payload.soul is not None else (load_agent_soul(slug) or "")

    try:
        _write_agent_files(
            slug=slug,
            description=updated_description,
            model=updated_model,
            tool_groups=updated_tool_groups,
            soul=updated_soul,
        )

        record = await business_store.get_agent_by_slug(slug)
        if record is None:
            raise HTTPException(status_code=404, detail=f"Agent '{slug}' not found")

        await business_store.create_agent(
            record.id,
            owner_user_id=current_user.id,
            name=record.name,
            slug=slug,
            description=updated_description or None,
            model=updated_model,
            tool_groups=list(updated_tool_groups or []),
            visibility=updated_visibility,
            soul_md=updated_soul,
            config_json=_build_config_json(
                slug=slug,
                description=updated_description,
                model=updated_model,
                tool_groups=updated_tool_groups,
                visibility=updated_visibility,
            ),
        )

        refreshed = load_agent_config(slug)
        if refreshed is None:
            raise FileNotFoundError(slug)
        return _agent_config_to_response(refreshed, slug=slug, include_soul=True, is_owner=True)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update agent '%s': %s", slug, e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to update agent: {str(e)}")


@router.delete(
    "/agents/{name}",
    status_code=204,
    summary="Delete Agent",
    description="Delete an owned agent and its mirrored filesystem files.",
)
async def delete_agent(request: Request, name: str) -> None:
    _validate_agent_name(name)
    slug = _normalize_agent_name(name)
    business_store = require_business_store(request)
    await require_accessible_agent(request, slug, owner_only=True)

    try:
        deleted = await business_store.delete_agent_by_slug(slug)
        if not deleted:
            raise HTTPException(status_code=404, detail=f"Agent '{slug}' not found")

        agent_dir = get_paths().agent_dir(slug)
        if agent_dir.exists():
            shutil.rmtree(agent_dir)
        logger.info("Deleted agent '%s'", slug)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to delete agent '%s': %s", slug, e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to delete agent: {str(e)}")


@router.get(
    "/user-profile",
    response_model=UserProfileResponse,
    summary="Get User Profile",
    description="Read the current authenticated user's profile markdown.",
)
async def get_user_profile(request: Request) -> UserProfileResponse:
    try:
        current_user = require_current_user(request)
        raw = get_user_profile_markdown(current_user.id).strip()
        return UserProfileResponse(content=raw or None)
    except Exception as e:
        logger.error("Failed to read user profile: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to read user profile: {str(e)}")


@router.put(
    "/user-profile",
    response_model=UserProfileResponse,
    summary="Update User Profile",
    description="Write the current authenticated user's profile markdown.",
)
async def update_user_profile(request: Request, payload: UserProfileUpdateRequest) -> UserProfileResponse:
    try:
        current_user = require_current_user(request)
        if not update_user_profile_markdown(current_user.id, payload.content):
            raise HTTPException(status_code=500, detail="Failed to update user profile.")
        logger.info("Updated user profile for %s", current_user.id)
        return UserProfileResponse(content=payload.content or None)
    except Exception as e:
        logger.error("Failed to update user profile: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to update user profile: {str(e)}")
