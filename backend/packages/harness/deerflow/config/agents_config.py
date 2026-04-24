"""Configuration and loaders for custom agents."""

import logging
import re
import threading
from typing import Any

import yaml
from pydantic import BaseModel
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.persistence.models import AgentContentRecord, AgentRecord, AgentVisibility
from deerflow.config.app_config import get_app_config
from deerflow.config.paths import get_paths

logger = logging.getLogger(__name__)

SOUL_FILENAME = "SOUL.md"
AGENT_NAME_PATTERN = re.compile(r"^[A-Za-z0-9-]+$")


class AgentConfig(BaseModel):
    """Configuration for a custom agent."""

    name: str
    description: str = ""
    model: str | None = None
    tool_groups: list[str] | None = None
    visibility: AgentVisibility = AgentVisibility.PRIVATE


_business_session_factory = None
_business_session_lock = threading.Lock()


def _build_sync_business_connection_string(connection_string: str) -> str:
    if connection_string.startswith("sqlite+aiosqlite:"):
        return connection_string.replace("sqlite+aiosqlite:", "sqlite:", 1)
    if connection_string.startswith("postgresql+asyncpg:"):
        return connection_string.replace("postgresql+asyncpg:", "postgresql+psycopg:", 1)
    return connection_string


def _get_business_session_factory():
    global _business_session_factory
    if _business_session_factory is not None:
        return _business_session_factory

    with _business_session_lock:
        if _business_session_factory is not None:
            return _business_session_factory

        config = get_app_config().business_storage
        if not config.enabled:
            return None

        engine = create_engine(_build_sync_business_connection_string(config.connection_string), echo=config.echo)
        _business_session_factory = sessionmaker(bind=engine, expire_on_commit=False)
        return _business_session_factory


def _load_agent_record_from_business_store(name: str) -> tuple[AgentRecord, AgentContentRecord | None] | None:
    session_factory = _get_business_session_factory()
    if session_factory is None:
        return None

    with session_factory() as session:
        agent = session.execute(select(AgentRecord).where(AgentRecord.slug == name)).scalar_one_or_none()
        if agent is None:
            return None
        content = session.get(AgentContentRecord, agent.id)
        session.expunge(agent)
        if content is not None:
            session.expunge(content)
        return agent, content


def save_agent_to_business_store(
    *,
    agent_id: str,
    owner_user_id: str,
    name: str,
    slug: str,
    description: str | None,
    model: str | None,
    tool_groups: list[str] | None,
    visibility: AgentVisibility,
    soul_md: str,
    config_json: dict[str, Any],
    memory_json: dict[str, Any] | None = None,
) -> bool:
    """Persist an agent into the business store from synchronous runtime code."""

    session_factory = _get_business_session_factory()
    if session_factory is None:
        return False

    try:
        with session_factory() as session:
            agent = session.execute(select(AgentRecord).where(AgentRecord.slug == slug)).scalar_one_or_none()
            if agent is None:
                agent = AgentRecord(
                    id=agent_id,
                    owner_user_id=owner_user_id,
                    name=name,
                    slug=slug,
                    description=description,
                    model=model,
                    tool_groups=list(tool_groups or []),
                    visibility=visibility,
                )
                session.add(agent)
            else:
                agent.owner_user_id = owner_user_id
                agent.name = name
                agent.slug = slug
                agent.description = description
                agent.model = model
                agent.tool_groups = list(tool_groups or [])
                agent.visibility = visibility

            content = session.get(AgentContentRecord, agent_id)
            if content is None:
                content = AgentContentRecord(
                    agent_id=agent_id,
                    soul_md=soul_md,
                    config_json=config_json,
                    memory_json=memory_json,
                )
                session.add(content)
            else:
                content.soul_md = soul_md
                content.config_json = config_json
                content.memory_json = memory_json

            session.commit()
        return True
    except Exception as e:
        logger.error("Failed to save agent '%s' to business store: %s", slug, e)
        return False


