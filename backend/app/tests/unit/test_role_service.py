from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIException, ForbiddenError, NotFoundError
from app.models import Role, RolePermission
from app.repositories.role_repository import RoleRepository
from app.schemas.crm_schemas import PermissionCreate, RoleCreate, RoleUpdate
from app.services.role_service import ALL_STANDARD_PERMISSIONS, RoleService


def _make_role(**overrides) -> Role:
    defaults = {
        "id": "role-1",
        "name": "Sales Manager",
        "description": "Manages sales team",
        "is_system_role": False,
        "created_at": datetime(2026, 8, 5, tzinfo=UTC),
    }
    defaults.update(overrides)
    return Role(**defaults)


@pytest.mark.asyncio
async def test_list_roles_classifies_types():
    admin = _make_role(id="role-1", name="admin", is_system_role=True)
    perm = type("P", (), {"key": "users:read"})()
    perm2 = type("P", (), {"key": "leads:read"})()
    repo: Any = RoleRepository()
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
    repo: Any = RoleRepository()
    repo.get_setting = AsyncMock(return_value=None)
    repo.get_permission_keys = AsyncMock(return_value=[])
    repo.list_roles = AsyncMock(return_value=[])
    repo.get_role_permissions = AsyncMock(return_value=[])
    service = RoleService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    await service.list_roles(db, "Manage", org_id="org-1")

    repo.list_roles.assert_awaited_once_with(db, "Manage", org_id="org-1")


@pytest.mark.asyncio
async def test_get_role_not_found():
    repo: Any = RoleRepository()
    repo.get_role = AsyncMock(return_value=None)
    service = RoleService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(NotFoundError):
        await service.get_role(db, "missing")


@pytest.mark.asyncio
async def test_create_role_without_permissions(monkeypatch):
    role = _make_role()
    repo: Any = RoleRepository()
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
    perm = type(
        "P",
        (),
        {"id": "p1", "key": "leads:read", "name": "View", "category": "Leads", "description": "d"},
    )()
    repo: Any = RoleRepository()
    repo.create_role = AsyncMock(return_value=role)
    repo.get_permissions_by_keys_or_ids = AsyncMock(return_value=[perm])
    repo.add_role_permission = AsyncMock()
    service = RoleService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.create_role(
        db, RoleCreate(name="Sales Manager", permissions=["leads:read"])
    )

    assert result["permissions"] == ["leads:read"]
    repo.add_role_permission.assert_awaited_with(db, "role-1", "p1")


@pytest.mark.asyncio
async def test_create_permission_fallback_on_error():
    repo: Any = RoleRepository()
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
    repo: Any = RoleRepository()
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
    repo: Any = RoleRepository()
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
    repo: Any = RoleRepository()
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
    repo: Any = RoleRepository()
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
    repo: Any = RoleRepository()
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
    repo: Any = RoleRepository()
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
    repo: Any = RoleRepository()
    repo.get_user_by_id_or_email = AsyncMock(return_value=user)
    repo.get_role_by_id_or_name = AsyncMock(return_value=None)
    service = RoleService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.check_permission(db, "u1", "leads:read")

    assert result["allowed"] is False


@pytest.mark.asyncio
async def test_list_roles_admin_returns_only_assigned_permissions():
    """Admin with 185 assigned role_permissions (incl. super_admin:manage) resolves to exactly those 185.

    The other 9 keys present in the permission catalog must NOT be added implicitly.
    """
    admin = _make_role(id="role-admin", name="Admin", is_system_role=True)
    all_db_keys = [f"perm:{i:03d}" for i in range(194)]
    assigned_keys = [f"perm:{i:03d}" for i in range(184)] + ["super_admin:manage"]
    assert len(assigned_keys) == 185
    perms = [type("P", (), {"key": k})() for k in assigned_keys]
    repo: Any = RoleRepository()
    repo.get_setting = AsyncMock(return_value=None)
    repo.get_permission_keys = AsyncMock(return_value=all_db_keys)
    repo.list_roles = AsyncMock(return_value=[admin])
    repo.get_role_permissions = AsyncMock(return_value=perms)
    service = RoleService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.list_roles(db, None)

    assert len(result[0]["permissions"]) == 185
    assert set(result[0]["permissions"]) == set(assigned_keys)
    assert "super_admin:manage" in result[0]["permissions"]
    assert "perm:184" not in result[0]["permissions"]


