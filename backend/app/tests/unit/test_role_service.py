from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIException, NotFoundError
from app.models import Role
from app.repositories.role_repository import RoleRepository
from app.schemas.crm_schemas import PermissionCreate, RoleCreate, RoleUpdate
from app.services.role_service import ALL_STANDARD_PERMISSIONS, RoleService


def _make_role(**overrides) -> Role:
    defaults = {
        "id": "role-1",
        "name": "Sales Manager",
        "description": "Manages sales team",
        "is_system_role": False,
        "created_at": datetime(2026, 8, 5, tzinfo=timezone.utc),
    }
    defaults.update(overrides)
    return Role(**defaults)


@pytest.mark.asyncio
async def test_list_roles_classifies_types():
    admin = _make_role(id="role-1", name="admin", is_system_role=True)
    repo = RoleRepository()
    repo.get_setting = AsyncMock(return_value=None)
    repo.get_permission_keys = AsyncMock(return_value=["users:read", "leads:read"])
    repo.list_roles = AsyncMock(return_value=[admin])
    repo.get_role_permissions = AsyncMock(return_value=[])
    service = RoleService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.list_roles(db, None)

    assert result[0]["type"] == "system"
    assert result[0]["permissions"] == ["users:read", "leads:read"]


@pytest.mark.asyncio
async def test_get_role_not_found():
    repo = RoleRepository()
    repo.get_role = AsyncMock(return_value=None)
    service = RoleService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(NotFoundError):
        await service.get_role(db, "missing")


@pytest.mark.asyncio
async def test_create_role_without_permissions(monkeypatch):
    role = _make_role()
    repo = RoleRepository()
    repo.create_role = AsyncMock(return_value=role)
    service = RoleService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.create_role(db, RoleCreate(name="Sales Manager", permissions=[]))

    assert result["name"] == "Sales Manager"
    assert result["permissions"] == []
    assert result["type"] == "custom"
    db.commit.assert_awaited()


@pytest.mark.asyncio
async def test_create_role_with_permissions(monkeypatch):
    role = _make_role()
    perm = type("P", (), {"id": "p1", "key": "leads:read", "name": "View", "category": "Leads", "description": "d"})()
    repo = RoleRepository()
    repo.create_role = AsyncMock(return_value=role)
    repo.get_permissions_by_keys_or_ids = AsyncMock(return_value=[perm])
    repo.add_role_permission = AsyncMock()
    service = RoleService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.create_role(db, RoleCreate(name="Sales Manager", permissions=["leads:read"]))

    assert result["permissions"] == ["leads:read"]
    repo.add_role_permission.assert_awaited_with(db, "role-1", "p1")


@pytest.mark.asyncio
async def test_create_permission_fallback_on_error():
    repo = RoleRepository()
    repo.create_permission = AsyncMock(return_value=None)
    service = RoleService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    async def commit_fail():
        raise RuntimeError

    db.commit = AsyncMock(side_effect=commit_fail)

    result = await service.create_permission(db, PermissionCreate(key="x:y", name="X Y"))

    assert result["key"] == "x:y"
    assert result["id"].startswith("perm-")


@pytest.mark.asyncio
async def test_set_multiple_default_roles():
    repo = RoleRepository()
    repo.get_setting = AsyncMock(return_value=None)
    repo.upsert_setting = AsyncMock()
    service = RoleService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.set_multiple_default_roles(db, ["role-1", "role-2"])

    assert repo.upsert_setting.await_count == 2
    assert "2 selected" in result["message"]
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_default_role_fallback():
    repo = RoleRepository()
    repo.get_setting = AsyncMock(return_value=None)
    repo.get_role_by_id_or_name = AsyncMock(return_value=None)
    repo.get_first_role = AsyncMock(return_value=None)
    service = RoleService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.get_default_role(db)

    assert result["id"] == "sys-manager"