def load_agent_config(name: str | None) -> AgentConfig | None:
    """Load the custom or default agent's config from its directory.

    Args:
        name: The agent name.

    Returns:
        AgentConfig instance.

    Raises:
        FileNotFoundError: If the agent directory or config.yaml does not exist.
        ValueError: If config.yaml cannot be parsed.
    """

    if name is None:
        return None

    if not AGENT_NAME_PATTERN.match(name):
        raise ValueError(f"Invalid agent name '{name}'. Must match pattern: {AGENT_NAME_PATTERN.pattern}")

    business_record = _load_agent_record_from_business_store(name)
    if business_record is not None:
        agent, content = business_record
        config_data = dict(content.config_json) if content and isinstance(content.config_json, dict) else {}
        config_data.setdefault("name", agent.slug)
        config_data.setdefault("description", agent.description or "")
        config_data.setdefault("model", agent.model)
        config_data.setdefault("tool_groups", list(agent.tool_groups or []))
        config_data.setdefault("visibility", agent.visibility)
        known_fields = set(AgentConfig.model_fields.keys())
        config_data = {k: v for k, v in config_data.items() if k in known_fields}
        return AgentConfig(**config_data)

    agent_dir = get_paths().agent_dir(name)
    config_file = agent_dir / "config.yaml"

    if not agent_dir.exists():
        raise FileNotFoundError(f"Agent directory not found: {agent_dir}")

    if not config_file.exists():
        raise FileNotFoundError(f"Agent config not found: {config_file}")

    try:
        with open(config_file, encoding="utf-8") as f:
            data: dict[str, Any] = yaml.safe_load(f) or {}
    except yaml.YAMLError as e:
        raise ValueError(f"Failed to parse agent config {config_file}: {e}") from e

    # Ensure name is set from directory name if not in file
    if "name" not in data:
        data["name"] = name

    # Strip unknown fields before passing to Pydantic (e.g. legacy prompt_file)
    known_fields = set(AgentConfig.model_fields.keys())
    data = {k: v for k, v in data.items() if k in known_fields}

    return AgentConfig(**data)


def load_agent_soul(agent_name: str | None) -> str | None:
    """Read the SOUL.md file for a custom agent, if it exists.

    SOUL.md defines the agent's personality, values, and behavioral guardrails.
    It is injected into the lead agent's system prompt as additional context.

    Args:
        agent_name: The name of the agent or None for the default agent.

    Returns:
        The SOUL.md content as a string, or None if the file does not exist.
    """
    if agent_name:
        business_record = _load_agent_record_from_business_store(agent_name)
        if business_record is not None:
            _agent, content = business_record
            if content is not None:
                value = content.soul_md.strip()
                return value or None

    agent_dir = get_paths().agent_dir(agent_name) if agent_name else get_paths().base_dir
    soul_path = agent_dir / SOUL_FILENAME
    if not soul_path.exists():
        return None
    content = soul_path.read_text(encoding="utf-8").strip()
    return content or None


def list_custom_agents() -> list[AgentConfig]:
    """Scan the agents directory and return all valid custom agents.

    Returns:
        List of AgentConfig for each valid agent directory found.
    """
    session_factory = _get_business_session_factory()
    if session_factory is not None:
        with session_factory() as session:
            records = session.execute(select(AgentRecord).order_by(AgentRecord.updated_at.desc())).scalars().all()
            if records:
                return [
                    AgentConfig(
                        name=record.slug,
                        description=record.description or "",
                        model=record.model,
                        tool_groups=list(record.tool_groups or []),
                        visibility=record.visibility,
                    )
                    for record in records
                ]

    agents_dir = get_paths().agents_dir

    if not agents_dir.exists():
        return []

    agents: list[AgentConfig] = []

    for entry in sorted(agents_dir.iterdir()):
        if not entry.is_dir():
            continue

        config_file = entry / "config.yaml"
        if not config_file.exists():
            logger.debug(f"Skipping {entry.name}: no config.yaml")
            continue

        try:
            agent_cfg = load_agent_config(entry.name)
            agents.append(agent_cfg)
        except Exception as e:
            logger.warning(f"Skipping agent '{entry.name}': {e}")

    return agents
