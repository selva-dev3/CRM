"""Regression coverage for the approved policy and repeated initialization."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.errors import APIException
from app.core.rbac_matrix import ADMIN_PERMISSIONS, SYSTEM_ROLE_PERMISSIONS
from app.repositories.role_repository import RoleRepository


def test_approved_counts_and_read_only_policy():
    assert {name: len(keys) for name, keys in SYSTEM_ROLE_PERMISSIONS.items()} == {
        "Admin": 149,
        "Sales Manager": 107,
        "Sales Executive": 50,
        "Marketing Executive": 30,
        "Customer Support": 29,
        "Read Only": 19,
    }
    assert all(key.endswith(":read") for key in SYSTEM_ROLE_PERMISSIONS["Read Only"])
    for name, keys in SYSTEM_ROLE_PERMISSIONS.items():
        assert ("emails:send" in keys) == (name != "Read Only")
    assert "leads:assign" not in SYSTEM_ROLE_PERMISSIONS["Sales Executive"]
    assert "leads:convert" not in SYSTEM_ROLE_PERMISSIONS["Marketing Executive"]
    assert not any(
        key.startswith(("users:", "roles:", "organization:"))
        for key in SYSTEM_ROLE_PERMISSIONS["Sales Manager"]
    )


@pytest.mark.parametrize("name", [" Admin ", "SUPER ADMIN", "super_admin", "Sales Executive"])
def test_custom_roles_cannot_recreate_system_names(name):
    with pytest.raises(APIException):
        RoleRepository.validate_custom_role_name(name)


def _result(values):
    result = MagicMock()
    result.scalars.return_value = values
    return result


@pytest.mark.asyncio
async def test_repeated_initialization_preserves_scopes_and_only_restores_missing_grants():
    repository = RoleRepository()
    repository.add_role_permission = AsyncMock()
    roles = [
        SimpleNamespace(id=name, name=name, organization_id="tenant-1")
        for name in SYSTEM_ROLE_PERMISSIONS
    ]
    roles.append(SimpleNamespace(id="Super Admin", name="Super Admin", organization_id=None))
    catalog = ADMIN_PERMISSIONS | {"super_admin:manage", "settings:database_reset"}
    permissions = [SimpleNamespace(id=key, key=key) for key in catalog]
    db = MagicMock()
    db.flush = AsyncMock()
    for first_run in (True, False):
        responses = [None, _result(roles), _result(permissions)]
        for name in sorted([*SYSTEM_ROLE_PERMISSIONS, "Super Admin"]):
            keys = catalog if name == "Super Admin" else SYSTEM_ROLE_PERMISSIONS[name]
            existing = keys - {"emails:send"} if first_run and name == "Sales Executive" else keys
            responses.extend([None, _result(existing)])
        db.execute = AsyncMock(side_effect=responses)
        await repository.synchronize_system_roles(db)
    repository.add_role_permission.assert_awaited_once_with(db, "Sales Executive", "emails:send")
    db.add.assert_not_called()
    db.commit.assert_not_called()


@pytest.mark.asyncio
async def test_initialization_rejects_incomplete_catalog():
    db = MagicMock()
    db.execute = AsyncMock(
        side_effect=[
            None,
            _result([SimpleNamespace(id="admin", name="Admin", organization_id=None)]),
            _result([]),
        ]
    )
    with pytest.raises(APIException, match="catalog is incomplete"):
        await RoleRepository().synchronize_system_roles(db)
    db.add.assert_not_called()
