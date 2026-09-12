from datetime import UTC, datetime
from typing import Any
from unittest.mock import ANY, AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIException, ForbiddenError, NotFoundError
from app.models import Role, RolePermission, User
from app.repositories.role_repository import RoleRepository
from app.schemas.crm_schemas import PermissionCreate, RoleCreate, RoleUpdate
from app.services.role_service import ALL_STANDARD_PERMISSIONS, RoleService


def _make_role(**overrides) -> Role:
    defaults = {
        "id": "role-1",
        "name": "Sales Manager",
        "description": "Manages sales team",
        "is_system_role": False,
        "organization_id": "org-1",
        "created_at": datetime(2026, 8, 5, tzinfo=UTC),
    }
    defaults.update(overrides)
    return Role(**defaults)


def _actor(**overrides) -> User:
    defaults = {
        "id": "admin-1",
        "name": "Admin",
        "email": "admin@crm.com",
        "hashed_password": "hashed",
        "role": "Admin",
        "organization_id": "org-1",
        "is_active": True,
    }
    defaults.update(overrides)
    return User(**defaults)


@pytest.mark.asyncio
async def test_list_roles_classifies_types():
    admin = _make_role(id="role-1", name="admin", is_system_role=True)
    repo: Any = RoleRepository()
    repo.get_setting = AsyncMock(return_value=None)
    repo.list_roles = AsyncMock(return_value=[admin])
    repo.get_permission_keys_by_role_ids = AsyncMock(
        return_value={"role-1": ["users:read", "leads:read"]}
    )
    service = RoleService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.list_roles(db, None)

    assert result[0]["type"] == "system"
    assert result[0]["permissions"] == ["leads:read", "users:read"]


@pytest.mark.asyncio
async def test_import_permissions_reports_failure_after_rollback():
    repo: Any = RoleRepository()
    repo.create_permission = AsyncMock(side_effect=RuntimeError("database unavailable"))
    service = RoleService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(APIException) as exc_info:
        await service.import_permissions_batch(
            db, [PermissionCreate(key="users:read", name="Read Users")]
        )

    assert exc_info.value.status_code == 400
    assert "No permissions were imported" in exc_info.value.message
    db.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_list_roles_forwards_org_id_to_repository():
    repo: Any = RoleRepository()
    repo.get_setting = AsyncMock(return_value=None)
    repo.list_roles = AsyncMock(return_value=[])
    repo.get_permission_keys_by_role_ids = AsyncMock(return_value={})
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
        await service.get_role(db, "missing", _actor())


@pytest.mark.asyncio
async def test_create_role_without_permissions(monkeypatch):
    role = _make_role()
    repo: Any = RoleRepository()
    repo.create_role = AsyncMock(return_value=role)
    service = RoleService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.create_role(
        db, RoleCreate(name="Sales Manager", permissions=[]), _actor()
    )

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
        db, RoleCreate(name="Sales Manager", permissions=["leads:read"]), _actor()
    )

    assert result["permissions"] == ["leads:read"]
    repo.add_role_permission.assert_awaited_with(db, "role-1", "p1")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "permission", ["all", "database:destroy", "organization:delete", "super_admin:manage"]
)
async def test_create_role_rejects_unapproved_permission(permission):
    repo: Any = RoleRepository()
    repo.create_role = AsyncMock()
    service = RoleService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(APIException) as exc:
        await service.create_role(
            db, RoleCreate(name="Unsafe", permissions=[permission]), _actor()
        )

    assert exc.value.code == "INVALID_PERMISSION_KEYS"
    repo.create_role.assert_not_awaited()
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_permission_reports_failure_after_rollback():
    repo: Any = RoleRepository()
    repo.create_permission = AsyncMock(return_value=None)
    service = RoleService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    async def commit_fail():
        raise RuntimeError

    db.commit = AsyncMock(side_effect=commit_fail)

    with pytest.raises(APIException):
        await service.create_permission(
            db, PermissionCreate(key="leads:read", name="Read leads")
        )
    db.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_set_multiple_default_roles():
    repo: Any = RoleRepository()
    repo.get_setting = AsyncMock(return_value=None)
    repo.upsert_setting = AsyncMock()
    service = RoleService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    repo.get_role_for_update = AsyncMock(
        side_effect=[_make_role(id="role-1"), _make_role(id="role-2")]
    )
    result = await service.set_multiple_default_roles(db, ["role-1", "role-2"], _actor())

    assert repo.upsert_setting.await_count == 2
    assert repo.upsert_setting.await_args_list[0].args[1] == "default_registration_roles:org-1"
    assert repo.upsert_setting.await_args_list[1].args[1] == "default_registration_role:org-1"
    assert "2 selected" in result["message"]
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_set_multiple_default_roles_locks_sorted_unique_ids_but_preserves_priority():
    repo: Any = RoleRepository()
    repo.get_setting = AsyncMock(return_value=None)
    repo.upsert_setting = AsyncMock()
    repo.get_role_for_update = AsyncMock(
        side_effect=lambda _db, role_id, _organization_id: _make_role(id=role_id)
    )
    service = RoleService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    await service.set_multiple_default_roles(
        db, ["role-2", "role-1", "role-2"], _actor()
    )

    assert [call.args[1] for call in repo.get_role_for_update.await_args_list] == [
        "role-1",
        "role-2",
    ]
    assert repo.upsert_setting.await_args_list[0].args[2] == '["role-2", "role-1"]'