@pytest.mark.asyncio
async def test_delete_role_blocks_default(monkeypatch):
    role = _make_role()
    repo = RoleRepository()
    repo.get_role_by_id_or_name = AsyncMock(return_value=role)
    service = RoleService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    async def fake_default_ids(db):
        return {"role-1"}

    monkeypatch.setattr(service, "_get_default_role_ids", fake_default_ids)

    with pytest.raises(APIException):
        await service.delete_role(db, "role-1")


@pytest.mark.asyncio
async def test_check_permission_admin_allows_all():
    role = _make_role(name="Super Admin", is_system_role=True)
    user = type("U", (), {"id": "u1", "role": "role-1", "email": "a@b.com", "name": "A"})()
    repo = RoleRepository()
    repo.get_user_by_id_or_email = AsyncMock(return_value=user)
    repo.get_role_by_id_or_name = AsyncMock(return_value=role)
    service = RoleService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.check_permission(db, "u1", "anything:x")

    assert result["allowed"] is True


@pytest.mark.asyncio
async def test_update_role_partial():
    role = _make_role()
    repo = RoleRepository()
    repo.get_role = AsyncMock(return_value=role)
    repo.get_role_permission_ids = AsyncMock(return_value=[])
    repo.get_permissions_by_keys_or_ids = AsyncMock(return_value=[])
    service = RoleService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.update_role(db, "role-1", RoleUpdate(name="New Name", permissions=["a:b"]))

    assert role.name == "New Name"
    assert result["name"] == "New Name"
    db.commit.assert_awaited()


@pytest.mark.asyncio
async def test_clone_role_copies_permissions():
    role = _make_role()
    orig_perms = [type("P", (), {"id": "p1", "key": "leads:read"})()]
    repo = RoleRepository()
    repo.get_role = AsyncMock(return_value=role)
    repo.create_role = AsyncMock(return_value=_make_role(id="role-2", name="Cloned"))
    repo.get_role_permissions = AsyncMock(return_value=orig_perms)
    repo.add_role_permission = AsyncMock()
    service = RoleService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.clone_role(db, "role-1", "Cloned")

    assert result["name"] == "Cloned"
    assert result["permissions"] == ["leads:read"]
    repo.add_role_permission.assert_awaited_once()


@pytest.mark.asyncio
async def test_assign_permissions_not_found():
    repo = RoleRepository()
    repo.get_role = AsyncMock(return_value=None)
    service = RoleService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(NotFoundError):
        await service.assign_permissions(db, "missing", ["a:b"])


@pytest.mark.asyncio
async def test_get_role_users_fallback():
    repo = RoleRepository()
    repo.get_role_by_id_or_name = AsyncMock(return_value=None)
    repo.get_users_by_role = AsyncMock(return_value=[])
    repo.get_users_by_user_role_id = AsyncMock(return_value=[])
    service = RoleService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.get_role_users(db, "unknown")

    assert result[0]["id"] == "usr-101"


@pytest.mark.asyncio
async def test_set_default_role_adds_and_removes():
    role = _make_role()
    repo = RoleRepository()
    repo.get_role_by_id_or_name = AsyncMock(return_value=role)
    repo.get_setting = AsyncMock(return_value=None)
    repo.upsert_setting = AsyncMock()
    service = RoleService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.set_default_role(db, "role-1")
    assert "added as default" in result["message"]

    repo.get_setting = AsyncMock(
        return_value=type("S", (), {"value": '["role-1"]'})()
    )
    result2 = await service.set_default_role(db, "role-1")
    assert "removed from default" in result2["message"]


def test_all_standard_permissions_complete():
    assert len(ALL_STANDARD_PERMISSIONS) >= 70
    keys = {p["key"] for p in ALL_STANDARD_PERMISSIONS}
    assert "leads:read" in keys
    assert "ai:generate" in keys
    assert len(keys) == len(ALL_STANDARD_PERMISSIONS)