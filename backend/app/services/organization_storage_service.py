"""Keep tenant storage writes inside the parent lifetime until metadata commits."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ForbiddenError
from app.repositories.organization_repository import OrganizationRepository


async def lock_organization_storage(db: AsyncSession, organization_id: str) -> None:
    if not await OrganizationRepository().lock_storage_writer(db, organization_id):
        raise ForbiddenError(message="Organization is unavailable", code="ORGANIZATION_UNAVAILABLE")
