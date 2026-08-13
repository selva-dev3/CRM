from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.repositories.organization_repository import OrganizationRepository


class OrganizationService:
    """Resolves a valid Organization foreign key for records that require one."""

    def __init__(self, repository: Optional[OrganizationRepository] = None) -> None:
        self.repository = repository or OrganizationRepository()

    async def resolve_valid_org_id(
        self, db: AsyncSession, current_user: Optional[User] = None
    ) -> str:
        if current_user and getattr(current_user, "organization_id", None):
            org = await self.repository.get_by_id(db, current_user.organization_id)
            if org:
                return org.id

        org = await self.repository.get_first(db)
        if org:
            return org.id

        org = await self.repository.create_default(db)
        return org.id


organization_service = OrganizationService()