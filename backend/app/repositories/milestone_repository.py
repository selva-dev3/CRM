from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.record_access import record_access_filter
from app.models import Project, ProjectMilestone


class MilestoneRepository:
    async def list(
        self,
        db: AsyncSession,
        *,
        organization_id: str,
        page: int,
        limit: int,
        project_id: str | None = None,
        status: str | None = None,
        access=None,
    ) -> list[ProjectMilestone]:
        conditions = [ProjectMilestone.organization_id == organization_id]
        access_filter = record_access_filter(
            access, assigned_column=Project.owner_id, created_column=Project.created_by
        )
        if access_filter is not None:
            conditions.append(access_filter)
        if project_id:
            conditions.append(ProjectMilestone.project_id == project_id)
        if status:
            conditions.append(ProjectMilestone.status == status)
        result = await db.execute(
            select(ProjectMilestone).join(Project, Project.id == ProjectMilestone.project_id)
            .where(*conditions)
            .order_by(ProjectMilestone.due_date.asc(), ProjectMilestone.created_at.desc())
            .offset((page - 1) * limit)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def count(
        self,
        db: AsyncSession,
        *,
        organization_id: str,
        project_id: str | None = None,
        status: str | None = None,
        access=None,
    ) -> int:
        conditions = [ProjectMilestone.organization_id == organization_id]
        access_filter = record_access_filter(
            access, assigned_column=Project.owner_id, created_column=Project.created_by
        )
        if access_filter is not None:
            conditions.append(access_filter)
        if project_id:
            conditions.append(ProjectMilestone.project_id == project_id)
        if status:
            conditions.append(ProjectMilestone.status == status)
        return int(
            (
                await db.execute(
                    select(func.count())
                    .select_from(ProjectMilestone)
                    .join(Project, Project.id == ProjectMilestone.project_id)
                    .where(*conditions)
                )
            ).scalar_one()
        )

    async def get(
        self, db: AsyncSession, *, milestone_id: str, organization_id: str, access=None
    ) -> ProjectMilestone | None:
        conditions = [
                ProjectMilestone.id == milestone_id,
                ProjectMilestone.organization_id == organization_id,
        ]
        access_filter = record_access_filter(
            access, assigned_column=Project.owner_id, created_column=Project.created_by
        )
        if access_filter is not None:
            conditions.append(access_filter)
        return await db.scalar(
            select(ProjectMilestone)
            .join(Project, Project.id == ProjectMilestone.project_id)
            .where(*conditions)
        )

    async def get_project(
        self, db: AsyncSession, *, project_id: str, organization_id: str, access=None
    ) -> Project | None:
        conditions = [
                Project.id == project_id,
                Project.organization_id == organization_id,
        ]
        access_filter = record_access_filter(
            access, assigned_column=Project.owner_id, created_column=Project.created_by
        )
        if access_filter is not None:
            conditions.append(access_filter)
        return await db.scalar(select(Project).where(*conditions))


milestone_repository = MilestoneRepository()
