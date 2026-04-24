from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for business persistence models."""


class UserRole(str, enum.Enum):
    MEMBER = "member"
    ADMIN = "admin"


class UserStatus(str, enum.Enum):
    ACTIVE = "active"
    DISABLED = "disabled"


class ThreadFileKind(str, enum.Enum):
    UPLOAD = "upload"
    OUTPUT = "output"
    ARTIFACT = "artifact"


class AgentVisibility(str, enum.Enum):
    PRIVATE = "private"
    ORG_SHARED = "org_shared"


class McpScopeType(str, enum.Enum):
    GLOBAL = "global"
    ROLE = "role"


class UserRecord(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    email: Mapped[str | None] = mapped_column(String(320), unique=True, nullable=True)
    name: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.MEMBER, nullable=False)
    status: Mapped[UserStatus] = mapped_column(Enum(UserStatus), default=UserStatus.ACTIVE, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    threads: Mapped[list[ThreadRecord]] = relationship(back_populates="user", cascade="all, delete-orphan")
    memory: Mapped[UserMemoryRecord | None] = relationship(back_populates="user", cascade="all, delete-orphan", uselist=False)
    owned_agents: Mapped[list[AgentRecord]] = relationship(back_populates="owner", cascade="all, delete-orphan")


class ThreadRecord(Base):
    __tablename__ = "threads"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(32), default="web", nullable=False)
    source_user_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    user: Mapped[UserRecord] = relationship(back_populates="threads")
    files: Mapped[list[ThreadFileRecord]] = relationship(back_populates="thread", cascade="all, delete-orphan")


class ThreadFileRecord(Base):
    __tablename__ = "thread_files"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    thread_id: Mapped[str] = mapped_column(ForeignKey("threads.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    kind: Mapped[ThreadFileKind] = mapped_column(Enum(ThreadFileKind), nullable=False)
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    mime_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    thread: Mapped[ThreadRecord] = relationship(back_populates="files")


class UserMemoryRecord(Base):
    __tablename__ = "user_memory"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    memory_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    user_profile_md: Mapped[str] = mapped_column(Text, default="", nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    user: Mapped[UserRecord] = relationship(back_populates="memory")


class AgentRecord(Base):
    __tablename__ = "agents"
    __table_args__ = (UniqueConstraint("slug", name="uq_agents_slug"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    owner_user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    model: Mapped[str | None] = mapped_column(String(255), nullable=True)
    tool_groups: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    visibility: Mapped[AgentVisibility] = mapped_column(Enum(AgentVisibility), default=AgentVisibility.PRIVATE, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    owner: Mapped[UserRecord] = relationship(back_populates="owned_agents")
    content: Mapped[AgentContentRecord | None] = relationship(back_populates="agent", cascade="all, delete-orphan", uselist=False)


class AgentContentRecord(Base):
    __tablename__ = "agent_content"

    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), primary_key=True)
    soul_md: Mapped[str] = mapped_column(Text, default="", nullable=False)
    config_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    memory_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    agent: Mapped[AgentRecord] = relationship(back_populates="content")


class McpAccessRuleRecord(Base):
    __tablename__ = "mcp_access_rules"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    server_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    scope_type: Mapped[McpScopeType] = mapped_column(Enum(McpScopeType), nullable=False)
    scope_value: Mapped[str | None] = mapped_column(String(255), nullable=True)
    enabled: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
