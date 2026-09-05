from __future__ import annotations

import builtins

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task import Task
from app.models.user import User


class TaskRepository:
    """DB query layer for the Task entity. No business logic here."""

    async def list(
        self,
        db: AsyncSession,
        *,
        page: int,
        limit: int,
        organization_id: str,
        status: str | None = None,
        priority: str | None = None,
    ) -> builtins.list[Task]:
        stmt = (
            select(Task)
            .where(Task.organization_id == organization_id)
            .offset((page - 1) * limit)
            .limit(limit)
        )
        if status:
            stmt = stmt.where(Task.status == status)
        if priority:
            stmt = stmt.where(Task.priority == priority)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def list_pending(self, db: AsyncSession, *, organization_id: str) -> builtins.list[Task]:
        result = await db.execute(
            select(Task).where(
                Task.organization_id == organization_id,
                Task.status == "Pending",
            )
        )
        return list(result.scalars().all())

    async def list_all(self, db: AsyncSession, *, organization_id: str) -> builtins.list[Task]:
        result = await db.execute(select(Task).where(Task.organization_id == organization_id))
        return list(result.scalars().all())

    async def get_by_id(
        self, db: AsyncSession, *, task_id: str, organization_id: str
    ) -> Task | None:
        result = await db.execute(
            select(Task).where(
                Task.id == task_id,
                Task.organization_id == organization_id,
            )
        )
        return result.scalars().first()

    async def list_by_ids(
        self, db: AsyncSession, *, ids: builtins.list[str], organization_id: str
    ) -> builtins.list[Task]:
        result = await db.execute(
            select(Task).where(
                Task.id.in_(ids),
                Task.organization_id == organization_id,
            )
        )
        return list(result.scalars().all())

    async def create(self, db: AsyncSession, *, data: dict) -> Task:
        task = Task(**data)
        db.add(task)
        return task

    async def delete(self, db: AsyncSession, task: Task) -> None:
        await db.delete(task)

    async def get_user_by_id_name_email(
        self, db: AsyncSession, *, value: str, organization_id: str
    ) -> User | None:
        result = await db.execute(
            select(User).where(
                User.organization_id == organization_id,
                (User.id == value) | (User.name.ilike(value)) | (User.email.ilike(value)),
            )
        )
        return result.scalars().first()
