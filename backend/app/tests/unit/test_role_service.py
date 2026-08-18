from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIException, ForbiddenError, NotFoundError
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
    perm = type("P", (), {"key": "users:read"})()
    perm2 = type("P", (), {"key": "leads:read"})()
    repo = RoleRepository()
    repo.get_setting = AsyncMock(return_value=None)
    repo.get_permission_keys = AsyncMock(return_value=["users:read", "leads:read"])
    repo.list_roles = AsyncMock(return_value=[admin])
    repo.get_role_permissions = AsyncMock(return_value=[perm, perm2])
    service = RoleService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.list_roles(db, None)

    assert result[0]["type"] == "system"
    assert result[0]["permissions"] == ["users:read", "leads:read"]


@pytest.mark.asyncio
async def test_list_roles_forwards_org_id_to_repository():
    repo = RoleRepository()
    repo.get_setting = AsyncMock(return_value=None)
    repo.get_permission_keys = AsyncMock(return_value=[])
    repo.list_roles = AsyncMock(return_value=[])
    repo.get_role_permissions = AsyncMock(return_value=[])
    service = RoleService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    await service.list_roles(db, "Manage", org_id="org-1")

    assert repo.list_roles.await_args.kwargs["org_id"] == "org-1"
    assert repo.list_roles.await_args.args[1] == "Manage"


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
async def test_check_permission_super_admin_permission_allows_all():
    role = _make_role(name="Super Admin", is_system_role=True)
    super_perm = type("P", (), {"key": "super_admin:manage"})()
    user = type("U", (), {"id": "u1", "role": "role-1", "email": "a@b.com", "name": "A"})()
    repo = RoleRepository()
    repo.get_user_by_id_or_email = AsyncMock(return_value=user)
    repo.get_role_by_id_or_name = AsyncMock(return_value=role)
    repo.get_role_permissions = AsyncMock(return_value=[super_perm])
    service = RoleService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.check_permission(db, "u1", "anything:x")

    assert result["allowed"] is True


@pytest.mark.asyncio
async def test_check_permission_requires_exact_key():
    role = _make_role(name="Sales Manager", is_system_role=False)
    perm = type("P", (), {"key": "deals:read"})()
    user = type("U", (), {"id": "u1", "role": "role-1", "email": "a@b.com", "name": "A"})()
    repo = RoleRepository()
    repo.get_user_by_id_or_email = AsyncMock(return_value=user)
    repo.get_role_by_id_or_name = AsyncMock(return_value=role)
    repo.get_role_permissions = AsyncMock(return_value=[perm])
    service = RoleService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    granted = await service.check_permission(db, "u1", "deals:read")
    denied = await service.check_permission(db, "u1", "deals:delete")

    assert granted["allowed"] is True
    assert denied["allowed"] is False


@pytest.mark.asyncio
async def test_check_permission_denies_admin_name_role_without_grants():
    """An 'Admin'-named role must NOT be granted everything by name alone."""
    role = _make_role(name="Admin", is_system_role=True)
    user = type("U", (), {"id": "u1", "role": "role-1", "email": "a@b.com", "name": "A"})()
    repo = RoleRepository()
    repo.get_user_by_id_or_email = AsyncMock(return_value=user)
    repo.get_role_by_id_or_name = AsyncMock(return_value=role)
    repo.get_role_permissions = AsyncMock(return_value=[])
    service = RoleService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.check_permission(db, "u1", "anything:x")

    assert result["allowed"] is False


@pytest.mark.asyncio
async def test_check_permission_denies_unknown_role():
    user = type("U", (), {"id": "u1", "role": "ghost-role", "email": "a@b.com", "name": "A"})()
    repo = RoleRepository()
    repo.get_user_by_id_or_email = AsyncMock(return_value=user)
    repo.get_role_by_id_or_name = AsyncMock(return_value=None)
    service = RoleService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.check_permission(db, "u1", "leads:read")

    assert result["allowed"] is False


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


SYSTEM_ROLE_MESSAGE = "System roles cannot be modified or deleted."


def _system_role():
    return _make_role(id="sys-1", name="super_admin", is_system_role=True)


def _assert_forbidden(excinfo) -> None:
    assert isinstance(excinfo.value, ForbiddenError)
    assert excinfo.value.status_code == 403
    assert excinfo.value.message == SYSTEM_ROLE_MESSAGE


