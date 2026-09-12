from unittest.mock import AsyncMock

import pytest
from fastapi import Response
from fastapi.routing import APIRoute
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.routers import activities
from app.models import User
from app.services.activity_service import activity_service


def _user() -> User:
    return User(
        id="user-1",
        organization_id="org-1",
        email="user@example.com",
        name="User",
        is_active=True,
    )


@pytest.mark.asyncio
async def test_activity_route_uses_valid_tenant_context(monkeypatch) -> None:
    db = AsyncMock(spec=AsyncSession)
    user = _user()
    resolve_org = AsyncMock(return_value="org-selected")
    list_activities = AsyncMock(return_value=([{"id": "calls:call-1"}], 8))
    monkeypatch.setattr(activities, "get_valid_org_id", resolve_org)
    monkeypatch.setattr(activity_service, "list_activities", list_activities)
    response = Response()

    result = await activities.list_activities(
        response=response,
        page=2,
        limit=20,
        module="calls",
        search="discovery",
        db=db,
        current_user=user,
    )

    resolve_org.assert_awaited_once_with(db, user)
    list_activities.assert_awaited_once_with(
        db,
        user,
        organization_id="org-selected",
        page=2,
        limit=20,
        module="calls",
        search="discovery",
    )
    assert result == [{"id": "calls:call-1"}]
    assert response.headers["X-Total-Count"] == "8"


def test_activity_route_bounds_pagination() -> None:
    route = next(
        route
        for route in activities.router.routes
        if isinstance(route, APIRoute) and route.path == "" and "GET" in route.methods
    )
    params = {parameter.name: parameter for parameter in route.dependant.query_params}

    assert any(getattr(item, "ge", None) == 1 for item in params["page"].field_info.metadata)
    assert any(getattr(item, "ge", None) == 1 for item in params["limit"].field_info.metadata)
    assert any(getattr(item, "le", None) == 100 for item in params["limit"].field_info.metadata)