@pytest.mark.asyncio
async def test_get_default_role_fails_closed_without_configured_role():
    repo: Any = RoleRepository()
    repo.get_setting = AsyncMock(return_value=None)
    repo.get_role_by_id_or_name = AsyncMock(return_value=None)
    repo.get_first_role = AsyncMock(return_value=None)
    service = RoleService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(APIException) as exc:
        await service.get_default_role(db, _actor())

    assert exc.value.code == "DEFAULT_ROLE_NOT_CONFIGURED"


@pytest.mark.asyncio
async def test_get_default_role_preserves_plural_setting_priority():
    preferred = _make_role(id="role-z", name="Preferred")
    plural = type("Setting", (), {"value": '["role-z", "role-a"]'})()
    repo: Any = RoleRepository()
    repo.get_setting = AsyncMock(side_effect=[None, plural])
    repo.get_role_by_id_or_name = AsyncMock(return_value=preferred)
    repo.get_role_permissions = AsyncMock(return_value=[])
    service = RoleService(repository=repo)

    result = await service.get_default_role(AsyncMock(spec=AsyncSession), _actor())

    assert result["id"] == "role-z"
    repo.get_role_by_id_or_name.assert_awaited_once_with(
        ANY, "role-z", organization_id="org-1"
    )


@pytest.mark.asyncio
async def test_list_system_roles_is_scoped_to_current_organization():
    repo: Any = RoleRepository()
    repo.get_setting = AsyncMock(return_value=None)
    repo.get_system_roles = AsyncMock(return_value=[])
    repo.get_permission_keys_by_role_ids = AsyncMock(return_value={})
    service = RoleService(repository=repo)

    await service.list_system_roles(AsyncMock(spec=AsyncSession), _actor())

    repo.get_system_roles.assert_awaited_once_with(ANY, "org-1")


@pytest.mark.asyncio
async def test_delete_role_blocks_default(monkeypatch):
    role = _make_role()
    repo: Any = RoleRepository()
    repo.get_role_by_id_or_name = AsyncMock(return_value=role)
    repo.get_role_for_update = AsyncMock(return_value=role)
    service = RoleService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    async def fake_default_ids(db, organization_id=None):
        return {"role-1"}

    monkeypatch.setattr(service, "_get_default_role_ids", fake_default_ids)

    with pytest.raises(APIException):
        await service.delete_role(db, "role-1", _actor())


@pytest.mark.asyncio
async def test_check_permission_global_role_mapping_fails_closed_for_tenant():
    role = _make_role(name="Super Admin", is_system_role=True, organization_id=None)
    super_perm = type("P", (), {"key": "super_admin:manage"})()
    user = type("U", (), {"id": "u1", "role": "role-1", "email": "a@b.com", "name": "A"})()
    repo: Any = RoleRepository()
    repo.get_user_by_id_or_email = AsyncMock(return_value=user)
    repo.get_user_role_mapping = AsyncMock(return_value=None)
    repo.get_role_by_id_or_name = AsyncMock(return_value=role)
    repo.get_role_permissions = AsyncMock(return_value=[super_perm])
    service = RoleService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    user.organization_id = "org-1"
    result = await service.check_permission(db, "u1", "anything:x", _actor())

    assert result["allowed"] is False


@pytest.mark.asyncio
async def test_check_permission_requires_exact_key():
    role = _make_role(name="Sales Manager", is_system_role=False)
    perm = type("P", (), {"key": "deals:read"})()
    user = type("U", (), {"id": "u1", "role": "role-1", "email": "a@b.com", "name": "A"})()
    repo: Any = RoleRepository()
    repo.get_user_by_id_or_email = AsyncMock(return_value=user)
    repo.get_user_role_mapping = AsyncMock(return_value=None)
    repo.get_role_by_id_or_name = AsyncMock(return_value=role)
    repo.get_role_permissions = AsyncMock(return_value=[perm])
    service = RoleService(repository=repo)
    service.authorization_service.get_user_permissions = AsyncMock(
        return_value=["deals:read"]
    )
    db = AsyncMock(spec=AsyncSession)

    user.organization_id = "org-1"
    granted = await service.check_permission(db, "u1", "deals:read", _actor())
    denied = await service.check_permission(db, "u1", "deals:delete", _actor())

    assert granted["allowed"] is True
    assert denied["allowed"] is False


