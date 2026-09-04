from unittest.mock import AsyncMock

import pytest
from fastapi.routing import APIRoute
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import require_permission
from app.api.v1.routers import projects
from app.core.errors import ForbiddenError
from app.models import User
from app.schemas.project import ProjectCreate, ProjectUpdate
from app.services.project_service import project_service


def _user() -> User:
    return User(
        id="user-1",
        organization_id="org-1",
        email="user@example.com",
        name="User",
        is_active=True,
    )


@pytest.mark.asyncio
async def test_project_routes_delegate_with_current_user(monkeypatch) -> None:
    db = AsyncMock(spec=AsyncSession)
    user = _user()
    list_projects = AsyncMock(return_value=[])
    create_project = AsyncMock(return_value={"id": "project-1"})
    monkeypatch.setattr(project_service, "list_projects", list_projects)
    monkeypatch.setattr(project_service, "create_project", create_project)

    await projects.list_projects(db=db, current_user=user, page=2, limit=10)
    await projects.create_project(ProjectCreate(name="X"), db=db, current_user=user)

    list_projects.assert_awaited_once_with(db, user, page=2, limit=10, status=None, priority=None)
    create_project.assert_awaited_once_with(db, user, ProjectCreate(name="X"))


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["get_project", "update_project", "delete_project"])
async def test_project_mutation_routes_delegate_with_current_user(monkeypatch, action) -> None:
    db = AsyncMock(spec=AsyncSession)
    user = _user()
    delegate = AsyncMock(return_value={"id": "project-1"})
    monkeypatch.setattr(project_service, action, delegate)

    if action == "get_project":
        await projects.get_project("project-1", db=db, current_user=user)
        delegate.assert_awaited_once_with(db, user, "project-1")
    elif action == "update_project":
        payload = ProjectUpdate(status="Active")
        await projects.update_project("project-1", payload, db=db, current_user=user)
        delegate.assert_awaited_once_with(db, user, "project-1", payload)
    else:
        await projects.delete_project("project-1", db=db, current_user=user)
        delegate.assert_awaited_once_with(db, user, "project-1")


def test_project_list_route_bounds_pagination() -> None:
    route = next(
        route
        for route in projects.router.routes
        if isinstance(route, APIRoute) and route.path == "" and "GET" in route.methods
    )
    params = {parameter.name: parameter for parameter in route.dependant.query_params}

    page_metadata = params["page"].field_info.metadata
    limit_metadata = params["limit"].field_info.metadata
    assert any(getattr(item, "ge", None) == 1 for item in page_metadata)
    assert any(getattr(item, "ge", None) == 1 for item in limit_metadata)
    assert any(getattr(item, "le", None) == 100 for item in limit_metadata)


@pytest.mark.asyncio
async def test_projects_read_dependency_rejects_missing_permission(monkeypatch) -> None:
    dependency = require_permission("projects:read")
    from app.api.v1.deps import auth_service

    monkeypatch.setattr(auth_service, "get_user_permissions", AsyncMock(return_value=set()))

    with pytest.raises(ForbiddenError):
        await dependency(current_user=_user(), db=AsyncMock(spec=AsyncSession))


@pytest.mark.parametrize(
    "payload",
    [
        {"name": ""},
        {"name": "Valid", "budget": -1},
        {"name": "Valid", "completion_percentage": 101},
    ],
)
def test_project_create_validation_rejects_invalid_payloads(payload) -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ProjectCreate(**payload)
