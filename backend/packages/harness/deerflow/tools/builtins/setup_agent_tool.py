import logging
from uuid import uuid4

import yaml
from langchain_core.messages import ToolMessage
from langchain_core.tools import tool
from langgraph.prebuilt import ToolRuntime
from langgraph.types import Command

from app.persistence.models import AgentVisibility
from deerflow.config.app_config import get_app_config
from deerflow.config.agents_config import save_agent_to_business_store
from deerflow.config.paths import get_paths

logger = logging.getLogger(__name__)


def _resolve_owner_from_thread(thread_id: str | None) -> str | None:
    if not thread_id:
        return None

    try:
        from sqlalchemy import create_engine, select
        from sqlalchemy.orm import sessionmaker

        from app.persistence.models import ThreadRecord

        config = get_app_config().business_storage
        if not config.enabled:
            return None

        connection_string = config.connection_string
        if connection_string.startswith("sqlite+aiosqlite:"):
            connection_string = connection_string.replace("sqlite+aiosqlite:", "sqlite:", 1)
        elif connection_string.startswith("postgresql+asyncpg:"):
            connection_string = connection_string.replace("postgresql+asyncpg:", "postgresql+psycopg:", 1)

        engine = create_engine(connection_string, echo=False)
        try:
            session_factory = sessionmaker(bind=engine, expire_on_commit=False)
            with session_factory() as session:
                return session.execute(select(ThreadRecord.user_id).where(ThreadRecord.id == thread_id)).scalar_one_or_none()
        finally:
            engine.dispose()
    except Exception:
        logger.warning("Failed to resolve owner from bootstrap thread %s", thread_id, exc_info=True)
        return None


@tool
def setup_agent(
    soul: str,
    description: str,
    runtime: ToolRuntime,
) -> Command:
    """Setup the custom DeerFlow agent.

    Args:
        soul: Full SOUL.md content defining the agent's personality and behavior.
        description: One-line description of what the agent does.
    """

    agent_name: str | None = runtime.context.get("agent_name") if runtime.context else None
    agent_slug = agent_name.lower() if agent_name else None
    user_id: str | None = runtime.context.get("user_id") if runtime.context else None
    thread_id: str | None = runtime.context.get("thread_id") if runtime.context else None
    raw_visibility = runtime.context.get("agent_visibility") if runtime.context else None
    visibility = AgentVisibility.ORG_SHARED if raw_visibility == AgentVisibility.ORG_SHARED.value else AgentVisibility.PRIVATE
    owner_user_id = user_id or _resolve_owner_from_thread(thread_id)
    business_storage_enabled = get_app_config().business_storage.enabled

    try:
        if agent_slug and business_storage_enabled and not owner_user_id:
            raise RuntimeError("Could not determine the current user for this agent creation run.")

        paths = get_paths()
        agent_dir = paths.agent_dir(agent_slug) if agent_slug else paths.base_dir
        agent_dir.mkdir(parents=True, exist_ok=True)

        if agent_slug:
            # If agent_name is provided, we are creating a custom agent in the agents/ directory
            config_data: dict = {"name": agent_slug}
            if description:
                config_data["description"] = description

            config_file = agent_dir / "config.yaml"
            with open(config_file, "w", encoding="utf-8") as f:
                yaml.dump(config_data, f, default_flow_style=False, allow_unicode=True)

            if owner_user_id:
                save_agent_to_business_store(
                    agent_id=uuid4().hex,
                    owner_user_id=owner_user_id,
                    name=agent_name,
                    slug=agent_slug,
                    description=description or None,
                    model=None,
                    tool_groups=None,
                    visibility=visibility,
                    soul_md=soul,
                    config_json=config_data,
                )

        soul_file = agent_dir / "SOUL.md"
        soul_file.write_text(soul, encoding="utf-8")

        logger.info(f"[agent_creator] Created agent '{agent_slug}' at {agent_dir}")
        return Command(
            update={
                "created_agent_name": agent_slug,
                "messages": [ToolMessage(content=f"Agent '{agent_slug}' created successfully!", tool_call_id=runtime.tool_call_id)],
            }
        )

    except Exception as e:
        import shutil

        if agent_slug and agent_dir.exists():
            # Cleanup the custom agent directory only if it was created but an error occurred during setup
            shutil.rmtree(agent_dir)
        logger.error(f"[agent_creator] Failed to create agent '{agent_slug}': {e}", exc_info=True)
        return Command(update={"messages": [ToolMessage(content=f"Error: {e}", tool_call_id=runtime.tool_call_id)]})