@pytest.mark.asyncio
async def test_check_permission_denies_admin_name_role_without_grants():
    """An 'Admin'-named role must NOT be granted everything by name alone."""
    role = _make_role(name="Admin", is_system_role=True)
    user = type("U", (), {"id": "u1", "role": "role-1", "email": "a@b.com", "name": "A"})()
    repo: Any = RoleRepository()
    repo.get_user_by_id_or_email = AsyncMock(return_value=user)
    repo.get_user_role_mapping = AsyncMock(return_value=None)
    repo.get_role_by_id_or_name = AsyncMock(return_value=role)
    repo.get_role_permissions = AsyncMock(return_value=[])
    service = RoleService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    user.organization_id = "org-1"
    result = await service.check_permission(db, "u1", "anything:x", _actor())

    assert result["allowed"] is False


@pytest.mark.asyncio
async def test_check_permission_denies_unknown_role():
    user = type("U", (), {"id": "u1", "role": "ghost-role", "email": "a@b.com", "name": "A"})()
    repo: Any = RoleRepository()
    repo.get_user_by_id_or_email = AsyncMock(return_value=user)
    repo.get_user_role_mapping = AsyncMock(return_value=None)
    repo.get_role_by_id_or_name = AsyncMock(return_value=None)
    service = RoleService(repository=repo)
    service.authorization_service.get_user_permissions = AsyncMock(return_value=[])
    db = AsyncMock(spec=AsyncSession)

    user.organization_id = "org-1"
    result = await service.check_permission(db, "u1", "leads:read", _actor())

    assert result["allowed"] is False


@pytest.mark.asyncio
async def test_list_roles_filters_unknown_and_platform_permissions():
    admin = _make_role(id="role-admin", name="Admin", is_system_role=True)
    assigned_keys = ["leads:read", "leads:update", "unknown:permission", "super_admin:manage"]
    repo: Any = RoleRepository()
    repo.get_setting = AsyncMock(return_value=None)
    repo.list_roles = AsyncMock(return_value=[admin])
    repo.get_permission_keys_by_role_ids = AsyncMock(
        return_value={"role-admin": assigned_keys}
    )
    service = RoleService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.list_roles(db, None)

    assert result[0]["permissions"] == ["leads:read", "leads:update"]


@pytest.mark.asyncio
async def test_permission_matrix_excludes_platform_only_permissions():
    repo: Any = RoleRepository()
    repo.get_permission_matrix = AsyncMock(
        return_value=[
            type("P", (), {"id": "p1", "key": "leads:read", "name": "Read", "category": "Leads", "description": ""})(),
            type("P", (), {"id": "p2", "key": "organization:delete", "name": "Delete org", "category": "Organization", "description": ""})(),
            type("P", (), {"id": "p3", "key": "super_admin:manage", "name": "Platform", "category": "Platform", "description": ""})(),
        ]
    )

    result = await RoleService(repository=repo).get_permission_matrix(
        AsyncMock(spec=AsyncSession)
    )

    assert [item["key"] for item in result] == ["leads:read"]


@pytest.mark.asyncio
async def test_tenant_role_endpoint_does_not_expose_global_super_admin_role():
    role = _make_role(id="sys-1", name="super_admin", is_system_role=True, organization_id=None)
    all_db_keys = [f"perm:{i:03d}" for i in range(194)]
    repo: Any = RoleRepository()
    repo.get_role = AsyncMock(return_value=role)
    repo.get_permission_keys = AsyncMock(return_value=all_db_keys)
    repo.get_role_permissions = AsyncMock(
        return_value=[type("P", (), {"key": "super_admin:manage"})()]
    )
    service = RoleService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(NotFoundError):
        await service.get_role(db, "sys-1", _actor())


@pytest.mark.asyncio
async def test_tenant_role_named_super_admin_resolves_only_assigned_keys():
    role = _make_role(id="tenant-super", name="Super Admin", organization_id="org-1")
    assigned = [type("P", (), {"key": "dashboard:read"})()]
    repo: Any = RoleRepository()
    repo.get_role = AsyncMock(return_value=role)
    repo.get_permission_keys = AsyncMock(return_value=["dashboard:read", "roles:update"])
    repo.get_role_permissions = AsyncMock(return_value=assigned)
    service = RoleService(repository=repo)

    result = await service.get_role(AsyncMock(spec=AsyncSession), "tenant-super", _actor())

    assert result["permissions"] == ["dashboard:read"]


