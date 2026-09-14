from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Company,
    Contact,
    Deal,
    Project,
    ProjectMember,
    ProjectMilestone,
    ProjectStakeholder,
    Task,
    User,
)
from app.repositories.project_access import project_record_access_filter


class ProjectRepository:
    async def list(
        self,
        db: AsyncSession,
        *,
        organization_id: str,
        page: int = 1,
        limit: int = 20,
        status: str | None = None,
        priority: str | None = None,
        search: str | None = None,
        access=None,
    ) -> list[Project]:
        conditions = [Project.organization_id == organization_id]
        access_filter = project_record_access_filter(access)
        if access_filter is not None:
            conditions.append(access_filter)
        if status:
            conditions.append(Project.status == status)
        if priority:
            conditions.append(Project.priority == priority)
        if search and search.strip():
            conditions.append(Project.name.ilike(f"%{search.strip()}%"))
        result = await db.execute(
            select(Project)
            .where(*conditions)
            .order_by(Project.created_at.desc(), Project.id.desc())
            .offset(max(page - 1, 0) * limit)
            .limit(min(limit, 100))
        )
        return list(result.scalars().all())

    async def count(
        self,
        db: AsyncSession,
        *,
        organization_id: str,
        status: str | None = None,
        priority: str | None = None,
        search: str | None = None,
        access=None,
    ) -> int:
        conditions = [Project.organization_id == organization_id]
        access_filter = project_record_access_filter(access)
        if access_filter is not None:
            conditions.append(access_filter)
        if status:
            conditions.append(Project.status == status)
        if priority:
            conditions.append(Project.priority == priority)
        if search and search.strip():
            conditions.append(Project.name.ilike(f"%{search.strip()}%"))
        result = await db.execute(select(func.count()).select_from(Project).where(*conditions))
        return int(result.scalar_one())

    async def get(
        self, db: AsyncSession, *, project_id: str, organization_id: str, access=None
    ) -> Project | None:
        conditions = [Project.id == project_id, Project.organization_id == organization_id]
        access_filter = project_record_access_filter(access)
        if access_filter is not None:
            conditions.append(access_filter)
        result = await db.execute(select(Project).where(*conditions))
        return result.scalars().first()

    async def create(self, db: AsyncSession, data: dict) -> Project:
        project = Project(**data)
        db.add(project)
        return project

    async def get_user_in_organization(
        self, db: AsyncSession, *, user_id: str, organization_id: str
    ) -> User | None:
        result = await db.execute(
            select(User).where(
                User.id == user_id,
                User.organization_id == organization_id,
                User.is_active.is_(True),
            )
        )
        return result.scalars().first()

    async def update(self, db: AsyncSession, project: Project, updates: dict) -> Project:
        for field, value in updates.items():
            setattr(project, field, value)
        return project

    async def delete(self, db: AsyncSession, project: Project) -> None:
        await db.delete(project)

    async def validate_related(
        self,
        db: AsyncSession,
        *,
        organization_id: str,
        company_id: str | None = None,
        contact_id: str | None = None,
        originating_deal_id: str | None = None,
    ) -> str | None:
        for label, model, value in (
            ("company", Company, company_id),
            ("contact", Contact, contact_id),
            ("originating deal", Deal, originating_deal_id),
        ):
            if value and not await db.scalar(
                select(model.id).where(model.id == value, model.organization_id == organization_id)
            ):
                return label
        return None

    async def list_stakeholders(self, db: AsyncSession, project_id: str):
        return list(
            (
                await db.scalars(
                    select(ProjectStakeholder)
                    .where(ProjectStakeholder.project_id == project_id)
                    .order_by(ProjectStakeholder.role)
                )
            ).all()
        )

    async def get_stakeholder(self, db: AsyncSession, project_id: str, stakeholder_id: str):
        return await db.scalar(
            select(ProjectStakeholder).where(
                ProjectStakeholder.id == stakeholder_id, ProjectStakeholder.project_id == project_id
            )
        )

    async def list_members(self, db: AsyncSession, project_id: str) -> list[ProjectMember]:
        return list(
            (
                await db.scalars(
                    select(ProjectMember)
                    .where(ProjectMember.project_id == project_id)
                    .order_by(ProjectMember.created_at, ProjectMember.id)
                )
            ).all()
        )

    async def get_member(
        self, db: AsyncSession, project_id: str, user_id: str
    ) -> ProjectMember | None:
        return await db.scalar(
            select(ProjectMember).where(
                ProjectMember.project_id == project_id, ProjectMember.user_id == user_id
            )
        )

    async def recalculate_progress(self, db: AsyncSession, project: Project) -> int:
        task_total, task_completed = (
            await db.execute(
                select(
                    func.count(Task.id),
                    func.count(Task.id).filter(func.lower(Task.status) == "completed"),
                ).where(Task.project_id == project.id, Task.organization_id == project.organization_id)
            )
        ).one()
        milestone_total, milestone_completed = (
            await db.execute(
                select(
                    func.count(ProjectMilestone.id),
                    func.count(ProjectMilestone.id).filter(
                        ProjectMilestone.status == "Completed"
                    ),
                ).where(
                    ProjectMilestone.project_id == project.id,
                    ProjectMilestone.organization_id == project.organization_id,
                )
            )
        ).one()
        total = int(task_total or 0) + int(milestone_total or 0)
        completed = int(task_completed or 0) + int(milestone_completed or 0)
        is_complete = total > 0 and completed >= total
        if total == 0:
            project.completion_percentage = 0
        elif is_complete:
            project.completion_percentage = 100
        else:
            project.completion_percentage = min(99, round(completed * 100 / total))
        if project.status == "Completed" and not is_complete:
            project.status = "In Progress"
        return project.completion_percentage
