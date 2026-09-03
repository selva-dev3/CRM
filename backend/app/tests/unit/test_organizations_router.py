from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.routers import organizations
from app.models import User
from app.services.organization_service import organization_domain_service


def test_current_organization_route_precedes_dynamic_org_route():
    route_paths = [route.path for route in organizations.router.routes]

    assert route_paths.index("/current") < route_paths.index("/{org_id}")


@pytest.mark.asyncio
async def test_get_current_organization_delegates_with_authenticated_user(monkeypatch):
    db = AsyncMock(spec=AsyncSession)
    current_user = User(
        id="user-1",
        name="Admin",
        email="admin@example.com",
        organization_id="org-current",
        is_active=True,
    )
    get_current = AsyncMock(return_value={"id": "org-current"})
    monkeypatch.setattr(organization_domain_service, "get_current_organization", get_current)

    result = await organizations.get_current_organization(db=db, current_user=current_user)

    assert result == {"id": "org-current"}
    get_current.assert_awaited_once_with(db, current_user)