@pytest.mark.asyncio
async def test_super_admin_role_resolves_all_keys():
    """The super_admin role (by name) is the only role granted every known key."""
    role = _make_role(id="sys-1", name="super_admin", is_system_role=True)
    all_db_keys = [f"perm:{i:03d}" for i in range(194)]
    repo: Any = RoleRepository()
    repo.get_role = AsyncMock(return_value=role)
    repo.get_permission_keys = AsyncMock(return_value=all_db_keys)
    repo.get_role_permissions = AsyncMock(
        return_value=[type("P", (), {"key": "super_admin:manage"})()]
    )
    service = RoleService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.get_role(db, "sys-1")

    assert result["permissions"] == all_db_keys


@pytest.mark.asyncio
async def test_check_permission_admin_holding_super_admin_manage_denies_unassigned():
    """Admin holding super_admin:manage only passes for keys explicitly assigned (fail closed)."""
    role = _make_role(name="Admin", is_system_role=True)
    perms = [type("P", (), {"key": "super_admin:manage"}), type("P", (), {"key": "deals:read"})]
    user = type("U", (), {"id": "u1", "role": "role-1", "email": "a@b.com", "name": "A"})()
    repo: Any = RoleRepository()
    repo.get_user_by_id_or_email = AsyncMock(return_value=user)
    repo.get_role_by_id_or_name = AsyncMock(return_value=role)
    repo.get_role_permissions = AsyncMock(return_value=perms)
    service = RoleService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    granted = await service.check_permission(db, "u1", "deals:read")
    denied = await service.check_permission(db, "u1", "anything:x")

    assert granted["allowed"] is True
    assert denied["allowed"] is False


@pytest.mark.asyncio
async def test_is_system_role_does_not_grant_permissions():
    """is_system_role only protects a role from mutation; it never grants permissions."""
    role = _make_role(id="sys-2", name="Manager", is_system_role=True)
    all_db_keys = ["dashboard:read", "users:read", "leads:read"]
    repo: Any = RoleRepository()
    repo.get_role = AsyncMock(return_value=role)
    repo.get_permission_keys = AsyncMock(return_value=all_db_keys)
    repo.get_role_permissions = AsyncMock(return_value=[])
    service = RoleService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.get_role(db, "sys-2")

    assert result["permissions"] == []


@pytest.mark.asyncio
async def test_update_role_partial():
    role = _make_role()
    repo: Any = RoleRepository()
    repo.get_role = AsyncMock(return_value=role)
    repo.get_role_permission_ids = AsyncMock(return_value=[])
    repo.get_permissions_by_keys_or_ids = AsyncMock(return_value=[])
    service = RoleService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.update_role(
        db, "role-1", RoleUpdate(name="New Name", permissions=["a:b"])
    )

    assert role.name == "New Name"
    assert result["name"] == "New Name"
    db.commit.assert_awaited()


@pytest.mark.asyncio
async def test_clone_role_copies_permissions():
    role = _make_role()
    orig_perms = [type("P", (), {"id": "p1", "key": "leads:read"})()]
    repo: Any = RoleRepository()
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
    repo: Any = RoleRepository()
    repo.get_role = AsyncMock(return_value=None)
    service = RoleService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(NotFoundError):
        await service.assign_permissions(db, "missing", ["a:b"])


