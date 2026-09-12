from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.record_access import record_access_filter
from app.models import Company, Contact, Deal, Project, ProjectStakeholder, User


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
        access_filter = record_access_filter(
            access, assigned_column=Project.owner_id, created_column=Project.created_by
        )
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
        access_filter = record_access_filter(
            access, assigned_column=Project.owner_id, created_column=Project.created_by
        )
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
        access_filter = record_access_filter(
            access, assigned_column=Project.owner_id, created_column=Project.created_by
        )
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
