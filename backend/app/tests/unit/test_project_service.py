from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIException, ForbiddenError, NotFoundError
from app.models import Project, User
from app.repositories.project_repository import ProjectRepository
from app.schemas.project import ProjectCreate, ProjectUpdate
from app.services.project_service import ProjectService


def _user(**overrides: Any) -> User:
    values = {
        "id": "user-1",
        "organization_id": "org-1",
        "email": "user@example.com",
        "name": "User",
        "is_active": True,
    }
    values.update(overrides)
    return User(**values)


def _project(**overrides: Any) -> Project:
    values = {
        "id": "project-1",
        "organization_id": "org-1",
        "name": "Website refresh",
        "status": "Planning",
        "priority": "Medium",
        "completion_percentage": 20,
        "created_at": datetime(2026, 9, 1),
        "updated_at": datetime(2026, 9, 1),
    }
    values.update(overrides)
    return Project(**values)


@pytest.mark.asyncio
async def test_create_project_is_org_scoped_and_commits() -> None:
    project = _project()
    repository: Any = ProjectRepository()
    repository.create = AsyncMock(return_value=project)
    service = ProjectService(repository)
    db = AsyncMock(spec=AsyncSession)
    user = _user()

    result = await service.create_project(db, user, ProjectCreate(name="Website refresh"))

    assert result["id"] == "project-1"
    assert repository.create.await_args.args[1]["organization_id"] == "org-1"
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_and_delete_delegate_to_repository() -> None:
    project = _project()
    repository: Any = ProjectRepository()
    repository.get = AsyncMock(return_value=project)
    repository.update = AsyncMock(return_value=project)
    repository.delete = AsyncMock()
    service = ProjectService(repository)
    db = AsyncMock(spec=AsyncSession)
    user = _user()

    await service.update_project(db, user, "project-1", ProjectUpdate(status="Active"))
    await service.delete_project(db, user, "project-1")

    repository.update.assert_awaited_once_with(db, project, {"status": "Active"})
    repository.delete.assert_awaited_once_with(db, project)


@pytest.mark.asyncio
async def test_missing_or_foreign_project_is_not_found() -> None:
    repository: Any = ProjectRepository()
    repository.get = AsyncMock(return_value=None)
    service = ProjectService(repository)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(NotFoundError):
        await service.get_project(db, _user(), "foreign-project")


@pytest.mark.asyncio
async def test_owner_requires_assign_permission_and_same_org_user(monkeypatch) -> None:
    repository: Any = ProjectRepository()
    repository.create = AsyncMock(return_value=_project(owner_id="user-2"))
    repository.get_user_in_organization = AsyncMock(return_value=_user(id="user-2"))
    service = ProjectService(repository)
    db = AsyncMock(spec=AsyncSession)
    user = _user()
    from app.services.project_service import auth_service

    monkeypatch.setattr(auth_service, "get_user_permissions", AsyncMock(return_value=set()))
    with pytest.raises(ForbiddenError):
        await service.create_project(db, user, ProjectCreate(name="X", owner_id="user-2"))

    monkeypatch.setattr(
        auth_service, "get_user_permissions", AsyncMock(return_value={"projects:assign"})
    )
    repository.get_user_in_organization.return_value = None
    with pytest.raises(APIException, match="current organization"):
        await service.create_project(db, user, ProjectCreate(name="X", owner_id="foreign"))