@pytest.mark.asyncio
async def test_check_permission_admin_holding_super_admin_manage_denies_unassigned():
    """Admin holding super_admin:manage only passes for keys explicitly assigned (fail closed)."""
    role = _make_role(name="Admin", is_system_role=True)
    perms = [type("P", (), {"key": "super_admin:manage"}), type("P", (), {"key": "deals:read"})]
    user = type("U", (), {"id": "u1", "role": "role-1", "email": "a@b.com", "name": "A"})()
    repo: Any = RoleRepository()
    repo.get_user_by_id_or_email = AsyncMock(return_value=user)
    repo.get_user_role_mapping = AsyncMock(return_value=None)
    repo.get_role_by_id_or_name = AsyncMock(return_value=role)
    repo.get_role_permissions = AsyncMock(return_value=perms)
    service = RoleService(repository=repo)
    service.authorization_service.get_user_permissions = AsyncMock(
        return_value=["deals:read"]
    )
    db = AsyncMock(spec=AsyncSession)

    user.organization_id = "org-1"
    granted = await service.check_permission(db, "u1", "deals:read", _actor())
    denied = await service.check_permission(db, "u1", "anything:x", _actor())

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

    result = await service.get_role(db, "sys-2", _actor())

    assert result["permissions"] == []


@pytest.mark.asyncio
async def test_update_role_partial():
    role = _make_role()
    repo: Any = RoleRepository()
    repo.get_role = AsyncMock(return_value=role)
    repo.get_role_for_update = AsyncMock(return_value=role)
    repo.get_role_reference_kinds = AsyncMock(return_value=[])
    repo.get_role_permission_ids = AsyncMock(return_value=[])
    repo.get_role_permissions = AsyncMock(return_value=[])
    repo.get_permissions_by_keys_or_ids = AsyncMock(
        return_value=[type("P", (), {"id": "p1", "key": "leads:read"})()]
    )
    repo.add_role_permission = AsyncMock()
    service = RoleService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.update_role(
        db, "role-1", RoleUpdate(name="New Name", permissions=["leads:read"]), _actor()
    )

    assert role.name == "New Name"
    assert result["name"] == "New Name"
    db.commit.assert_awaited()


@pytest.mark.asyncio
async def test_update_role_rejects_rename_when_legacy_references_exist():
    role = _make_role(name="Regional Sales")
    repo: Any = RoleRepository()
    repo.get_role = AsyncMock(return_value=role)
    repo.get_role_for_update = AsyncMock(return_value=role)
    repo.get_role_permissions = AsyncMock(return_value=[])
    repo.get_role_reference_kinds = AsyncMock(
        return_value=["users", "user invitations", "default role settings"]
    )
    service = RoleService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(APIException) as exc_info:
        await service.update_role(
            db, role.id, RoleUpdate(name="Renamed Sales"), _actor()
        )

    assert exc_info.value.code == "ROLE_IN_USE"
    assert role.name == "Regional Sales"
    db.rollback.assert_awaited_once()
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_clone_role_copies_permissions():
    role = _make_role()
    orig_perms = [type("P", (), {"id": "p1", "key": "leads:read"})()]
    repo: Any = RoleRepository()
    repo.get_role_for_update = AsyncMock(return_value=role)
    repo.create_role = AsyncMock(return_value=_make_role(id="role-2", name="Cloned"))
    repo.get_role_permissions = AsyncMock(return_value=orig_perms)
    repo.record_scopes = AsyncMock(
        return_value=[type("Scope", (), {"module": "leads", "scope": "team"})()]
    )
    repo.replace_record_scopes = AsyncMock()
    repo.add_role_permission = AsyncMock()
    service = RoleService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.clone_role(db, "role-1", "Cloned", _actor())

    assert result["name"] == "Cloned"
    assert result["permissions"] == ["leads:read"]
    repo.add_role_permission.assert_awaited_once()
    scopes = repo.replace_record_scopes.await_args.args[2]
    assert {item["module"]: item["scope"] for item in scopes}["leads"] == "team"
    repo.get_role_for_update.assert_awaited_once_with(ANY, "role-1", "org-1")


@pytest.mark.asyncio
async def test_assign_permissions_not_found():
    repo: Any = RoleRepository()
    repo.get_role = AsyncMock(return_value=None)
    service = RoleService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(NotFoundError):
        await service.assign_permissions(db, "missing", ["a:b"], _actor())


