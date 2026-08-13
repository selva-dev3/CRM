from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Organization


class OrganizationRepository:
    """DB query layer for the Organization entity. No business logic here."""

    async def get_by_id(self, db: AsyncSession, org_id: str) -> Optional[Organization]:
        result = await db.execute(select(Organization).where(Organization.id == org_id))
        return result.scalars().first()

    async def get_first(self, db: AsyncSession) -> Optional[Organization]:
        result = await db.execute(select(Organization).limit(1))
        return result.scalars().first()

    async def create_default(self, db: AsyncSession) -> Organization:
        org = Organization(
            id="org-1",
            name="Default Organization",
            slug="default-org",
            status="active",
        )
        db.add(org)
        await db.commit()
        return org