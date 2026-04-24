"""Memory storage providers."""

import abc
import json
import logging
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.persistence.models import UserMemoryRecord
from deerflow.config.app_config import get_app_config
from deerflow.config.agents_config import AGENT_NAME_PATTERN
from deerflow.config.memory_config import get_memory_config
from deerflow.config.paths import get_paths

logger = logging.getLogger(__name__)


def create_empty_memory() -> dict[str, Any]:
    """Create an empty memory structure."""
    return {
        "version": "1.0",
        "lastUpdated": datetime.utcnow().isoformat() + "Z",
        "user": {
            "workContext": {"summary": "", "updatedAt": ""},
            "personalContext": {"summary": "", "updatedAt": ""},
            "topOfMind": {"summary": "", "updatedAt": ""},
        },
        "history": {
            "recentMonths": {"summary": "", "updatedAt": ""},
            "earlierContext": {"summary": "", "updatedAt": ""},
            "longTermBackground": {"summary": "", "updatedAt": ""},
        },
        "facts": [],
    }


class MemoryStorage(abc.ABC):
    """Abstract base class for memory storage providers."""

    @abc.abstractmethod
    def load(self, agent_name: str | None = None) -> dict[str, Any]:
        """Load memory data for the given agent."""
        pass

    @abc.abstractmethod
    def reload(self, agent_name: str | None = None) -> dict[str, Any]:
        """Force reload memory data for the given agent."""
        pass

    @abc.abstractmethod
    def save(self, memory_data: dict[str, Any], agent_name: str | None = None) -> bool:
        """Save memory data for the given agent."""
        pass


class FileMemoryStorage(MemoryStorage):
    """File-based memory storage provider."""

    def __init__(self):
        """Initialize the file memory storage."""
        # Per-agent memory cache: keyed by agent_name (None = global)
        # Value: (memory_data, file_mtime)
        self._memory_cache: dict[str | None, tuple[dict[str, Any], float | None]] = {}

    def _validate_agent_name(self, agent_name: str) -> None:
        """Validate that the agent name is safe to use in filesystem paths.

        Uses the repository's established AGENT_NAME_PATTERN to ensure consistency
        across the codebase and prevent path traversal or other problematic characters.
        """
        if not agent_name:
            raise ValueError("Agent name must be a non-empty string.")
        if not AGENT_NAME_PATTERN.match(agent_name):
            raise ValueError(f"Invalid agent name {agent_name!r}: names must match {AGENT_NAME_PATTERN.pattern}")

    def _get_memory_file_path(self, agent_name: str | None = None) -> Path:
        """Get the path to the memory file."""
        if agent_name is not None:
            self._validate_agent_name(agent_name)
            return get_paths().agent_memory_file(agent_name)

        config = get_memory_config()
        if config.storage_path:
            p = Path(config.storage_path)
            return p if p.is_absolute() else get_paths().base_dir / p
        return get_paths().memory_file

    def _load_memory_from_file(self, agent_name: str | None = None) -> dict[str, Any]:
        """Load memory data from file."""
        file_path = self._get_memory_file_path(agent_name)

        if not file_path.exists():
            return create_empty_memory()

        try:
            with open(file_path, encoding="utf-8") as f:
                data = json.load(f)
            return data
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to load memory file: %s", e)
            return create_empty_memory()

    def load(self, agent_name: str | None = None) -> dict[str, Any]:
        """Load memory data (cached with file modification time check)."""
        file_path = self._get_memory_file_path(agent_name)

        try:
            current_mtime = file_path.stat().st_mtime if file_path.exists() else None
        except OSError:
            current_mtime = None

        cached = self._memory_cache.get(agent_name)

        if cached is None or cached[1] != current_mtime:
            memory_data = self._load_memory_from_file(agent_name)
            self._memory_cache[agent_name] = (memory_data, current_mtime)
            return memory_data

        return cached[0]

    def reload(self, agent_name: str | None = None) -> dict[str, Any]:
        """Reload memory data from file, forcing cache invalidation."""
        file_path = self._get_memory_file_path(agent_name)
        memory_data = self._load_memory_from_file(agent_name)

        try:
            mtime = file_path.stat().st_mtime if file_path.exists() else None
        except OSError:
            mtime = None

        self._memory_cache[agent_name] = (memory_data, mtime)
        return memory_data

    def save(self, memory_data: dict[str, Any], agent_name: str | None = None) -> bool:
        """Save memory data to file and update cache."""
        file_path = self._get_memory_file_path(agent_name)

        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            memory_data["lastUpdated"] = datetime.utcnow().isoformat() + "Z"

            temp_path = file_path.with_suffix(".tmp")
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(memory_data, f, indent=2, ensure_ascii=False)

            temp_path.replace(file_path)

            try:
                mtime = file_path.stat().st_mtime
            except OSError:
                mtime = None

            self._memory_cache[agent_name] = (memory_data, mtime)
            logger.info("Memory saved to %s", file_path)
            return True
        except OSError as e:
            logger.error("Failed to save memory file: %s", e)
            return False