@pytest.mark.asyncio
async def test_get_role_users_fallback():
    repo: Any = RoleRepository()
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
    repo: Any = RoleRepository()
    repo.get_role_by_id_or_name = AsyncMock(return_value=role)
    repo.get_setting = AsyncMock(return_value=None)
    repo.upsert_setting = AsyncMock()
    service = RoleService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.set_default_role(db, "role-1")
    assert "added as default" in result["message"]

    repo.get_setting = AsyncMock(return_value=type("S", (), {"value": '["role-1"]'})())
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
    repo: Any = RoleRepository()
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
    repo: Any = RoleRepository()
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
    repo: Any = RoleRepository()
    repo.get_role_by_id_or_name = AsyncMock(return_value=role)
    repo.delete_role = AsyncMock()
    service = RoleService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    async def fake_default_ids(db):
        return set()

    from unittest.mock import patch

    with (
        patch.object(service, "_get_default_role_ids", fake_default_ids),
        pytest.raises(ForbiddenError) as excinfo,
    ):
        await service.delete_role(db, "sys-1")
    _assert_forbidden(excinfo)
    repo.delete_role.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_normal_role_succeeds():
    role = _make_role(id="role-1", name="Sales Manager")
    repo: Any = RoleRepository()
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
    repo: Any = RoleRepository()
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
    repo: Any = RoleRepository()
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
    repo: Any = RoleRepository()
    repo.get_role = AsyncMock(
        side_effect=lambda db, role_id: role if role_id == "role-1" else sys_role
    )
    repo.delete_role = AsyncMock()
    service = RoleService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    async def fake_default_ids(db):
        return set()

    from unittest.mock import patch

    with (
        patch.object(service, "_get_default_role_ids", fake_default_ids),
        pytest.raises(ForbiddenError) as excinfo,
    ):
        await service.bulk_delete_roles(db, ["role-1", "sys-1"])
    _assert_forbidden(excinfo)
    repo.delete_role.assert_not_awaited()


@pytest.mark.asyncio
async def test_bulk_delete_roles_skips_defaults_only():
    role = _make_role(id="role-1", name="Sales Manager")
    default_role = _make_role(id="role-2", name="Default Role")
    repo: Any = RoleRepository()
    repo.get_role = AsyncMock(
        side_effect=lambda db, role_id: role if role_id == "role-1" else default_role
    )
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


def _make_result_mock(items=None, first_item=None) -> MagicMock:
    res = MagicMock()
    res.scalars.return_value.all.return_value = items if items is not None else []
    res.scalars.return_value.first.return_value = first_item
    return res


@pytest.mark.asyncio
async def test_seed_permissions_global_system_admin_is_synchronized():
    """TEST 1: Global system Admin (is_system_role=True, organization_id=None) is synchronized with standard permissions."""
    admin_role = _make_role(id="admin-1", name="Admin", is_system_role=True, organization_id=None)
    perm_bill = type("P", (), {"id": "p-bill", "key": "organization:billing"})()
    perm_brand = type("P", (), {"id": "p-brand", "key": "organization:branding"})()

    repo: Any = RoleRepository()
    db = AsyncMock(spec=AsyncSession)

    mock_res_keys = _make_result_mock(items=["dashboard:read"])
    mock_res_admin = _make_result_mock(first_item=admin_role)
    mock_res_perms = _make_result_mock(items=[perm_bill, perm_brand])
    mock_res_rp = _make_result_mock(items=[])

    db.execute = AsyncMock(side_effect=[mock_res_keys, mock_res_admin, mock_res_perms, mock_res_rp])
    db.add = AsyncMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()

    await repo.seed_permissions(
        db,
        [
            {
                "key": "organization:billing",
                "name": "Manage Subscriptions",
                "category": "Organization",
                "description": "",
            },
            {
                "key": "organization:branding",
                "name": "Update Logo",
                "category": "Organization",
                "description": "",
            },
        ],
    )

    added_rp = [
        call.args[0] for call in db.add.call_args_list if isinstance(call.args[0], RolePermission)
    ]
    assert len(added_rp) == 2
    assert {rp.permission_id for rp in added_rp} == {"p-bill", "p-brand"}
    assert all(rp.role_id == "admin-1" for rp in added_rp)
    db.commit.assert_awaited()


