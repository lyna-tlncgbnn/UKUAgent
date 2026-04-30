from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from sqlalchemy import delete, or_, select
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from deerflow.config.app_config import get_app_config

from .models import (
    AgentContentRecord,
    AgentRecord,
    AgentVisibility,
    AssetKind,
    AssetRecord,
    AssetStatus,
    AssetVisibility,
    Base,
    McpAccessRuleRecord,
    ScheduledTaskConcurrencyPolicy,
    ScheduledTaskRecord,
    ScheduledTaskRunRecord,
    ScheduledTaskRunStatus,
    ScheduledTaskScheduleType,
    ScheduledTaskStatus,
    ScheduledTaskThreadPolicy,
    ScheduledTaskTriggerType,
    ThreadFileKind,
    ThreadFileRecord,
    ThreadRecord,
    UserMemoryRecord,
    UserRecord,
    UserRole,
    UserStatus,
)


def _migrate_business_schema(sync_conn) -> None:
    """Apply small additive migrations for deployments using create_all."""

    inspector = inspect(sync_conn)
    table_names = set(inspector.get_table_names())
    if "users" not in table_names:
        return

    user_columns = {column["name"] for column in inspector.get_columns("users")}
    if "wecom_userid" not in user_columns:
        sync_conn.execute(text("ALTER TABLE users ADD COLUMN wecom_userid VARCHAR(255)"))

    index_names = {index["name"] for index in inspector.get_indexes("users")}
    if "ix_users_wecom_userid_unique" not in index_names:
        sync_conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_wecom_userid_unique ON users (wecom_userid)"))


