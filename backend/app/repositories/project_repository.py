from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Project, User


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
    ) -> list[Project]:
        conditions = [Project.organization_id == organization_id]
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
    ) -> int:
        conditions = [Project.organization_id == organization_id]
        if status:
            conditions.append(Project.status == status)
        if priority:
            conditions.append(Project.priority == priority)
        if search and search.strip():
            conditions.append(Project.name.ilike(f"%{search.strip()}%"))
        result = await db.execute(select(func.count()).select_from(Project).where(*conditions))
        return int(result.scalar_one())

    async def get(
        self, db: AsyncSession, *, project_id: str, organization_id: str
    ) -> Project | None:
        result = await db.execute(
            select(Project).where(
                Project.id == project_id,
                Project.organization_id == organization_id,
            )
        )
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
