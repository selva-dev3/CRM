"""Exercise the scoped repair and original migration on disposable PostgreSQL."""

import asyncio
import json
import os
from pathlib import Path
from uuid import uuid4

import asyncpg
import pytest
from alembic import command
from alembic.config import Config
from scripts.prepare_tenant_admin_repair import (
    CUSTOM_KEYS,
    CUSTOM_ORG_ID,
    CUSTOM_ROLE_ID,
    GLOBAL_ADMIN,
    INVITATION_ID,
    TARGETS,
    build_sql,
)
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError

from app.core.config import settings
from app.core.rbac_matrix import ADMIN_PERMISSIONS, PLATFORM_PERMISSIONS


@pytest.fixture(params=["approved", "reviewed_legacy"])
async def repair_database(monkeypatch, request):
    url = os.getenv("CRM_WORKFLOW_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set CRM_WORKFLOW_TEST_DATABASE_URL to the isolated local test database")
    parsed = make_url(url)
    assert parsed.host in {"localhost", "127.0.0.1"}
    assert parsed.database == "crm_workflow_test"
    database = f"rbac_repair_{uuid4().hex}"
    root = await asyncpg.connect(parsed.set(drivername="postgresql").render_as_string(False))
    await root.execute(f'CREATE DATABASE "{database}"')
    isolated = parsed.set(database=database)
    monkeypatch.setattr(settings, "DATABASE_URL", isolated.render_as_string(False))
    config = Config()
    config.set_main_option("script_location", str(Path(__file__).resolve().parents[3] / "alembic"))
    connection = None
    try:
        await asyncio.to_thread(command.upgrade, config, "t4d5e6f7a8b9")
        connection = await asyncpg.connect(
            isolated.set(drivername="postgresql").render_as_string(False)
        )
        await connection.execute("DELETE FROM roles; DELETE FROM permissions;")
        await connection.execute(
            "INSERT INTO roles (id,name,is_system_role) VALUES ($1,'Admin',true),"
            "('super','Super Admin',true),('custom','Custom',false)",
            GLOBAL_ADMIN,
        )
        legacy = request.param == "reviewed_legacy"
        source_grants = (
            (ADMIN_PERMISSIONS - {"api_keys:revoke"}) | {"organization:delete"}
            if legacy
            else ADMIN_PERMISSIONS
        )
        catalog = (ADMIN_PERMISSIONS | PLATFORM_PERMISSIONS) - (
            {"api_keys:revoke"} if legacy else set()
        )
        for key in sorted(catalog):
            await connection.execute(
                "INSERT INTO permissions (id,key,name,category) VALUES ($1,$1,$1,'test')", key
            )
            await connection.execute(
                "INSERT INTO role_permissions (id,role_id,permission_id) VALUES ($1,'super',$2)",
                f"super:{key}",
                key,
            )
            if key in source_grants:
                await connection.execute(
                    "INSERT INTO role_permissions (id,role_id,permission_id) VALUES ($1,$2,$3)",
                    f"admin:{key}",
                    GLOBAL_ADMIN,
                    key,
                )
        await connection.execute(
            "INSERT INTO role_permissions (id,role_id,permission_id) "
            "VALUES ('custom-read','custom','dashboard:read')"
        )
        for user, organization in TARGETS:
            await connection.execute(
                "INSERT INTO organizations (id,name,is_active,status) VALUES ($1,$1,true,'active')",
                organization,
            )
            await connection.execute(
                "INSERT INTO users (id,name,email,hashed_password,role,organization_id,"
                "is_platform_admin,is_active,is_verified) VALUES ($1,$1,$2,'test-hash',$3,$4,false,true,true)",
                user,
                f"{user}@example.com",
                GLOBAL_ADMIN,
                organization,
            )
            await connection.execute(
                "INSERT INTO user_roles (id,user_id,role_id) VALUES ($1,$1,$2)", user, GLOBAL_ADMIN
            )
        await connection.execute(
            "INSERT INTO users (id,name,email,hashed_password,role,is_platform_admin,is_active,is_verified) "
            "VALUES ('platform','Platform','platform@example.com','test-hash','Super Admin',true,true,true);"
            "INSERT INTO user_roles (id,user_id,role_id) VALUES ('platform-map','platform','super');"
        )
        await connection.execute(
            "INSERT INTO roles (id,name,description,is_system_role) VALUES ($1,'testing','Preserved description',false)",
            CUSTOM_ROLE_ID,
        )
        for key in CUSTOM_KEYS:
            await connection.execute(
                "INSERT INTO role_permissions (id,role_id,permission_id) VALUES ($1,$2,$3)",
                f"testing:{key}",
                CUSTOM_ROLE_ID,
                key,
            )
        await connection.execute(
            "INSERT INTO user_invitations (id,email,token,role,organization_id,status) "
            "VALUES ($1,'invited@example.com','fixture-token',$2,$3,'pending')",
            INVITATION_ID,
            CUSTOM_ROLE_ID,
            CUSTOM_ORG_ID,
        )
        yield connection, config
    finally:
        if connection is not None:
            await connection.close()
        await root.execute(f'DROP DATABASE "{database}"')
        await root.close()


