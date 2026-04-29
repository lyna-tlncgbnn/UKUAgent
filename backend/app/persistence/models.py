from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint, func
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


class ScheduledTaskScheduleType(str, enum.Enum):
    ONCE = "once"
    INTERVAL = "interval"
    CRON = "cron"


class ScheduledTaskStatus(str, enum.Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    DISABLED = "disabled"


class ScheduledTaskConcurrencyPolicy(str, enum.Enum):
    SKIP = "skip"
    INTERRUPT = "interrupt"
    ENQUEUE = "enqueue"


class ScheduledTaskThreadPolicy(str, enum.Enum):
    NEW_THREAD_EACH_RUN = "new_thread_each_run"
    REUSE_THREAD = "reuse_thread"


class ScheduledTaskRunStatus(str, enum.Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCESS = "success"
    ERROR = "error"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


class ScheduledTaskTriggerType(str, enum.Enum):
    SCHEDULE = "schedule"
    MANUAL = "manual"
    CONVERSATION = "conversation"


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
    scheduled_tasks: Mapped[list[ScheduledTaskRecord]] = relationship(back_populates="user", cascade="all, delete-orphan")


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


class ScheduledTaskRecord(Base):
    __tablename__ = "scheduled_tasks"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    assistant_id: Mapped[str] = mapped_column(String(255), default="lead_agent", nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)

    schedule_type: Mapped[ScheduledTaskScheduleType] = mapped_column(Enum(ScheduledTaskScheduleType), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Shanghai", nullable=False)
    cron_expr: Mapped[str | None] = mapped_column(String(255), nullable=True)
    interval_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)

    status: Mapped[ScheduledTaskStatus] = mapped_column(Enum(ScheduledTaskStatus), default=ScheduledTaskStatus.ACTIVE, nullable=False, index=True)
    concurrency_policy: Mapped[ScheduledTaskConcurrencyPolicy] = mapped_column(
        Enum(ScheduledTaskConcurrencyPolicy),
        default=ScheduledTaskConcurrencyPolicy.SKIP,
        nullable=False,
    )
    thread_policy: Mapped[ScheduledTaskThreadPolicy] = mapped_column(
        Enum(ScheduledTaskThreadPolicy),
        default=ScheduledTaskThreadPolicy.NEW_THREAD_EACH_RUN,
        nullable=False,
    )
    thread_id: Mapped[str | None] = mapped_column(ForeignKey("threads.id", ondelete="SET NULL"), nullable=True, index=True)

    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    failure_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    locked_by: Mapped[str | None] = mapped_column(String(255), nullable=True)

    task_metadata: Mapped[dict] = mapped_column("metadata", JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    user: Mapped[UserRecord] = relationship(back_populates="scheduled_tasks")
    runs: Mapped[list[ScheduledTaskRunRecord]] = relationship(back_populates="task", cascade="all, delete-orphan")


class ScheduledTaskRunRecord(Base):
    __tablename__ = "scheduled_task_runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    task_id: Mapped[str] = mapped_column(ForeignKey("scheduled_tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    thread_id: Mapped[str | None] = mapped_column(ForeignKey("threads.id", ondelete="SET NULL"), nullable=True, index=True)
    run_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    scheduled_for: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    status: Mapped[ScheduledTaskRunStatus] = mapped_column(Enum(ScheduledTaskRunStatus), default=ScheduledTaskRunStatus.QUEUED, nullable=False, index=True)
    trigger_type: Mapped[ScheduledTaskTriggerType] = mapped_column(Enum(ScheduledTaskTriggerType), default=ScheduledTaskTriggerType.SCHEDULE, nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    task: Mapped[ScheduledTaskRecord] = relationship(back_populates="runs")
