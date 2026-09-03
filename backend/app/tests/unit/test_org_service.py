from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ForbiddenError, NotFoundError
from app.models import User
from app.services.org_service import OrganizationService


@pytest.mark.asyncio
async def test_current_user_without_organization_does_not_fall_back():
    repository = AsyncMock()
    service = OrganizationService(repository=repository)

    with pytest.raises(ForbiddenError):
        await service.resolve_valid_org_id(
            AsyncMock(spec=AsyncSession), User(id="user-1", email="user@crm.com")
        )
    repository.get_first.assert_not_awaited()


@pytest.mark.asyncio
async def test_unknown_current_organization_does_not_fall_back():
    repository = AsyncMock()
    repository.get_by_id.return_value = None
    service = OrganizationService(repository=repository)
    user = User(id="user-1", email="user@crm.com", organization_id="org-missing")

    with pytest.raises(NotFoundError):
        await service.resolve_valid_org_id(AsyncMock(spec=AsyncSession), user)
    repository.get_first.assert_not_awaited()