@pytest.mark.asyncio
async def test_assign_permissions_locks_role_before_reading_and_mutating():
    role = _make_role()
    permission = type("P", (), {"id": "permission-1", "key": "leads:read"})()
    repo: Any = RoleRepository()
    repo.get_role = AsyncMock(return_value=role)
    repo.get_role_for_update = AsyncMock(return_value=role)
    repo.get_permissions_by_keys_or_ids = AsyncMock(return_value=[permission])
    repo.get_role_permissions = AsyncMock(return_value=[])
    repo.get_role_permission_ids = AsyncMock(return_value=[])
    repo.add_role_permission = AsyncMock()
    service = RoleService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.assign_permissions(
        db, role.id, [permission.key], _actor()
    )

    assert result["status"] == "success"
    repo.get_role_for_update.assert_awaited_once_with(db, role.id, "org-1")
    repo.add_role_permission.assert_awaited_once_with(db, role.id, permission.id)


@pytest.mark.asyncio
async def test_get_role_users_rejects_unknown_role():
    repo: Any = RoleRepository()
    repo.get_role_by_id_or_name = AsyncMock(return_value=None)
    repo.get_users_by_role = AsyncMock(return_value=[])
    repo.get_users_by_user_role_id = AsyncMock(return_value=[])
    service = RoleService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(NotFoundError):
        await service.get_role_users(db, "unknown", _actor())


@pytest.mark.asyncio
async def test_get_user_role_prefers_mapping_over_stale_user_field():
    user = _actor(id="user-2", role="stale-role")
    mapped_role = _make_role(id="admin-role", name="Admin")
    repo: Any = RoleRepository()
    repo.get_user_by_id_or_email = AsyncMock(return_value=user)
    repo.get_user_role_mapping = AsyncMock(
        return_value=type("Mapping", (), {"role_id": mapped_role.id})()
    )
    repo.get_role_by_id_or_name = AsyncMock(return_value=mapped_role)
    repo.get_role_permissions = AsyncMock(return_value=[])
    service = RoleService(repository=repo)

    result = await service.get_user_role(
        AsyncMock(spec=AsyncSession), user.id, _actor()
    )

    assert result["id"] == mapped_role.id
    repo.get_role_by_id_or_name.assert_awaited_once_with(
        ANY, mapped_role.id, organization_id="org-1"
    )


@pytest.mark.asyncio
async def test_set_default_role_adds_and_removes():
    role = _make_role()
    repo: Any = RoleRepository()
    repo.get_role_by_id_or_name = AsyncMock(return_value=role)
    repo.get_role_for_update = AsyncMock(return_value=role)
    repo.get_setting = AsyncMock(return_value=None)
    repo.upsert_setting = AsyncMock()
    service = RoleService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.set_default_role(db, "role-1", _actor())
    assert "added as default" in result["message"]

    repo.get_setting = AsyncMock(return_value=type("S", (), {"value": '["role-1"]'})())
    result2 = await service.set_default_role(db, "role-1", _actor())
    assert "removed from default" in result2["message"]
    assert all(call.args[1].endswith(":org-1") for call in repo.upsert_setting.await_args_list)
    assert repo.upsert_setting.await_args_list[-1].args[2] == ""
    assert db.add.call_count == 2


@pytest.mark.asyncio
async def test_role_audit_logs_expose_role_name_from_persisted_details():
    log = type(
        "Log",
        (),
        {
            "id": "audit-1",
            "action": "ROLE_UPDATED",
            "user_id": "admin-1",
            "created_at": datetime(2026, 8, 5, tzinfo=UTC),
            "details": '{"target_id":"role-1","after":{"name":"Regional Sales"}}',
        },
    )()
    result_proxy = MagicMock()
    result_proxy.scalars.return_value.all.return_value = [log]
    db = AsyncMock(spec=AsyncSession)
    db.execute.return_value = result_proxy

    result = await RoleService().role_audit_logs(db, _actor())

    assert result[0]["role_name"] == "Regional Sales"
    assert result[0]["details"]["target_id"] == "role-1"