class BusinessStore:
    """Async persistence wrapper for multi-user business metadata."""

    def __init__(self, engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession], auto_create_tables: bool) -> None:
        self.engine = engine
        self.session_factory = session_factory
        self.auto_create_tables = auto_create_tables

    async def setup(self) -> None:
        if not self.auto_create_tables:
            return
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            await conn.run_sync(_migrate_business_schema)

    async def close(self) -> None:
        await self.engine.dispose()

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        async with self.session_factory() as session:
            yield session

    async def upsert_user(
        self,
        user_id: str,
        *,
        email: str | None,
        name: str,
        role: UserRole = UserRole.MEMBER,
        status: UserStatus = UserStatus.ACTIVE,
        wecom_userid: str | None = None,
    ) -> UserRecord:
        async with self.session() as session:
            record = await session.get(UserRecord, user_id)
            if record is None:
                record = UserRecord(id=user_id, email=email, name=name, role=role, status=status, wecom_userid=wecom_userid)
                session.add(record)
            else:
                record.email = email
                record.name = name
                record.role = role
                record.status = status
                if wecom_userid is not None:
                    record.wecom_userid = wecom_userid
            await session.commit()
            await session.refresh(record)
            return record

    async def get_user(self, user_id: str) -> UserRecord | None:
        async with self.session() as session:
            return await session.get(UserRecord, user_id)

    async def get_user_by_wecom_userid(self, wecom_userid: str) -> UserRecord | None:
        async with self.session() as session:
            result = await session.execute(select(UserRecord).where(UserRecord.wecom_userid == wecom_userid))
            return result.scalar_one_or_none()

    async def create_thread(
        self,
        thread_id: str,
        *,
        user_id: str,
        title: str | None = None,
        source: str = "web",
        source_user_id: str | None = None,
    ) -> ThreadRecord:
        async with self.session() as session:
            record = await session.get(ThreadRecord, thread_id)
            if record is None:
                record = ThreadRecord(
                    id=thread_id,
                    user_id=user_id,
                    title=title,
                    source=source,
                    source_user_id=source_user_id,
                )
                session.add(record)
            else:
                record.user_id = user_id
                record.title = title
                record.source = source
                record.source_user_id = source_user_id
            await session.commit()
            await session.refresh(record)
            return record

    async def get_thread(self, thread_id: str) -> ThreadRecord | None:
        async with self.session() as session:
            return await session.get(ThreadRecord, thread_id)

    async def list_threads_for_user(self, user_id: str) -> list[ThreadRecord]:
        async with self.session() as session:
            result = await session.execute(select(ThreadRecord).where(ThreadRecord.user_id == user_id).order_by(ThreadRecord.updated_at.desc()))
            return list(result.scalars().all())

    async def get_thread_for_user_by_source(self, user_id: str, source: str) -> ThreadRecord | None:
        async with self.session() as session:
            result = await session.execute(
                select(ThreadRecord)
                .where(
                    ThreadRecord.user_id == user_id,
                    ThreadRecord.source == source,
                )
                .order_by(ThreadRecord.updated_at.desc())
                .limit(1)
            )
            return result.scalar_one_or_none()

    async def delete_thread(self, thread_id: str, *, user_id: str | None = None) -> bool:
        async with self.session() as session:
            record = await session.get(ThreadRecord, thread_id)
            if record is None:
                return False
            if user_id is not None and record.user_id != user_id:
                return False
            assets_result = await session.execute(select(AssetRecord).where(AssetRecord.thread_id == thread_id))
            now = datetime.now(UTC)
            for asset in assets_result.scalars().all():
                if asset.visibility == AssetVisibility.ORG_SHARED:
                    asset.thread_id = None
                    asset.asset_metadata = {**(asset.asset_metadata or {}), "detached_thread_id": thread_id}
                else:
                    asset.status = AssetStatus.DELETED
                    asset.deleted_at = now
            await session.execute(delete(ThreadFileRecord).where(ThreadFileRecord.thread_id == thread_id))
            await session.delete(record)
            await session.commit()
            return True

    async def delete_thread_files(self, thread_id: str, *, user_id: str | None = None) -> int:
        async with self.session() as session:
            if user_id is not None:
                record = await session.get(ThreadRecord, thread_id)
                if record is None or record.user_id != user_id:
                    return 0
            result = await session.execute(delete(ThreadFileRecord).where(ThreadFileRecord.thread_id == thread_id))
            await session.commit()
            return int(result.rowcount or 0)

    async def record_thread_file(
        self,
        file_id: str,
        *,
        thread_id: str,
        user_id: str,
        kind: ThreadFileKind,
        filename: str,
        storage_path: str,
        mime_type: str | None = None,
        size_bytes: int | None = None,
    ) -> ThreadFileRecord:
        async with self.session() as session:
            record = await session.get(ThreadFileRecord, file_id)
            if record is None:
                record = ThreadFileRecord(
                    id=file_id,
                    thread_id=thread_id,
                    user_id=user_id,
                    kind=kind,
                    filename=filename,
                    storage_path=storage_path,
                    mime_type=mime_type,
                    size_bytes=size_bytes,
                )
                session.add(record)
            else:
                record.thread_id = thread_id
                record.user_id = user_id
                record.kind = kind
                record.filename = filename
                record.storage_path = storage_path
                record.mime_type = mime_type
                record.size_bytes = size_bytes
            await session.commit()
            await session.refresh(record)
            return record

    async def list_thread_files(
        self,
        *,
        thread_id: str,
        kind: ThreadFileKind | None = None,
    ) -> list[ThreadFileRecord]:
        async with self.session() as session:
            stmt = select(ThreadFileRecord).where(ThreadFileRecord.thread_id == thread_id).order_by(ThreadFileRecord.created_at.desc())
            if kind is not None:
                stmt = stmt.where(ThreadFileRecord.kind == kind)
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def delete_thread_file_by_path(
        self,
        *,
        thread_id: str,
        storage_path: str,
    ) -> int:
        async with self.session() as session:
            result = await session.execute(
                delete(ThreadFileRecord).where(
                    ThreadFileRecord.thread_id == thread_id,
                    ThreadFileRecord.storage_path == storage_path,
                )
            )
            await session.commit()
            return int(result.rowcount or 0)

    async def create_asset(
        self,
        asset_id: str,
        *,
        owner_user_id: str,
        filename: str,
        display_name: str | None,
        kind: AssetKind,
        storage_uri: str,
        mime_type: str | None = None,
        size_bytes: int | None = None,
        checksum: str | None = None,
        visibility: AssetVisibility = AssetVisibility.PRIVATE,
        status: AssetStatus = AssetStatus.ACTIVE,
        thread_id: str | None = None,
        run_id: str | None = None,
        task_id: str | None = None,
        agent_id: str | None = None,
        message_id: str | None = None,
        tool_call_id: str | None = None,
        source_asset_id: str | None = None,
        version_group_id: str | None = None,
        version_number: int = 1,
        metadata: dict | None = None,
    ) -> AssetRecord:
        async with self.session() as session:
            record = AssetRecord(
                id=asset_id,
                owner_user_id=owner_user_id,
                filename=filename,
                display_name=display_name or filename,
                kind=kind,
                mime_type=mime_type,
                size_bytes=size_bytes,
                storage_uri=storage_uri,
                checksum=checksum,
                visibility=visibility,
                status=status,
                thread_id=thread_id,
                run_id=run_id,
                task_id=task_id,
                agent_id=agent_id,
                message_id=message_id,
                tool_call_id=tool_call_id,
                source_asset_id=source_asset_id,
                version_group_id=version_group_id or asset_id,
                version_number=version_number,
                asset_metadata=metadata or {},
            )
            session.add(record)
            await session.commit()
            await session.refresh(record)
            return record

    async def upsert_asset_by_storage_uri(
        self,
        asset_id: str,
        *,
        owner_user_id: str,
        filename: str,
        display_name: str | None,
        kind: AssetKind,
        storage_uri: str,
        thread_id: str | None,
        mime_type: str | None = None,
        size_bytes: int | None = None,
        checksum: str | None = None,
        run_id: str | None = None,
        task_id: str | None = None,
        agent_id: str | None = None,
        message_id: str | None = None,
        tool_call_id: str | None = None,
        source_asset_id: str | None = None,
        metadata: dict | None = None,
    ) -> AssetRecord:
        async with self.session() as session:
            stmt = select(AssetRecord).where(
                AssetRecord.thread_id == thread_id,
                AssetRecord.storage_uri == storage_uri,
            )
            result = await session.execute(stmt)
            record = result.scalar_one_or_none()
            if record is None:
                record = AssetRecord(
                    id=asset_id,
                    owner_user_id=owner_user_id,
                    filename=filename,
                    display_name=display_name or filename,
                    kind=kind,
                    mime_type=mime_type,
                    size_bytes=size_bytes,
                    storage_uri=storage_uri,
                    checksum=checksum,
                    thread_id=thread_id,
                    run_id=run_id,
                    task_id=task_id,
                    agent_id=agent_id,
                    message_id=message_id,
                    tool_call_id=tool_call_id,
                    source_asset_id=source_asset_id,
                    version_group_id=asset_id,
                    version_number=1,
                    asset_metadata=metadata or {},
                )
                session.add(record)
            else:
                record.mime_type = record.mime_type or mime_type
                record.size_bytes = record.size_bytes or size_bytes
                record.checksum = record.checksum or checksum
                record.run_id = record.run_id or run_id
                record.task_id = record.task_id or task_id
                record.agent_id = record.agent_id or agent_id
                record.message_id = record.message_id or message_id
                record.tool_call_id = record.tool_call_id or tool_call_id
                record.source_asset_id = record.source_asset_id or source_asset_id
                if metadata:
                    record.asset_metadata = {**(record.asset_metadata or {}), **metadata}
            await session.commit()
            await session.refresh(record)
            return record

    async def get_asset(self, asset_id: str) -> AssetRecord | None:
        async with self.session() as session:
            return await session.get(AssetRecord, asset_id)

    async def list_assets(
        self,
        *,
        owner_user_id: str | None = None,
        visibility: AssetVisibility | None = None,
        status: AssetStatus | None = AssetStatus.ACTIVE,
        thread_id: str | None = None,
        task_id: str | None = None,
        kind: AssetKind | None = None,
        q: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[AssetRecord]:
        async with self.session() as session:
            stmt = select(AssetRecord)
            if owner_user_id is not None:
                stmt = stmt.where(AssetRecord.owner_user_id == owner_user_id)
            if visibility is not None:
                stmt = stmt.where(AssetRecord.visibility == visibility)
            if status is not None:
                stmt = stmt.where(AssetRecord.status == status)
            if thread_id is not None:
                stmt = stmt.where(AssetRecord.thread_id == thread_id)
            if task_id is not None:
                stmt = stmt.where(AssetRecord.task_id == task_id)
            if kind is not None:
                stmt = stmt.where(AssetRecord.kind == kind)
            if q:
                pattern = f"%{q}%"
                stmt = stmt.where(or_(AssetRecord.filename.like(pattern), AssetRecord.display_name.like(pattern)))
            stmt = stmt.order_by(AssetRecord.created_at.desc(), AssetRecord.id.desc()).offset(offset).limit(limit)
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def update_asset(
        self,
        asset_id: str,
        *,
        display_name: str | None = None,
        visibility: AssetVisibility | None = None,
        status: AssetStatus | None = None,
        deleted_at: datetime | None = None,
        metadata: dict | None = None,
        clear_task_id: bool = False,
    ) -> AssetRecord | None:
        async with self.session() as session:
            record = await session.get(AssetRecord, asset_id)
            if record is None:
                return None
            if display_name is not None:
                record.display_name = display_name
            if visibility is not None:
                record.visibility = visibility
            if status is not None:
                record.status = status
                if status != AssetStatus.DELETED:
                    record.deleted_at = None
            if deleted_at is not None:
                record.deleted_at = deleted_at
            if clear_task_id:
                record.task_id = None
            if metadata is not None:
                record.asset_metadata = {**(record.asset_metadata or {}), **metadata}
            await session.commit()
            await session.refresh(record)
            return record

    async def soft_delete_asset(self, asset_id: str) -> AssetRecord | None:
        return await self.update_asset(
            asset_id,
            status=AssetStatus.DELETED,
            deleted_at=datetime.now(UTC),
        )

    async def soft_delete_private_assets_for_thread(self, thread_id: str, *, user_id: str | None = None) -> int:
        async with self.session() as session:
            stmt = select(AssetRecord).where(
                AssetRecord.thread_id == thread_id,
                AssetRecord.visibility != AssetVisibility.ORG_SHARED,
                AssetRecord.status != AssetStatus.DELETED,
            )
            if user_id is not None:
                stmt = stmt.where(AssetRecord.owner_user_id == user_id)
            result = await session.execute(stmt)
            records = list(result.scalars().all())
            now = datetime.now(UTC)
            for record in records:
                record.status = AssetStatus.DELETED
                record.deleted_at = now
            await session.commit()
            return len(records)

    async def detach_shared_assets_for_task(self, task_id: str, *, user_id: str | None = None) -> int:
        async with self.session() as session:
            stmt = select(AssetRecord).where(
                AssetRecord.task_id == task_id,
                AssetRecord.visibility == AssetVisibility.ORG_SHARED,
            )
            if user_id is not None:
                stmt = stmt.where(AssetRecord.owner_user_id == user_id)
            result = await session.execute(stmt)
            records = list(result.scalars().all())
            for record in records:
                record.task_id = None
                record.asset_metadata = {**(record.asset_metadata or {}), "detached_task_id": task_id}
            await session.commit()
            return len(records)

    async def soft_delete_private_assets_for_task(self, task_id: str, *, user_id: str | None = None) -> int:
        async with self.session() as session:
            stmt = select(AssetRecord).where(
                AssetRecord.task_id == task_id,
                AssetRecord.visibility != AssetVisibility.ORG_SHARED,
                AssetRecord.status != AssetStatus.DELETED,
            )
            if user_id is not None:
                stmt = stmt.where(AssetRecord.owner_user_id == user_id)
            result = await session.execute(stmt)
            records = list(result.scalars().all())
            now = datetime.now(UTC)
            for record in records:
                record.status = AssetStatus.DELETED
                record.deleted_at = now
            await session.commit()
            return len(records)

    async def get_user_memory(self, user_id: str) -> UserMemoryRecord | None:
        async with self.session() as session:
            return await session.get(UserMemoryRecord, user_id)

    async def upsert_user_memory(self, user_id: str, *, memory_json: dict, user_profile_md: str) -> UserMemoryRecord:
        async with self.session() as session:
            record = await session.get(UserMemoryRecord, user_id)
            if record is None:
                record = UserMemoryRecord(user_id=user_id, memory_json=memory_json, user_profile_md=user_profile_md)
                session.add(record)
            else:
                record.memory_json = memory_json
                record.user_profile_md = user_profile_md
            await session.commit()
            await session.refresh(record)
            return record

    async def create_agent(
        self,
        agent_id: str,
        *,
        owner_user_id: str,
        name: str,
        slug: str,
        description: str | None,
        model: str | None,
        tool_groups: list[str],
        visibility: AgentVisibility,
        soul_md: str,
        config_json: dict,
        memory_json: dict | None = None,
    ) -> AgentRecord:
        async with self.session() as session:
            record = await session.get(AgentRecord, agent_id)
            if record is None:
                record = AgentRecord(
                    id=agent_id,
                    owner_user_id=owner_user_id,
                    name=name,
                    slug=slug,
                    description=description,
                    model=model,
                    tool_groups=tool_groups,
                    visibility=visibility,
                )
                session.add(record)
            else:
                record.owner_user_id = owner_user_id
                record.name = name
                record.slug = slug
                record.description = description
                record.model = model
                record.tool_groups = tool_groups
                record.visibility = visibility

            content = await session.get(AgentContentRecord, agent_id)
            if content is None:
                content = AgentContentRecord(agent_id=agent_id, soul_md=soul_md, config_json=config_json, memory_json=memory_json)
                session.add(content)
            else:
                content.soul_md = soul_md
                content.config_json = config_json
                content.memory_json = memory_json

            await session.commit()
            await session.refresh(record)
            return record

    async def get_agent_by_slug(self, slug: str) -> AgentRecord | None:
        async with self.session() as session:
            result = await session.execute(select(AgentRecord).where(AgentRecord.slug == slug))
            return result.scalar_one_or_none()

    async def list_accessible_agents(self, user_id: str) -> list[AgentRecord]:
        async with self.session() as session:
            result = await session.execute(
                select(AgentRecord)
                .where(or_(AgentRecord.owner_user_id == user_id, AgentRecord.visibility == AgentVisibility.ORG_SHARED))
                .order_by(AgentRecord.updated_at.desc())
            )
            return list(result.scalars().all())

    async def upsert_mcp_rule(
        self,
        rule_id: str,
        *,
        server_name: str,
        scope_type,
        scope_value: str | None,
        enabled: bool,
    ) -> McpAccessRuleRecord:
        async with self.session() as session:
            record = await session.get(McpAccessRuleRecord, rule_id)
            if record is None:
                record = McpAccessRuleRecord(
                    id=rule_id,
                    server_name=server_name,
                    scope_type=scope_type,
                    scope_value=scope_value,
                    enabled=enabled,
                )
                session.add(record)
            else:
                record.server_name = server_name
                record.scope_type = scope_type
                record.scope_value = scope_value
                record.enabled = enabled
            await session.commit()
            await session.refresh(record)
            return record

    async def create_scheduled_task(
        self,
        task_id: str,
        *,
        user_id: str,
        title: str,
        description: str | None,
        assistant_id: str,
        prompt: str,
        schedule_type: ScheduledTaskScheduleType,
        timezone: str,
        cron_expr: str | None,
        interval_seconds: int | None,
        run_at: datetime | None,
        next_run_at: datetime | None,
        status: ScheduledTaskStatus = ScheduledTaskStatus.ACTIVE,
        concurrency_policy: ScheduledTaskConcurrencyPolicy = ScheduledTaskConcurrencyPolicy.SKIP,
        thread_policy: ScheduledTaskThreadPolicy = ScheduledTaskThreadPolicy.NEW_THREAD_EACH_RUN,
        thread_id: str | None = None,
        metadata: dict | None = None,
    ) -> ScheduledTaskRecord:
        async with self.session() as session:
            record = ScheduledTaskRecord(
                id=task_id,
                user_id=user_id,
                title=title,
                description=description,
                assistant_id=assistant_id,
                prompt=prompt,
                schedule_type=schedule_type,
                timezone=timezone,
                cron_expr=cron_expr,
                interval_seconds=interval_seconds,
                run_at=run_at,
                next_run_at=next_run_at,
                status=status,
                concurrency_policy=concurrency_policy,
                thread_policy=thread_policy,
                thread_id=thread_id,
                task_metadata=metadata or {},
            )
            session.add(record)
            await session.commit()
            await session.refresh(record)
            return record

    async def get_scheduled_task(self, task_id: str) -> ScheduledTaskRecord | None:
        async with self.session() as session:
            return await session.get(ScheduledTaskRecord, task_id)

    async def get_scheduled_task_for_user(self, task_id: str, user_id: str) -> ScheduledTaskRecord | None:
        async with self.session() as session:
            result = await session.execute(
                select(ScheduledTaskRecord).where(
                    ScheduledTaskRecord.id == task_id,
                    ScheduledTaskRecord.user_id == user_id,
                )
            )
            return result.scalar_one_or_none()

    async def list_scheduled_tasks_for_user(self, user_id: str) -> list[ScheduledTaskRecord]:
        async with self.session() as session:
            result = await session.execute(
                select(ScheduledTaskRecord)
                .where(ScheduledTaskRecord.user_id == user_id)
                .order_by(ScheduledTaskRecord.updated_at.desc())
            )
            return list(result.scalars().all())

    async def update_scheduled_task(
        self,
        task_id: str,
        *,
        user_id: str | None = None,
        **fields,
    ) -> ScheduledTaskRecord | None:
        async with self.session() as session:
            record = await session.get(ScheduledTaskRecord, task_id)
            if record is None:
                return None
            if user_id is not None and record.user_id != user_id:
                return None
            for key, value in fields.items():
                if key == "metadata":
                    key = "task_metadata"
                if hasattr(ScheduledTaskRecord, key):
                    setattr(record, key, value)
            await session.commit()
            await session.refresh(record)
            return record

    async def delete_scheduled_task(self, task_id: str, *, user_id: str) -> bool:
        async with self.session() as session:
            record = await session.get(ScheduledTaskRecord, task_id)
            if record is None or record.user_id != user_id:
                return False
            await session.execute(
                delete(ScheduledTaskRunRecord).where(
                    ScheduledTaskRunRecord.task_id == task_id,
                    ScheduledTaskRunRecord.user_id == user_id,
                )
            )
            await session.delete(record)
            await session.commit()
            return True

    async def list_due_scheduled_tasks(
        self,
        now: datetime,
        *,
        limit: int = 25,
    ) -> list[ScheduledTaskRecord]:
        async with self.session() as session:
            result = await session.execute(
                select(ScheduledTaskRecord)
                .where(
                    ScheduledTaskRecord.status == ScheduledTaskStatus.ACTIVE,
                    ScheduledTaskRecord.next_run_at.is_not(None),
                    ScheduledTaskRecord.next_run_at <= now,
                    or_(ScheduledTaskRecord.locked_until.is_(None), ScheduledTaskRecord.locked_until <= now),
                )
                .order_by(ScheduledTaskRecord.next_run_at.asc())
                .limit(limit)
            )
            return list(result.scalars().all())

    async def has_running_scheduled_task_run(self, task_id: str) -> bool:
        async with self.session() as session:
            result = await session.execute(
                select(ScheduledTaskRunRecord.id)
                .where(
                    ScheduledTaskRunRecord.task_id == task_id,
                    ScheduledTaskRunRecord.status.in_(
                        [
                            ScheduledTaskRunStatus.QUEUED,
                            ScheduledTaskRunStatus.RUNNING,
                        ]
                    ),
                )
                .limit(1)
            )
            return result.scalar_one_or_none() is not None

    async def create_scheduled_task_run(
        self,
        run_record_id: str,
        *,
        task_id: str,
        user_id: str,
        thread_id: str | None,
        run_id: str | None,
        scheduled_for: datetime | None,
        started_at: datetime | None,
        finished_at: datetime | None = None,
        status: ScheduledTaskRunStatus = ScheduledTaskRunStatus.QUEUED,
        trigger_type: ScheduledTaskTriggerType = ScheduledTaskTriggerType.SCHEDULE,
        error: str | None = None,
        result_summary: str | None = None,
    ) -> ScheduledTaskRunRecord:
        async with self.session() as session:
            record = ScheduledTaskRunRecord(
                id=run_record_id,
                task_id=task_id,
                user_id=user_id,
                thread_id=thread_id,
                run_id=run_id,
                scheduled_for=scheduled_for,
                started_at=started_at,
                finished_at=finished_at,
                status=status,
                trigger_type=trigger_type,
                error=error,
                result_summary=result_summary,
            )
            session.add(record)
            await session.commit()
            await session.refresh(record)
            return record

    async def update_scheduled_task_run(
        self,
        run_record_id: str,
        *,
        user_id: str | None = None,
        **fields,
    ) -> ScheduledTaskRunRecord | None:
        async with self.session() as session:
            record = await session.get(ScheduledTaskRunRecord, run_record_id)
            if record is None:
                return None
            if user_id is not None and record.user_id != user_id:
                return None
            for key, value in fields.items():
                if hasattr(ScheduledTaskRunRecord, key):
                    setattr(record, key, value)
            await session.commit()
            await session.refresh(record)
            return record

    async def list_scheduled_task_runs(
        self,
        *,
        task_id: str,
        user_id: str,
    ) -> list[ScheduledTaskRunRecord]:
        async with self.session() as session:
            result = await session.execute(
                select(ScheduledTaskRunRecord)
                .where(
                    ScheduledTaskRunRecord.task_id == task_id,
                    ScheduledTaskRunRecord.user_id == user_id,
                )
                .order_by(ScheduledTaskRunRecord.created_at.desc())
            )
            return list(result.scalars().all())

    async def get_scheduled_task_run_for_user(
        self,
        run_record_id: str,
        *,
        task_id: str,
        user_id: str,
    ) -> ScheduledTaskRunRecord | None:
        async with self.session() as session:
            result = await session.execute(
                select(ScheduledTaskRunRecord).where(
                    ScheduledTaskRunRecord.id == run_record_id,
                    ScheduledTaskRunRecord.task_id == task_id,
                    ScheduledTaskRunRecord.user_id == user_id,
                )
            )
            return result.scalar_one_or_none()


@asynccontextmanager
async def create_business_store() -> AsyncIterator[BusinessStore | None]:
    """Create the optional business metadata store configured for the app."""

    config = get_app_config().business_storage
    if not config.enabled:
        yield None
        return

    engine = create_async_engine(config.connection_string, echo=config.echo)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    store = BusinessStore(engine=engine, session_factory=session_factory, auto_create_tables=config.auto_create_tables)
    await store.setup()
    try:
        yield store
    finally:
        await store.close()