@pytest.mark.asyncio
async def test_seed_permissions_tenant_custom_admin_role_not_synchronized():
    """TEST 2: Tenant custom role named Admin (is_system_role=False, organization_id='org-1') is NOT synchronized."""
    repo: Any = RoleRepository()
    db = AsyncMock(spec=AsyncSession)

    mock_res_keys = _make_result_mock(items=["organization:billing"])
    mock_res_admin = _make_result_mock(first_item=None)

    db.execute = AsyncMock(side_effect=[mock_res_keys, mock_res_admin])
    db.add = AsyncMock()
    db.commit = AsyncMock()

    await repo.seed_permissions(
        db,
        [
            {
                "key": "organization:billing",
                "name": "Manage Subscriptions",
                "category": "Organization",
                "description": "",
            }
        ],
    )

    added_rp = [
        call.args[0] for call in db.add.call_args_list if isinstance(call.args[0], RolePermission)
    ]
    assert len(added_rp) == 0


@pytest.mark.asyncio
async def test_seed_permissions_non_system_global_admin_not_synchronized():
    """TEST 3: Non-system global role named Admin (is_system_role=False, organization_id=None) is NOT synchronized."""
    repo: Any = RoleRepository()
    db = AsyncMock(spec=AsyncSession)

    mock_res_keys = _make_result_mock(items=["organization:billing"])
    mock_res_admin = _make_result_mock(first_item=None)

    db.execute = AsyncMock(side_effect=[mock_res_keys, mock_res_admin])
    db.add = AsyncMock()
    db.commit = AsyncMock()

    await repo.seed_permissions(
        db,
        [
            {
                "key": "organization:billing",
                "name": "Manage Subscriptions",
                "category": "Organization",
                "description": "",
            }
        ],
    )

    added_rp = [
        call.args[0] for call in db.add.call_args_list if isinstance(call.args[0], RolePermission)
    ]
    assert len(added_rp) == 0


@pytest.mark.asyncio
async def test_seed_permissions_only_standard_permissions_synchronized():
    """TEST 4: Only standard permissions are synchronized; custom/arbitrary permissions are NOT attached to Admin."""
    admin_role = _make_role(id="admin-1", name="Admin", is_system_role=True, organization_id=None)
    perm_std = type("P", (), {"id": "p-std", "key": "organization:billing"})()

    repo: Any = RoleRepository()
    db = AsyncMock(spec=AsyncSession)

    mock_res_keys = _make_result_mock(items=["organization:billing", "custom:arbitrary_perm"])
    mock_res_admin = _make_result_mock(first_item=admin_role)
    mock_res_perms = _make_result_mock(items=[perm_std])
    mock_res_rp = _make_result_mock(items=[])

    db.execute = AsyncMock(side_effect=[mock_res_keys, mock_res_admin, mock_res_perms, mock_res_rp])
    db.add = AsyncMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()

    await repo.seed_permissions(
        db,
        [
            {
                "key": "organization:billing",
                "name": "Manage Subscriptions",
                "category": "Organization",
                "description": "",
            }
        ],
    )

    added_rp = [
        call.args[0] for call in db.add.call_args_list if isinstance(call.args[0], RolePermission)
    ]
    assert len(added_rp) == 1
    assert added_rp[0].permission_id == "p-std"


@pytest.mark.asyncio
async def test_seed_permissions_existing_admin_mappings_remain_intact():
    """TEST 5: Existing Admin permission mappings remain intact and are not duplicated."""
    admin_role = _make_role(id="admin-1", name="Admin", is_system_role=True, organization_id=None)
    perm_existing = type("P", (), {"id": "p-existing", "key": "organization:read"})()
    perm_new = type("P", (), {"id": "p-new", "key": "organization:billing"})()

    repo: Any = RoleRepository()
    db = AsyncMock(spec=AsyncSession)

    mock_res_keys = _make_result_mock(items=["organization:read", "organization:billing"])
    mock_res_admin = _make_result_mock(first_item=admin_role)
    mock_res_perms = _make_result_mock(items=[perm_existing, perm_new])
    mock_res_rp = _make_result_mock(items=["p-existing"])

    db.execute = AsyncMock(side_effect=[mock_res_keys, mock_res_admin, mock_res_perms, mock_res_rp])
    db.add = AsyncMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()

    await repo.seed_permissions(
        db,
        [
            {
                "key": "organization:read",
                "name": "View Org",
                "category": "Organization",
                "description": "",
            },
            {
                "key": "organization:billing",
                "name": "Manage Subscriptions",
                "category": "Organization",
                "description": "",
            },
        ],
    )

    added_rp = [
        call.args[0] for call in db.add.call_args_list if isinstance(call.args[0], RolePermission)
    ]
    assert len(added_rp) == 1
    assert added_rp[0].permission_id == "p-new"


