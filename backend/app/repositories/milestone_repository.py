from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

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
    ) -> list[ProjectMilestone]:
        conditions = [ProjectMilestone.organization_id == organization_id]
        if project_id:
            conditions.append(ProjectMilestone.project_id == project_id)
        if status:
            conditions.append(ProjectMilestone.status == status)
        result = await db.execute(
            select(ProjectMilestone)
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
    ) -> int:
        conditions = [ProjectMilestone.organization_id == organization_id]
        if project_id:
            conditions.append(ProjectMilestone.project_id == project_id)
        if status:
            conditions.append(ProjectMilestone.status == status)
        return int(
            (
                await db.execute(
                    select(func.count()).select_from(ProjectMilestone).where(*conditions)
                )
            ).scalar_one()
        )

    async def get(
        self, db: AsyncSession, *, milestone_id: str, organization_id: str
    ) -> ProjectMilestone | None:
        return await db.scalar(
            select(ProjectMilestone).where(
                ProjectMilestone.id == milestone_id,
                ProjectMilestone.organization_id == organization_id,
            )
        )

    async def get_project(
        self, db: AsyncSession, *, project_id: str, organization_id: str
    ) -> Project | None:
        return await db.scalar(
            select(Project).where(
                Project.id == project_id,
                Project.organization_id == organization_id,
            )
        )


milestone_repository = MilestoneRepository()
