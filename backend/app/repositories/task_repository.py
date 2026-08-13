from typing import Optional

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
        status: Optional[str] = None,
        priority: Optional[str] = None,
    ) -> list[Task]:
        stmt = select(Task).offset((page - 1) * limit).limit(limit)
        if status:
            stmt = stmt.where(Task.status == status)
        if priority:
            stmt = stmt.where(Task.priority == priority)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def list_pending(self, db: AsyncSession) -> list[Task]:
        result = await db.execute(select(Task).where(Task.status == "Pending"))
        return list(result.scalars().all())

    async def list_all(self, db: AsyncSession) -> list[Task]:
        result = await db.execute(select(Task))
        return list(result.scalars().all())

    async def get_by_id(self, db: AsyncSession, task_id: str) -> Optional[Task]:
        result = await db.execute(select(Task).where(Task.id == task_id))
        return result.scalars().first()

    async def list_by_ids(self, db: AsyncSession, ids: list[str]) -> list[Task]:
        result = await db.execute(select(Task).where(Task.id.in_(ids)))
        return list(result.scalars().all())

    async def create(self, db: AsyncSession, *, data: dict) -> Task:
        task = Task(**data)
        db.add(task)
        return task

    async def delete(self, db: AsyncSession, task: Task) -> None:
        await db.delete(task)

    async def get_user_by_id_name_email(
        self, db: AsyncSession, value: str
    ) -> Optional[User]:
        result = await db.execute(
            select(User).where(
                (User.id == value) | (User.name.ilike(value)) | (User.email.ilike(value))
            )
        )
        return result.scalars().first()

    async def get_first_user(self, db: AsyncSession) -> Optional[User]:
        result = await db.execute(select(User).limit(1))
        return result.scalars().first()

    async def create_system_user(self, db: AsyncSession) -> User:
        user = User(
            id="usr-system",
            name="System Admin",
            email="system@crm.com",
            hashed_password="hashed_default",
            role="Admin",
            organization_id="org-1",
        )
        db.add(user)
        await db.flush()
        return user