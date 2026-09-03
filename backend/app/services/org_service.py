from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ForbiddenError, NotFoundError
from app.models import User
from app.repositories.organization_repository import OrganizationRepository


class OrganizationService:
    """Resolves a valid Organization foreign key for records that require one."""

    def __init__(self, repository: OrganizationRepository | None = None) -> None:
        self.repository = repository or OrganizationRepository()

    async def resolve_valid_org_id(self, db: AsyncSession, current_user: User | None = None) -> str:
        if current_user is not None:
            organization_id = getattr(current_user, "organization_id", None)
            if not organization_id:
                raise ForbiddenError(message="Authenticated user has no current organization")
            org = await self.repository.get_by_id(db, organization_id)
            if not org:
                raise NotFoundError(message="Current organization not found")
            return org.id

        org = await self.repository.get_first(db)
        if org:
            return org.id

        org = await self.repository.create_default(db)
        return org.id


organization_service = OrganizationService()