async def snapshot(connection):
    return {
        table: await connection.fetch(
            f"SELECT * FROM {table} ORDER BY id"  # noqa: S608 -- Fixed table allow-list below.
        )
        for table in (
            "roles",
            "role_permissions",
            "permissions",
            "user_roles",
            "users",
            "organizations",
            "user_invitations",
            "organization_invitations",
            "settings",
        )
    }


@pytest.mark.asyncio
async def test_repair_dry_run_then_migration_preserves_scope_and_permissions(repair_database):
    connection, config = repair_database
    before = await snapshot(connection)
    # Reproduce the reported deployment failure before applying the repair.
    with pytest.raises(
        DBAPIError, match="cross-organization role mappings require reviewed cleanup"
    ):
        await asyncio.to_thread(command.upgrade, config, "head")
    assert await snapshot(connection) == before

    await connection.execute(build_sql())
    assert await snapshot(connection) == before
    await connection.execute(build_sql(commit=True))
    repaired = await snapshot(connection)
    for table in ("users", "user_roles", "organizations", "user_invitations"):
        assert repaired[table] == before[table]
    for row in before["permissions"]:
        assert row in repaired["permissions"]
    for row in before["role_permissions"]:
        assert row in repaired["role_permissions"]
    missing_revoke = not any(row["key"] == "api_keys:revoke" for row in before["permissions"])
    assert len(repaired["permissions"]) == len(before["permissions"]) + int(missing_revoke)
    assert (
        await connection.fetchval("SELECT count(*) FROM permissions WHERE key='api_keys:revoke'")
        == 1
    )
    assert len(repaired["roles"]) == len(before["roles"]) + 5
    assert (
        len(repaired["role_permissions"])
        == len(before["role_permissions"]) + 4 * len(ADMIN_PERMISSIONS) + 3
    )
    for _, organization in TARGETS:
        grants = await connection.fetch(
            "SELECT p.key FROM roles r JOIN role_permissions rp ON rp.role_id=r.id "
            "JOIN permissions p ON p.id=rp.permission_id WHERE r.organization_id=$1 AND r.name='Admin'",
            organization,
        )
        assert {row["key"] for row in grants} == ADMIN_PERMISSIONS
    with pytest.raises(asyncpg.RaiseError, match="tenant Admin already exists"):
        await connection.execute(build_sql(commit=True))
    await connection.execute("ROLLBACK")
    assert await snapshot(connection) == repaired

    await asyncio.to_thread(command.upgrade, config, "head")
    invitation = await connection.fetchrow(
        "SELECT * FROM user_invitations WHERE id=$1", INVITATION_ID
    )
    original_invitation = before["user_invitations"][0]
    assert invitation["role"] != CUSTOM_ROLE_ID
    assert {k: v for k, v in dict(invitation).items() if k != "role"} == {
        k: v for k, v in dict(original_invitation).items() if k != "role"
    }
    copied_role = await connection.fetchrow("SELECT * FROM roles WHERE id=$1", invitation["role"])
    assert copied_role["organization_id"] == CUSTOM_ORG_ID
    assert copied_role["name"] == "testing" and not copied_role["is_system_role"]
    assert copied_role["description"] == "Preserved description"
    copied_keys = await connection.fetch(
        "SELECT p.key FROM permissions p JOIN role_permissions rp ON rp.permission_id=p.id WHERE rp.role_id=$1",
        copied_role["id"],
    )
    assert {row["key"] for row in copied_keys} == set(CUSTOM_KEYS)
    assert await connection.fetchrow("SELECT * FROM roles WHERE id=$1", CUSTOM_ROLE_ID) == next(
        row for row in before["roles"] if row["id"] == CUSTOM_ROLE_ID
    )
    for user, organization in TARGETS:
        row = await connection.fetchrow(
            "SELECT u.organization_id,u.role,u.is_platform_admin,r.id,r.organization_id AS role_org "
            "FROM users u JOIN user_roles ur ON ur.user_id=u.id JOIN roles r ON r.id=ur.role_id "
            "WHERE u.id=$1",
            user,
        )
        assert row["organization_id"] == row["role_org"] == organization
        assert row["role"] == row["id"]
        assert row["is_platform_admin"] is False
    assert (
        await connection.fetchval("SELECT role_id FROM user_roles WHERE user_id='platform'")
        == "super"
    )
    assert await connection.fetchval("SELECT role FROM users WHERE id='platform'") == "Super Admin"
    assert await connection.fetch("SELECT * FROM role_permissions WHERE role_id='custom'") == [
        row for row in before["role_permissions"] if row["role_id"] == "custom"
    ]
    # The original migration's isolation trigger must still reject cross-tenant grants.
    other_role = await connection.fetchval(
        "SELECT id FROM roles WHERE organization_id=$1", TARGETS[1][1]
    )
    with pytest.raises(
        asyncpg.RaiseError, match="tenant users may only hold roles from their organization"
    ):
        await connection.execute(
            "UPDATE user_roles SET role_id=$1 WHERE user_id=$2", other_role, TARGETS[0][0]
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "drift",
    [
        "user",
        "missing_grant",
        "platform_grant",
        "revision",
        "global_role",
        "both_keys",
        "neither_key",
        "invitation",
        "custom_grant",
        "custom_local",
    ],
)
async def test_repair_rejects_drift_without_partial_writes(repair_database, drift):
    connection, _ = repair_database
    if drift == "user":
        await connection.execute(
            "UPDATE users SET organization_id=$1 WHERE id=$2", TARGETS[1][1], TARGETS[0][0]
        )
    elif drift == "missing_grant":
        await connection.execute(
            "DELETE FROM role_permissions WHERE role_id=$1 AND permission_id='dashboard:read'",
            GLOBAL_ADMIN,
        )
    elif drift == "platform_grant":
        await connection.execute(
            "INSERT INTO role_permissions (id,role_id,permission_id) VALUES ('extra',$1,'super_admin:manage')",
            GLOBAL_ADMIN,
        )
    elif drift == "revision":
        await connection.execute("UPDATE alembic_version SET version_num='unexpected'")
    elif drift == "global_role":
        await connection.execute("UPDATE roles SET is_system_role=false WHERE id=$1", GLOBAL_ADMIN)
    elif drift == "both_keys":
        await connection.execute(
            "INSERT INTO permissions (id,key,name,category) "
            "VALUES ('api_keys:revoke','api_keys:revoke','Revoke','api_keys') ON CONFLICT DO NOTHING"
        )
        for key in ("api_keys:revoke", "organization:delete"):
            await connection.execute(
                "INSERT INTO role_permissions (id,role_id,permission_id) VALUES ($1,$2,$3) "
                "ON CONFLICT DO NOTHING",
                f"admin:{key}",
                GLOBAL_ADMIN,
                key,
            )
    elif drift == "neither_key":
        await connection.execute(
            "DELETE FROM role_permissions WHERE role_id=$1 "
            "AND permission_id IN ('api_keys:revoke','organization:delete')",
            GLOBAL_ADMIN,
        )
    elif drift == "invitation":
        await connection.execute(
            "UPDATE user_invitations SET status='accepted' WHERE id=$1", INVITATION_ID
        )
    elif drift == "custom_grant":
        await connection.execute(
            "INSERT INTO role_permissions (id,role_id,permission_id) VALUES ('unexpected-custom',$1,'users:delete')",
            CUSTOM_ROLE_ID,
        )
    else:
        await connection.execute(
            "INSERT INTO roles (id,organization_id,name,is_system_role) VALUES ('existing-testing',$1,' TESTING ',false)",
            CUSTOM_ORG_ID,
        )
    before = await snapshot(connection)
    with pytest.raises(asyncpg.RaiseError, match="Repair blocked:"):
        await connection.execute(build_sql(commit=True))
    await connection.execute("ROLLBACK")
    assert await snapshot(connection) == before