@pytest.mark.asyncio
async def test_update_system_role_forbidden():
    role = _system_role()
    repo = RoleRepository()
    repo.get_role = AsyncMock(return_value=role)
    service = RoleService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(ForbiddenError) as excinfo:
        await service.update_role(db, "sys-1", RoleUpdate(name="New Name"))
    _assert_forbidden(excinfo)
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_system_role_permissions_forbidden():
    role = _system_role()
    repo = RoleRepository()
    repo.get_role = AsyncMock(return_value=role)
    service = RoleService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(ForbiddenError) as excinfo:
        await service.update_role(db, "sys-1", RoleUpdate(permissions=["leads:read"]))
    _assert_forbidden(excinfo)
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_system_role_forbidden():
    role = _system_role()
    repo = RoleRepository()
    repo.get_role_by_id_or_name = AsyncMock(return_value=role)
    repo.delete_role = AsyncMock()
    service = RoleService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    async def fake_default_ids(db):
        return set()

    from unittest.mock import patch

    with patch.object(service, "_get_default_role_ids", fake_default_ids), pytest.raises(ForbiddenError) as excinfo:
        await service.delete_role(db, "sys-1")
    _assert_forbidden(excinfo)
    repo.delete_role.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_normal_role_succeeds():
    role = _make_role(id="role-1", name="Sales Manager")
    repo = RoleRepository()
    repo.get_role_by_id_or_name = AsyncMock(return_value=role)
    repo.delete_role = AsyncMock()
    service = RoleService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    async def fake_default_ids(db):
        return set()

    from unittest.mock import patch

    with patch.object(service, "_get_default_role_ids", fake_default_ids):
        result = await service.delete_role(db, "role-1")

    assert result["status"] == "success"
    repo.delete_role.assert_awaited_once_with(db, role)


@pytest.mark.asyncio
async def test_assign_permissions_to_system_role_forbidden():
    role = _system_role()
    repo = RoleRepository()
    repo.get_role = AsyncMock(return_value=role)
    repo.delete_role_permission = AsyncMock()
    service = RoleService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(ForbiddenError) as excinfo:
        await service.assign_permissions(db, "sys-1", ["leads:read"])
    _assert_forbidden(excinfo)
    repo.delete_role_permission.assert_not_awaited()


@pytest.mark.asyncio
async def test_remove_permission_from_system_role_forbidden():
    role = _system_role()
    repo = RoleRepository()
    repo.get_role = AsyncMock(return_value=role)
    repo.remove_permission_from_role = AsyncMock()
    service = RoleService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(ForbiddenError) as excinfo:
        await service.remove_permission(db, "sys-1", "p1")
    _assert_forbidden(excinfo)
    repo.remove_permission_from_role.assert_not_awaited()


@pytest.mark.asyncio
async def test_bulk_delete_roles_with_system_role_forbidden():
    role = _make_role(id="role-1", name="Sales Manager")
    sys_role = _system_role()
    repo = RoleRepository()
    repo.get_role = AsyncMock(side_effect=lambda db, role_id: role if role_id == "role-1" else sys_role)
    repo.delete_role = AsyncMock()
    service = RoleService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    async def fake_default_ids(db):
        return set()

    from unittest.mock import patch

    with patch.object(service, "_get_default_role_ids", fake_default_ids), pytest.raises(ForbiddenError) as excinfo:
        await service.bulk_delete_roles(db, ["role-1", "sys-1"])
    _assert_forbidden(excinfo)
    repo.delete_role.assert_not_awaited()


@pytest.mark.asyncio
async def test_bulk_delete_roles_skips_defaults_only():
    role = _make_role(id="role-1", name="Sales Manager")
    default_role = _make_role(id="role-2", name="Default Role")
    repo = RoleRepository()
    repo.get_role = AsyncMock(side_effect=lambda db, role_id: role if role_id == "role-1" else default_role)
    repo.delete_role = AsyncMock()
    service = RoleService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    async def fake_default_ids(db):
        return {"role-2"}

    from unittest.mock import patch

    with patch.object(service, "_get_default_role_ids", fake_default_ids):
        result = await service.bulk_delete_roles(db, ["role-1", "role-2"])

    assert result["affected_count"] == 1
    repo.delete_role.assert_awaited_once_with(db, role)