_storage_instance: MemoryStorage | None = None
_storage_lock = threading.Lock()
_business_session_factory = None
_business_session_lock = threading.Lock()


def _build_sync_business_connection_string(connection_string: str) -> str:
    """Convert async SQLAlchemy URLs into sync URLs for memory/profile access."""

    if connection_string.startswith("sqlite+aiosqlite:"):
        return connection_string.replace("sqlite+aiosqlite:", "sqlite:", 1)
    if connection_string.startswith("postgresql+asyncpg:"):
        return connection_string.replace("postgresql+asyncpg:", "postgresql+psycopg:", 1)
    return connection_string


def _get_business_session_factory():
    """Create a synchronous session factory for business user-memory access."""

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


def load_user_memory_from_business_store(user_id: str) -> dict[str, Any]:
    """Load per-user memory from the business store, falling back to an empty structure."""

    session_factory = _get_business_session_factory()
    if session_factory is None:
        return get_memory_storage().load(None)

    with session_factory() as session:
        record = session.get(UserMemoryRecord, user_id)
        if record is None or not isinstance(record.memory_json, dict):
            return create_empty_memory()
        return dict(record.memory_json)


def save_user_memory_to_business_store(user_id: str, memory_data: dict[str, Any]) -> bool:
    """Persist per-user memory into the business store."""

    session_factory = _get_business_session_factory()
    if session_factory is None:
        return get_memory_storage().save(memory_data, None)

    try:
        normalized = dict(memory_data)
        normalized["lastUpdated"] = datetime.utcnow().isoformat() + "Z"
        with session_factory() as session:
            record = session.get(UserMemoryRecord, user_id)
            if record is None:
                record = UserMemoryRecord(user_id=user_id, memory_json=normalized, user_profile_md="")
                session.add(record)
            else:
                record.memory_json = normalized
            session.commit()
        return True
    except Exception as e:
        logger.error("Failed to save user memory to business store: %s", e)
        return False


def load_user_profile_from_business_store(user_id: str) -> str:
    """Load per-user profile markdown from the business store."""

    session_factory = _get_business_session_factory()
    if session_factory is None:
        profile_path = get_paths().user_md_file
        if not profile_path.exists():
            return ""
        return profile_path.read_text(encoding="utf-8")

    with session_factory() as session:
        record = session.get(UserMemoryRecord, user_id)
        if record is None:
            return ""
        return record.user_profile_md or ""


def save_user_profile_to_business_store(user_id: str, profile_markdown: str) -> bool:
    """Persist per-user profile markdown into the business store."""

    session_factory = _get_business_session_factory()
    if session_factory is None:
        try:
            profile_path = get_paths().user_md_file
            profile_path.parent.mkdir(parents=True, exist_ok=True)
            profile_path.write_text(profile_markdown, encoding="utf-8")
            return True
        except Exception as e:
            logger.error("Failed to save user profile to fallback file store: %s", e)
            return False

    try:
        with session_factory() as session:
            record = session.get(UserMemoryRecord, user_id)
            if record is None:
                record = UserMemoryRecord(
                    user_id=user_id,
                    memory_json=create_empty_memory(),
                    user_profile_md=profile_markdown,
                )
                session.add(record)
            else:
                record.user_profile_md = profile_markdown
            session.commit()
        return True
    except Exception as e:
        logger.error("Failed to save user profile to business store: %s", e)
        return False


def get_memory_storage() -> MemoryStorage:
    """Get the configured memory storage instance."""
    global _storage_instance
    if _storage_instance is not None:
        return _storage_instance

    with _storage_lock:
        if _storage_instance is not None:
            return _storage_instance

        config = get_memory_config()
        storage_class_path = config.storage_class

        try:
            module_path, class_name = storage_class_path.rsplit(".", 1)
            import importlib

            module = importlib.import_module(module_path)
            storage_class = getattr(module, class_name)

            # Validate that the configured storage is a MemoryStorage implementation
            if not isinstance(storage_class, type):
                raise TypeError(f"Configured memory storage '{storage_class_path}' is not a class: {storage_class!r}")
            if not issubclass(storage_class, MemoryStorage):
                raise TypeError(f"Configured memory storage '{storage_class_path}' is not a subclass of MemoryStorage")

            _storage_instance = storage_class()
        except Exception as e:
            logger.error(
                "Failed to load memory storage %s, falling back to FileMemoryStorage: %s",
                storage_class_path,
                e,
            )
            _storage_instance = FileMemoryStorage()

    return _storage_instance