@pytest.mark.asyncio
@pytest.mark.parametrize("is_system_role", [True, False])
async def test_sales_manager_assignment_ignores_system_role_flag(is_system_role, monkeypatch):
    target = _actor(id="user-2", name="Seller", email="seller@crm.com", role="old-role")
    role = _make_role(
        id="sales-manager",
        name="Sales Manager",
        organization_id="org-1",
        is_system_role=is_system_role,
    )
    mapping = type("Mapping", (), {"role_id": "old-role"})()
    repo: Any = RoleRepository()
    repo.get_user_by_id_or_email = AsyncMock(return_value=target)
    repo.get_role_by_id_or_name = AsyncMock(return_value=role)
    repo.get_role_for_update = AsyncMock(return_value=role)
    repo.get_user_role_mapping = AsyncMock(return_value=mapping)
    repo.replace_user_role = AsyncMock()
    service = RoleService(repository=repo)
    db = AsyncMock(spec=AsyncSession)
    monkeypatch.setattr(
        "app.repositories.user_repository.UserRepository.lock_active_by_org",
        AsyncMock(return_value=[target]),
    )
    monkeypatch.setattr(
        "app.repositories.user_repository.UserRepository.effective_role_names_for_users",
        AsyncMock(return_value={target.id: "Sales Executive"}),
    )

    result = await service.assign_role_to_user(db, target.id, role.id, _actor())

    assert result["status"] == "success"
    assert target.role == role.id
    repo.replace_user_role.assert_awaited_once_with(db, target.id, role.id)
    repo.get_role_by_id_or_name.assert_awaited_once_with(db, role.id, organization_id="org-1")
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_assign_role_remaps_legacy_global_uuid_with_tenant_context(monkeypatch):
    target = _actor(id="user-2", email="seller@crm.com", role="old-role")
    scoped_role = _make_role(id="scoped-admin", name="Admin", organization_id="org-1")
    mapping = type("Mapping", (), {"role_id": "old-role"})()
    repo: Any = RoleRepository()
    repo.get_user_by_id_or_email = AsyncMock(return_value=target)

    async def resolve_role(db, role_id, *, organization_id=None):
        assert role_id == "legacy-global-admin"
        assert organization_id == "org-1"
        return scoped_role

    repo.get_role_by_id_or_name = AsyncMock(side_effect=resolve_role)
    repo.get_role_for_update = AsyncMock(return_value=scoped_role)
    repo.get_user_role_mapping = AsyncMock(return_value=mapping)
    repo.replace_user_role = AsyncMock()
    service = RoleService(repository=repo)
    db = AsyncMock(spec=AsyncSession)
    monkeypatch.setattr(
        "app.repositories.user_repository.UserRepository.lock_active_by_org",
        AsyncMock(return_value=[target]),
    )
    monkeypatch.setattr(
        "app.repositories.user_repository.UserRepository.effective_role_names_for_users",
        AsyncMock(return_value={target.id: "Sales Executive"}),
    )

    await service.assign_role_to_user(
        db, target.id, "legacy-global-admin", _actor(organization_id="org-1")
    )

    assert target.role == scoped_role.id
    repo.replace_user_role.assert_awaited_once_with(db, target.id, scoped_role.id)
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_assign_role_rejects_cross_organization_role():
    target = _actor(id="user-2", email="seller@crm.com")
    foreign_role = _make_role(id="foreign-role", organization_id="org-2")
    repo: Any = RoleRepository()
    repo.get_user_by_id_or_email = AsyncMock(return_value=target)
    repo.get_role_by_id_or_name = AsyncMock(return_value=foreign_role)
    service = RoleService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(NotFoundError):
        await service.assign_role_to_user(db, target.id, foreign_role.id, _actor())
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_assign_role_rejects_cross_organization_user():
    target = _actor(id="user-2", email="seller@other.com", organization_id="org-2")
    role = _make_role(id="sales-manager")
    repo: Any = RoleRepository()
    repo.get_user_by_id_or_email = AsyncMock(return_value=target)
    repo.get_role_by_id_or_name = AsyncMock(return_value=role)
    service = RoleService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(NotFoundError):
        await service.assign_role_to_user(db, target.id, role.id, _actor())
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_non_super_admin_cannot_assign_super_admin(monkeypatch):
    target = _actor(id="user-2", email="seller@crm.com")
    role = _make_role(
        id="super-admin", name="Super Admin", organization_id=None, is_system_role=True
    )
    repo: Any = RoleRepository()
    repo.get_user_by_id_or_email = AsyncMock(return_value=target)
    repo.get_role_by_id_or_name = AsyncMock(return_value=role)
    service = RoleService(repository=repo)
    db = AsyncMock(spec=AsyncSession)
    monkeypatch.setattr(
        "app.services.role_service.is_super_admin_user", AsyncMock(return_value=False)
    )

    with pytest.raises(NotFoundError):
        await service.assign_role_to_user(db, target.id, role.id, _actor())
    db.commit.assert_not_awaited()


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
        await service.update_role(db, "sys-1", RoleUpdate(name="New Name"), _actor())
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
        await service.update_role(db, "sys-1", RoleUpdate(permissions=["leads:read"]), _actor())
    _assert_forbidden(excinfo)
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_system_role_forbidden():
    role = _system_role()
    repo: Any = RoleRepository()
    repo.get_role_by_id_or_name = AsyncMock(return_value=role)
    repo.get_role_for_update = AsyncMock(return_value=role)
    repo.get_role_reference_kinds = AsyncMock(return_value=[])
    repo.delete_role = AsyncMock()
    service = RoleService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    async def fake_default_ids(db, organization_id=None):
        return set()

    from unittest.mock import patch

    with (
        patch.object(service, "_get_default_role_ids", fake_default_ids),
        pytest.raises(ForbiddenError) as excinfo,
    ):
        await service.delete_role(db, "sys-1", _actor())
    _assert_forbidden(excinfo)
    repo.delete_role.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_normal_role_succeeds():
    role = _make_role(id="role-1", name="Sales Manager")
    repo: Any = RoleRepository()
    repo.get_role_by_id_or_name = AsyncMock(return_value=role)
    repo.get_role_for_update = AsyncMock(return_value=role)
    repo.get_role_reference_kinds = AsyncMock(return_value=[])
    repo.delete_role = AsyncMock()
    service = RoleService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    async def fake_default_ids(db, organization_id=None):
        return set()

    from unittest.mock import patch

    with patch.object(service, "_get_default_role_ids", fake_default_ids):
        result = await service.delete_role(db, "role-1", _actor())

    assert result["status"] == "success"
    repo.delete_role.assert_awaited_once_with(db, role)


