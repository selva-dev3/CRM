from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Integration, Organization, User


class IntegrationRepository:
    """Query layer for the Integration domain — no business logic."""

    async def resolve_org_id(self, db: AsyncSession, current_user: Optional[User] = None) -> str:
        if current_user and getattr(current_user, "organization_id", None):
            return current_user.organization_id
        res = await db.execute(select(Organization).limit(1))
        org = res.scalars().first()
        return org.id if org else "org-1"

    async def list_all(self, db: AsyncSession, limit: int = 20) -> Sequence[Integration]:
        res = await db.execute(select(Integration).limit(limit))
        return res.scalars().all()

    async def get_by_provider(self, db: AsyncSession, org_id: str, provider: str) -> Optional[Integration]:
        return await db.scalar(
            select(Integration).where(
                Integration.organization_id == org_id,
                Integration.provider == provider,
            )
        )

    async def get_connected_by_provider(
        self, db: AsyncSession, org_id: str, provider: str
    ) -> Optional[Integration]:
        return await db.scalar(
            select(Integration).where(
                Integration.organization_id == org_id,
                Integration.provider == provider,
                Integration.is_connected == True,  # noqa: E712
            )
        )

    async def get_by_name_like(self, db: AsyncSession, name: str) -> Optional[Integration]:
        res = await db.execute(select(Integration).where(Integration.name.ilike(f"%{name}%")))
        return res.scalars().first()

    async def create(self, db: AsyncSession, *, data: dict) -> Integration:
        integration = Integration(**data)
        db.add(integration)
        return integration

    async def commit(self, db: AsyncSession) -> None:
        await db.commit()