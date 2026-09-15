"""Regression coverage for the approved policy and repeated initialization."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.errors import APIException
from app.core.rbac_matrix import (
    APPROVED_PERMISSION_KEYS,
    RECORD_SCOPE_MODULES,
    SYSTEM_ROLE_PERMISSIONS,
    SYSTEM_ROLE_RECORD_SCOPES,
    canonical_system_role_name,
)
from app.repositories.role_repository import RoleRepository
from app.tests.mock_helpers import as_async_mock, as_mock, replace_attr


def test_approved_counts_and_read_only_policy():
    assert {name: len(keys) for name, keys in SYSTEM_ROLE_PERMISSIONS.items()} == {
        "Admin": 178,
        "Sales Manager": 111,
        "Sales Executive": 56,
        "Marketing Executive": 30,
        "Customer Support": 37,
        "Read Only": 20,
        "Project Manager": 26,
        "Project Member": 16,
        "Support Manager": 43,
        "Finance/Accounts": 20,
    }
    assert all(key.endswith(":read") for key in SYSTEM_ROLE_PERMISSIONS["Read Only"])
    for name, keys in SYSTEM_ROLE_PERMISSIONS.items():
        if name in {
            "Sales Manager",
            "Sales Executive",
            "Marketing Executive",
            "Customer Support",
            "Support Manager",
        }:
            assert "emails:send" in keys
    assert "leads:assign" not in SYSTEM_ROLE_PERMISSIONS["Sales Executive"]
    assert "api_keys:revoke" in SYSTEM_ROLE_PERMISSIONS["Admin"]
    assert all(
        "api_keys:revoke" not in keys
        for name, keys in SYSTEM_ROLE_PERMISSIONS.items()
        if name != "Admin"
    )
    assert "leads:convert" not in SYSTEM_ROLE_PERMISSIONS["Marketing Executive"]
    assert not any(
        key.startswith(("users:", "roles:", "organization:"))
        for key in SYSTEM_ROLE_PERMISSIONS["Sales Manager"]
    )
    assert not any(key.startswith("projects:") for key in SYSTEM_ROLE_PERMISSIONS["Sales Manager"])
    assert {
        "whatsapp:read_all",
        "whatsapp:assign",
        "whatsapp:manage_ai",
    }.isdisjoint(SYSTEM_ROLE_PERMISSIONS["Customer Support"])
    assert "whatsapp:read_all" in SYSTEM_ROLE_PERMISSIONS["Support Manager"]
    for role in ("Project Manager", "Project Member"):
        assert {"activities:read", "activities:create"}.issubset(SYSTEM_ROLE_PERMISSIONS[role])
    assert "projects:update" not in SYSTEM_ROLE_PERMISSIONS["Project Member"]


def test_system_role_record_scopes_are_complete_and_least_privilege():
    assert set(SYSTEM_ROLE_RECORD_SCOPES) == set(SYSTEM_ROLE_PERMISSIONS)
    assert all(
        set(scopes) == set(RECORD_SCOPE_MODULES) for scopes in SYSTEM_ROLE_RECORD_SCOPES.values()
    )
    assert set(SYSTEM_ROLE_RECORD_SCOPES["Admin"].values()) == {"all"}
    assert SYSTEM_ROLE_RECORD_SCOPES["Sales Manager"]["leads"] == "team"
    assert SYSTEM_ROLE_RECORD_SCOPES["Sales Executive"]["leads"] == "assigned"
    assert SYSTEM_ROLE_RECORD_SCOPES["Project Member"]["projects"] == "assigned"
    assert SYSTEM_ROLE_RECORD_SCOPES["Support Manager"]["tickets"] == "team"
    assert SYSTEM_ROLE_RECORD_SCOPES["Finance/Accounts"]["payments"] == "all"
    assert SYSTEM_ROLE_RECORD_SCOPES["Finance/Accounts"]["tickets"] == "none"


def test_rbac_backfill_migration_remains_a_frozen_policy_snapshot():
    migration_path = (
        Path(__file__).parents[3]
        / "alembic"
        / "versions"
        / "d0e1f2a3b4c5_backfill_core_rbac_roles.py"
    )
    spec = importlib.util.spec_from_file_location("rbac_backfill_migration", migration_path)
    assert spec and spec.loader
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    assert migration.ROLE_PERMISSIONS == SYSTEM_ROLE_PERMISSIONS
    # Historical migrations are immutable snapshots. New scope modules are
    # added by later additive migrations, so compare the original slice only.
    assert set(migration.RECORD_SCOPE_MODULES) < set(RECORD_SCOPE_MODULES)
    for role_name, historical_scopes in migration.ROLE_SCOPES.items():
        assert historical_scopes == {
            module: SYSTEM_ROLE_RECORD_SCOPES[role_name][module]
            for module in migration.RECORD_SCOPE_MODULES
        }
    assert migration.REMOVE_ROLE_PERMISSIONS["Project Member"] == {"projects:update"}


@pytest.mark.parametrize(
    "name",
    [
        " Admin ",
        "SUPER ADMIN",
        "super_admin",
        "Sales Executive",
        "Sales_Representative",
        "Support Agent",
        "Analyst / Viewer",
        "Finance / Accounts",
    ],
)
def test_custom_roles_cannot_recreate_system_names(name):
    with pytest.raises(APIException):
        RoleRepository.validate_custom_role_name(name)


@pytest.mark.parametrize(
    ("alias", "canonical"),
    [
        ("Sales Rep", "Sales Executive"),
        ("Support Agent", "Customer Support"),
        ("Viewer", "Read Only"),
        ("Finance / Accounts", "Finance/Accounts"),
    ],
)
def test_system_role_aliases_resolve_to_one_canonical_role(alias, canonical):
    assert canonical_system_role_name(alias) == canonical


def _result(values):
    result = MagicMock()
    as_mock(result.scalars).return_value = values
    return result


@pytest.mark.asyncio
async def test_repeated_initialization_preserves_scopes_and_only_restores_missing_grants():
    repository = RoleRepository()
    replace_attr(repository, "add_role_permission", AsyncMock())
    roles = [
        SimpleNamespace(id=name, name=name, organization_id="tenant-1")
        for name in SYSTEM_ROLE_PERMISSIONS
    ]
    roles.append(SimpleNamespace(id="Super Admin", name="Super Admin", organization_id=None))
    catalog = APPROVED_PERMISSION_KEYS | {"settings:database_reset"}
    permissions = [SimpleNamespace(id=key, key=key) for key in catalog]
    db = MagicMock()
    db.flush = AsyncMock()
    for first_run in (True, False):
        responses = [None, _result(roles), _result(permissions)]
        for role in roles:
            name = role.name
            keys = (
                APPROVED_PERMISSION_KEYS if name == "Super Admin" else SYSTEM_ROLE_PERMISSIONS[name]
            )
            existing = keys - {"emails:send"} if first_run and name == "Sales Executive" else keys
            responses.extend([None, _result(existing)])
        db.execute = AsyncMock(side_effect=responses)
        await repository.synchronize_system_roles(db)
    as_async_mock(repository.add_role_permission).assert_awaited_once_with(
        db, "Sales Executive", "emails:send"
    )
    db.add.assert_not_called()
    db.commit.assert_not_called()


@pytest.mark.asyncio
async def test_initialization_rejects_incomplete_catalog():
    db = MagicMock()
    db.execute = AsyncMock(
        side_effect=[
            None,
            _result([SimpleNamespace(id="super-admin", name="Super Admin", organization_id=None)]),
            _result([]),
        ]
    )
    with pytest.raises(APIException, match="catalog is incomplete"):
        await RoleRepository().synchronize_system_roles(db)
    db.add.assert_not_called()


@pytest.mark.asyncio
async def test_initialization_rejects_global_tenant_role():
    global_admin = SimpleNamespace(id="admin", name="Admin", organization_id=None)
    no_collision = MagicMock()
    as_mock(no_collision.scalar_one_or_none).return_value = None
    db = MagicMock()
    db.flush = AsyncMock()
    db.execute = AsyncMock(
        side_effect=[
            None,
            _result([global_admin]),
            _result([SimpleNamespace(id=key, key=key) for key in APPROVED_PERMISSION_KEYS]),
            no_collision,
        ]
    )

    with pytest.raises(APIException, match="Global tenant roles"):
        await RoleRepository().synchronize_system_roles(db)