@pytest.mark.asyncio
async def test_delete_role_blocks_legacy_and_invitation_references():
    role = _make_role(id="role-1", name="Regional Seller")
    repo: Any = RoleRepository()
    repo.get_role_by_id_or_name = AsyncMock(return_value=role)
    repo.get_role_for_update = AsyncMock(return_value=role)
    repo.get_setting = AsyncMock(return_value=None)
    repo.get_role_reference_kinds = AsyncMock(
        return_value=["users", "user invitations", "default role settings"]
    )
    repo.delete_role = AsyncMock()
    service = RoleService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(APIException) as exc_info:
        await service.delete_role(db, role.id, _actor())

    assert exc_info.value.code == "ROLE_IN_USE"
    repo.get_role_for_update.assert_awaited_once_with(db, role.id, "org-1")
    repo.delete_role.assert_not_awaited()


@pytest.mark.asyncio
async def test_role_reference_check_uses_exact_default_role_values():
    role = _make_role(id="sales-role", name="Sales")
    db = AsyncMock(spec=AsyncSession)
    db.scalar = AsyncMock(return_value=None)
    settings_result = MagicMock()
    settings_result.scalars.return_value = [
        type(
            "Setting",
            (),
            {
                "key": "default_registration_roles:org-1",
                "value": '["sales-manager-role", "Sales Manager"]',
            },
        )()
    ]
    db.execute = AsyncMock(return_value=settings_result)

    references = await RoleRepository().get_role_reference_kinds(db, role)

    assert references == []


@pytest.mark.asyncio
async def test_role_assignment_blocks_last_admin_demotion(monkeypatch):
    target = _actor(id="admin-2", role="Admin")
    replacement = _make_role(id="read-only", name="Read Only")
    repo: Any = RoleRepository()
    repo.get_user_by_id_or_email = AsyncMock(return_value=target)
    repo.get_role_by_id_or_name = AsyncMock(return_value=replacement)
    repo.get_role_for_update = AsyncMock(return_value=replacement)
    repo.replace_user_role = AsyncMock()
    guard = AsyncMock(
        side_effect=APIException(
            status_code=409,
            code="LAST_ADMIN_DEACTIVATION_FORBIDDEN",
            message="last admin",
        )
    )
    monkeypatch.setattr(
        "app.services.user_service.UserService._ensure_not_last_admin", guard
    )

    with pytest.raises(APIException):
        await RoleService(repository=repo).assign_role_to_user(
            AsyncMock(spec=AsyncSession), target.id, replacement.id, _actor()
        )

    repo.replace_user_role.assert_not_awaited()