@pytest.mark.asyncio
async def test_seed_permissions_idempotency():
    """TEST 6: Synchronization is idempotent and produces no duplicates when run repeatedly."""
    admin_role = _make_role(id="admin-1", name="Admin", is_system_role=True, organization_id=None)
    perm_bill = type("P", (), {"id": "p-bill", "key": "organization:billing"})()

    repo: Any = RoleRepository()
    db = AsyncMock(spec=AsyncSession)

    mock_res_keys = _make_result_mock(items=["organization:billing"])
    mock_res_admin = _make_result_mock(first_item=admin_role)
    mock_res_perms = _make_result_mock(items=[perm_bill])
    mock_res_rp = _make_result_mock(items=["p-bill"])

    db.execute = AsyncMock(side_effect=[mock_res_keys, mock_res_admin, mock_res_perms, mock_res_rp])
    db.add = AsyncMock()
    db.commit = AsyncMock()

    await repo.seed_permissions(
        db,
        [
            {
                "key": "organization:billing",
                "name": "Manage Subscriptions",
                "category": "Organization",
                "description": "",
            }
        ],
    )

    added_rp = [
        call.args[0] for call in db.add.call_args_list if isinstance(call.args[0], RolePermission)
    ]
    assert len(added_rp) == 0


@pytest.mark.asyncio
async def test_seed_permissions_concurrency_savepoint_resilience():
    """TEST 7: IntegrityError on one item does not rollback outer transaction or lose other items."""
    from sqlalchemy.exc import IntegrityError

    admin_role = _make_role(id="admin-1", name="Admin", is_system_role=True, organization_id=None)
    perm_bill = type("P", (), {"id": "p-bill", "key": "organization:billing"})()

    repo: Any = RoleRepository()
    db = AsyncMock(spec=AsyncSession)

    mock_res_keys = _make_result_mock(items=[])
    mock_res_admin = _make_result_mock(first_item=admin_role)
    mock_res_perms = _make_result_mock(items=[perm_bill])
    mock_res_rp = _make_result_mock(items=[])

    db.execute = AsyncMock(side_effect=[mock_res_keys, mock_res_admin, mock_res_perms, mock_res_rp])

    # First flush (for item 1) raises IntegrityError from concurrent insert; second flush succeeds
    db.flush = AsyncMock(side_effect=[IntegrityError("stmt", "params", Exception()), None, None])
    db.commit = AsyncMock()

    await repo.seed_permissions(
        db,
        [
            {
                "key": "organization:billing",
                "name": "Manage Subscriptions",
                "category": "Organization",
                "description": "",
            },
            {
                "key": "organization:branding",
                "name": "Update Logo",
                "category": "Organization",
                "description": "",
            },
        ],
    )

    db.commit.assert_awaited()


def test_standard_permissions_catalog_superset_of_migration_catalog():
    """TEST 8: Ensure all keys in migration f9a0b1c2d3e4 are present in runtime ALL_STANDARD_PERMISSIONS."""
    import importlib.util
    from pathlib import Path

    migration_path = (
        Path(__file__).resolve().parents[3]
        / "alembic"
        / "versions"
        / "f9a0b1c2d3e4_sync_organization_and_admin_permissions.py"
    )
    spec = importlib.util.spec_from_file_location("migration_f9a0b1c2d3e4", str(migration_path))
    assert spec is not None and spec.loader is not None
    migration_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration_mod)

    runtime_keys = {p["key"] for p in ALL_STANDARD_PERMISSIONS}
    migration_keys = {p["key"] for p in migration_mod.STANDARD_PERMISSIONS}

    missing_in_runtime = migration_keys - runtime_keys
    assert not missing_in_runtime, (
        f"Migration contains keys not in runtime catalog: {missing_in_runtime}"
    )