@pytest.mark.asyncio
async def test_repair_reuses_existing_normalized_revoke_permission(repair_database):
    connection, _ = repair_database
    await connection.execute(
        "INSERT INTO permissions (id,key,name,category) "
        "SELECT 'existing-revoke',' API_KEYS:REVOKE ','Existing revoke','api_keys' "
        "WHERE NOT EXISTS (SELECT 1 FROM permissions WHERE lower(btrim(key))='api_keys:revoke')"
    )
    original = await connection.fetchrow(
        "SELECT * FROM permissions WHERE lower(btrim(key))='api_keys:revoke'"
    )
    await connection.execute(build_sql(commit=True))
    assert (
        await connection.fetchrow("SELECT * FROM permissions WHERE id=$1", original["id"])
        == original
    )
    assert (
        await connection.fetchval(
            "SELECT count(*) FROM role_permissions rp JOIN roles r ON r.id=rp.role_id "
            "WHERE rp.permission_id=$1 AND r.organization_id IS NOT NULL",
            original["id"],
        )
        == 4
    )


@pytest.mark.asyncio
async def test_additional_custom_references_abort_atomically(repair_database):
    connection, _ = repair_database
    # Each case starts from the same snapshot; only its extra reference is added.
    cases = (
        (
            "legacy_user",
            "INSERT INTO users (id,name,email,hashed_password,organization_id,role,is_platform_admin,is_active,is_verified) VALUES ('extra','Extra','extra@example.com','test',$1,$2,false,true,true)",
            [CUSTOM_ORG_ID, f" {CUSTOM_ROLE_ID} "],
        ),
        (
            "user_mapping",
            "INSERT INTO users (id,name,email,hashed_password,organization_id,role,is_platform_admin,is_active,is_verified) VALUES ('extra','Extra','extra@example.com','test',$1,'Admin',false,true,true)",
            [CUSTOM_ORG_ID],
        ),
        (
            "user_invitation",
            "INSERT INTO user_invitations (id,email,token,organization_id,role,status) VALUES ('extra','extra@example.com','extra-token',$1,$2,'expired')",
            [CUSTOM_ORG_ID, f" {CUSTOM_ROLE_ID} "],
        ),
        (
            "organization_invitation",
            "INSERT INTO organization_invitations (id,email,full_name,token,organization_id,role_id,status,expires_at) VALUES ('extra','extra@example.com','Extra','extra-token',$1,$2,'Pending',now()+interval '1 day')",
            [CUSTOM_ORG_ID, f" {CUSTOM_ROLE_ID} "],
        ),
        (
            "scalar_default",
            "INSERT INTO settings (id,key,value) VALUES ('extra',$1,$2)",
            [f"default_registration_role:{CUSTOM_ORG_ID}", f" {CUSTOM_ROLE_ID} "],
        ),
        (
            "array_default",
            "INSERT INTO settings (id,key,value) VALUES ('extra',$1,$2)",
            [
                f"default_registration_roles:{CUSTOM_ORG_ID}",
                json.dumps(["unrelated", f" {CUSTOM_ROLE_ID} "]),
            ],
        ),
        (
            "invalid_json",
            "INSERT INTO settings (id,key,value) VALUES ('extra',$1,'not-json')",
            [f"default_registration_roles:{CUSTOM_ORG_ID}"],
        ),
        (
            "non_array",
            "INSERT INTO settings (id,key,value) VALUES ('extra',$1,'{}')",
            [f"default_registration_roles:{CUSTOM_ORG_ID}"],
        ),
    )
    baseline = await snapshot(connection)
    for name, query, parameters in cases:
        await connection.execute(query, *parameters)
        if name == "user_mapping":
            await connection.execute(
                "INSERT INTO user_roles (id,user_id,role_id) VALUES ('extra','extra',$1)",
                CUSTOM_ROLE_ID,
            )
        with_extra = await snapshot(connection)
        with pytest.raises(
            asyncpg.RaiseError,
            match="Repair blocked: (additional custom-role references|invalid custom-organization default role settings)",
        ):
            await connection.execute(build_sql(commit=True))
        await connection.execute("ROLLBACK")
        assert await snapshot(connection) == with_extra, name
        # Remove only the fixture records added by this iteration.
        for table in (
            "user_roles",
            "users",
            "user_invitations",
            "organization_invitations",
            "settings",
        ):
            await connection.execute(
                f"DELETE FROM {table} WHERE id='extra'"  # noqa: S608 -- Fixed fixture table names.
            )
        assert await snapshot(connection) == baseline, name