@pytest.mark.asyncio
async def test_assign_permissions_to_system_role_forbidden():
    role = _system_role()
    repo: Any = RoleRepository()
    repo.get_role = AsyncMock(return_value=role)
    repo.delete_role_permission = AsyncMock()
    service = RoleService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(ForbiddenError) as excinfo:
        await service.assign_permissions(db, "sys-1", ["leads:read"], _actor())
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
        await service.remove_permission(db, "sys-1", "p1", _actor())
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
    repo.get_role_for_update = AsyncMock(
        side_effect=lambda db, role_id, organization_id: role if role_id == "role-1" else sys_role
    )
    repo.delete_role = AsyncMock()
    service = RoleService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    async def fake_default_ids(db, organization_id=None):
        return set()

    from unittest.mock import patch

    with (
        patch.object(service, "_get_default_role_ids", fake_default_ids),
        pytest.raises(ForbiddenError) as excinfo,
    ):
        await service.bulk_delete_roles(db, ["role-1", "sys-1"], _actor())
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
    repo.get_role_for_update = AsyncMock(
        side_effect=lambda db, role_id, organization_id: role
        if role_id == "role-1"
        else default_role
    )
    repo.delete_role = AsyncMock()
    repo.get_role_reference_kinds = AsyncMock(return_value=[])
    service = RoleService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    async def fake_default_ids(db, organization_id=None):
        return {"role-2"}

    from unittest.mock import patch

    with patch.object(service, "_get_default_role_ids", fake_default_ids):
        result = await service.bulk_delete_roles(db, ["role-1", "role-2"], _actor())

    assert result["affected_count"] == 1
    repo.delete_role.assert_awaited_once_with(db, role)


@pytest.mark.asyncio
async def test_bulk_delete_roles_locks_sorted_unique_ids():
    roles = {role_id: _make_role(id=role_id, name=f"Custom {role_id}") for role_id in ("a", "b")}
    repo: Any = RoleRepository()
    repo.get_role_for_update = AsyncMock(
        side_effect=lambda _db, role_id, _organization_id: roles[role_id]
    )
    repo.get_role_reference_kinds = AsyncMock(return_value=[])
    repo.delete_role = AsyncMock()
    service = RoleService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    from unittest.mock import patch

    with patch.object(service, "_get_default_role_ids", AsyncMock(return_value=set())):
        result = await service.bulk_delete_roles(db, ["b", "a", "b"], _actor())

    assert [call.args[1] for call in repo.get_role_for_update.await_args_list] == ["a", "b"]
    assert result["affected_count"] == 2
    assert repo.delete_role.await_count == 2


def _make_result_mock(items=None, first_item=None) -> MagicMock:
    res = MagicMock()
    res.scalars.return_value.all.return_value = items if items is not None else []
    res.scalars.return_value.first.return_value = first_item
    return res


@pytest.mark.asyncio
async def test_seed_permissions_does_not_grant_global_admin_role():
    """Permission seeding never grants a legacy global tenant Admin role."""
    admin_role = _make_role(id="admin-1", name="Admin", is_system_role=True, organization_id=None)
    perm_bill = type("P", (), {"id": "p-bill", "key": "organization:billing"})()
    perm_brand = type("P", (), {"id": "p-brand", "key": "organization:branding"})()

    repo: Any = RoleRepository()
    db = AsyncMock(spec=AsyncSession)

    mock_res_keys = _make_result_mock(
        items=["dashboard:read", "organization:billing", "organization:branding"]
    )
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
    assert len(added_rp) == 0
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
async def test_seed_permissions_does_not_attach_permissions_to_global_admin():
    """Approved and arbitrary catalog rows are never attached during seeding."""
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
    assert len(added_rp) == 0


@pytest.mark.asyncio
async def test_seed_permissions_does_not_modify_existing_admin_mappings():
    """Existing legacy Admin mappings are left for the integrity migration."""
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
    assert len(added_rp) == 0


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
async def test_seed_permissions_can_stage_without_committing():
    repo: Any = RoleRepository()
    db = AsyncMock(spec=AsyncSession)
    db.execute = AsyncMock(
        side_effect=[_make_result_mock(items=[]), _make_result_mock(first_item=None)]
    )

    await repo.seed_permissions(db, [], commit=False)

    db.commit.assert_not_awaited()
    db.rollback.assert_not_awaited()


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
    assert (
        not missing_in_runtime
    ), f"Migration contains keys not in runtime catalog: {missing_in_runtime}"


@pytest.mark.asyncio
async def test_role_lookup_does_not_fallback_to_global_role():
    global_role = _make_role(
        id="global-admin", name="Admin", organization_id=None, is_system_role=True
    )
    scoped_role = _make_role(
        id="scoped-admin", name="Admin", organization_id="org-1", is_system_role=True
    )
    db = AsyncMock(spec=AsyncSession)
    db.scalar = AsyncMock(side_effect=[None, global_role, scoped_role])

    role = await RoleRepository().get_role_by_id_or_name(
        db, "global-admin", organization_id="org-1"
    )

    assert role is None
    assert db.scalar.await_count == 1
