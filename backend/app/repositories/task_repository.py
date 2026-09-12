from __future__ import annotations

import builtins

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.record_access import record_access_filter
from app.models.support import Ticket
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
        search: str | None = None,
        lead_id: str | None = None,
        contact_id: str | None = None,
        company_id: str | None = None,
        deal_id: str | None = None,
        project_id: str | None = None,
        ticket_id: str | None = None,
        project_linked: bool = False,
        access=None,
    ) -> builtins.list[Task]:
        stmt = select(Task).where(Task.organization_id == organization_id)
        access_filter = record_access_filter(
            access, assigned_column=Task.assigned_to, created_column=Task.created_by
        )
        if access_filter is not None:
            stmt = stmt.where(access_filter)
        if status:
            stmt = stmt.where(Task.status == status)
        if priority:
            stmt = stmt.where(Task.priority == priority)
        for column, value in (
            (Task.lead_id, lead_id),
            (Task.contact_id, contact_id),
            (Task.company_id, company_id),
            (Task.deal_id, deal_id),
            (Task.project_id, project_id),
            (Task.ticket_id, ticket_id),
        ):
            if value:
                stmt = stmt.where(column == value)
        if project_linked and not project_id:
            stmt = stmt.where(Task.project_id.is_not(None))
        if search and search.strip():
            pattern = f"%{search.strip()}%"
            stmt = stmt.where(Task.title.ilike(pattern) | Task.description.ilike(pattern))
        stmt = (
            stmt.order_by(Task.created_at.desc(), Task.id.desc())
            .offset((page - 1) * limit)
            .limit(limit)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def count(
        self,
        db: AsyncSession,
        *,
        organization_id: str,
        status: str | None = None,
        priority: str | None = None,
        search: str | None = None,
        lead_id: str | None = None,
        contact_id: str | None = None,
        company_id: str | None = None,
        deal_id: str | None = None,
        project_id: str | None = None,
        ticket_id: str | None = None,
        project_linked: bool = False,
        access=None,
    ) -> int:
        stmt = select(func.count()).select_from(Task).where(Task.organization_id == organization_id)
        access_filter = record_access_filter(
            access, assigned_column=Task.assigned_to, created_column=Task.created_by
        )
        if access_filter is not None:
            stmt = stmt.where(access_filter)
        if status:
            stmt = stmt.where(Task.status == status)
        if priority:
            stmt = stmt.where(Task.priority == priority)
        for column, value in (
            (Task.lead_id, lead_id),
            (Task.contact_id, contact_id),
            (Task.company_id, company_id),
            (Task.deal_id, deal_id),
            (Task.project_id, project_id),
            (Task.ticket_id, ticket_id),
        ):
            if value:
                stmt = stmt.where(column == value)
        if project_linked and not project_id:
            stmt = stmt.where(Task.project_id.is_not(None))
        if search and search.strip():
            pattern = f"%{search.strip()}%"
            stmt = stmt.where(Task.title.ilike(pattern) | Task.description.ilike(pattern))
        result = await db.execute(stmt)
        return int(result.scalar_one())

    async def list_pending(
        self, db: AsyncSession, *, organization_id: str, access=None
    ) -> builtins.list[Task]:
        filters = [Task.organization_id == organization_id, Task.status == "Pending"]
        access_filter = record_access_filter(
            access, assigned_column=Task.assigned_to, created_column=Task.created_by
        )
        if access_filter is not None:
            filters.append(access_filter)
        result = await db.execute(select(Task).where(*filters))
        return list(result.scalars().all())

    async def list_all(
        self, db: AsyncSession, *, organization_id: str, access=None
    ) -> builtins.list[Task]:
        filters = [Task.organization_id == organization_id]
        access_filter = record_access_filter(
            access, assigned_column=Task.assigned_to, created_column=Task.created_by
        )
        if access_filter is not None:
            filters.append(access_filter)
        result = await db.execute(select(Task).where(*filters))
        return list(result.scalars().all())

    async def get_by_id(
        self, db: AsyncSession, *, task_id: str, organization_id: str, access=None
    ) -> Task | None:
        filters = [Task.id == task_id, Task.organization_id == organization_id]
        access_filter = record_access_filter(
            access, assigned_column=Task.assigned_to, created_column=Task.created_by
        )
        if access_filter is not None:
            filters.append(access_filter)
        result = await db.execute(select(Task).where(*filters))
        return result.scalars().first()

    async def list_by_ids(
        self,
        db: AsyncSession,
        *,
        ids: builtins.list[str],
        organization_id: str,
        access=None,
    ) -> builtins.list[Task]:
        filters = [Task.id.in_(ids), Task.organization_id == organization_id]
        access_filter = record_access_filter(
            access, assigned_column=Task.assigned_to, created_column=Task.created_by
        )
        if access_filter is not None:
            filters.append(access_filter)
        result = await db.execute(select(Task).where(*filters))
        return list(result.scalars().all())

    async def create(self, db: AsyncSession, *, data: dict) -> Task:
        task = Task(**data)
        db.add(task)
        return task

    async def validate_ticket(
        self, db: AsyncSession, ticket_id: str | None, organization_id: str
    ) -> str | None:
        if not ticket_id:
            return None
        ticket = await db.scalar(
            select(Ticket).where(
                Ticket.id == ticket_id,
                Ticket.organization_id == organization_id,
                Ticket.is_archived.is_(False),
            )
        )
        if not ticket:
            from app.core.errors import NotFoundError

            raise NotFoundError(message=f"Ticket '{ticket_id}' not found")
        return ticket.id

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
