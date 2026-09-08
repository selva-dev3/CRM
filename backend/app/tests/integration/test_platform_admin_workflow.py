"""Global identity migration and same-session access against disposable PostgreSQL."""

import asyncio
import os
from pathlib import Path
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr
from sqlalchemy import select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.v1.routers import organizations, roles, users
from app.core.config import settings
from app.core.errors import ConflictError, register_exception_handlers
from app.core.security import get_password_hash, verify_password
from app.db.session import get_db
from app.models import Organization, OrganizationInvitation, User
from app.repositories.role_repository import RoleRepository
from app.schemas.crm_schemas import LoginRequest
from app.schemas.organization_invitation_schemas import AcceptInvitationRequest
from app.schemas.organization_lifecycle import InitialAdminInvitation, PlatformOrganizationCreate
from app.services.auth_service import AuthService
from app.services.invitation_service import accept_organization_invitation
from app.services.organization_lifecycle_service import OrganizationLifecycleService
from app.services.platform_admin_service import PlatformAdminService
from app.services.role_service import ALL_STANDARD_PERMISSIONS


@pytest.mark.asyncio
@pytest.mark.parametrize("legacy_platform_role", [True, False])
async def test_migration_singleton_provisioning_and_same_login_across_organizations(monkeypatch, legacy_platform_role):
    url = os.getenv("CRM_WORKFLOW_TEST_DATABASE_URL")
    if not url:
        pytest.skip("An isolated PostgreSQL workflow database is required")
    parsed = make_url(url)
    assert parsed.host in {"localhost", "127.0.0.1"}
    assert parsed.database == "crm_workflow_test"
    database = f"platform_test_{uuid4().hex}"
    root = create_async_engine(url, isolation_level="AUTOCOMMIT")
    async with root.connect() as connection:
        await connection.execute(text(f'CREATE DATABASE "{database}"'))
    isolated_url = parsed.set(database=database).render_as_string(hide_password=False)
    engine = create_async_engine(isolated_url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    # Historical p9 explicitly targets public: isolate the whole database.
    monkeypatch.setattr(settings, "DATABASE_URL", isolated_url)
    config = Config()
    config.set_main_option("script_location", str(Path(__file__).resolve().parents[3] / "alembic"))
    test_password = f"Test-{uuid4().hex}"
    original_hash = get_password_hash(test_password)
    try:
        await asyncio.to_thread(command.upgrade, config, "q0f1a2b3c4d5")
        async with engine.begin() as connection:
            await connection.execute(text("""
                INSERT INTO organizations (id,name,is_active,status)
                VALUES ('original-org','Original',true,'active')
            """))
            await connection.execute(
                text("""
                INSERT INTO users (id,name,email,hashed_password,role,organization_id,is_active,is_verified)
                VALUES ('intended-user','Platform','original@example.com',:hash,
                            :role,'original-org',true,true)
            """),
                {"hash": original_hash, "role": "super_admin" if legacy_platform_role else "Sales Executive"},
            )
        await asyncio.to_thread(command.upgrade, config, "head")
        if not legacy_platform_role:
            async with engine.begin() as connection:
                await connection.execute(text(
                    "INSERT INTO roles (id,name,organization_id,is_system_role) "
                    "VALUES ('tenant-role','Sales Executive','original-org',true)"
                ))
                await connection.execute(text("UPDATE users SET role='tenant-role' WHERE id='intended-user'"))
                await connection.execute(text(
                    "INSERT INTO user_roles (id,user_id,role_id) "
                    "VALUES ('tenant-mapping','intended-user','tenant-role')"
                ))
            async with sessions() as db:
                failed_provisioner = PlatformAdminService()
                failed_provisioner.repository.revoke_all_user_sessions = AsyncMock(
                    side_effect=RuntimeError("Injected session revocation failure")
                )
                with pytest.raises(RuntimeError, match="Injected"):
                    await failed_provisioner.provision(
                        db, email="superadmin@mycrm.com", password=SecretStr(test_password),
                        existing_user_id="intended-user",
                    )
                preserved = await db.get(User, "intended-user")
                assert not preserved.is_platform_admin
                assert preserved.organization_id == "original-org"
                assert preserved.hashed_password == original_hash
                assert await db.scalar(text(
                    "SELECT role_id FROM user_roles WHERE user_id='intended-user'"
                )) == "tenant-role"
        async with sessions() as db:
            user = await db.get(User, "intended-user")
            assert user.is_platform_admin is legacy_platform_role
            assert user.organization_id == (None if legacy_platform_role else "original-org")
            assert user.hashed_password == original_hash
            # Explicit provisioning must preserve the migrated identity.
            user_id = await PlatformAdminService().provision(
                db,
                email="superadmin@mycrm.com",
                password=SecretStr(test_password),
                existing_user_id="intended-user",
            )
            assert user_id == "intended-user"
            assert verify_password(test_password, user.hashed_password)
            assert user.hashed_password != test_password
        async with sessions() as db:
            with pytest.raises(ConflictError):
                await PlatformAdminService().provision(
                    db, email="duplicate@example.com", password=SecretStr(test_password)
                )

        monkeypatch.setattr("app.services.organization_lifecycle_service.send_user_invite_email", lambda **_: True)
        async with sessions() as db:
            await RoleRepository().seed_permissions(db, ALL_STANDARD_PERMISSIONS, commit=False)
            await RoleRepository().synchronize_system_roles(db)
            await db.commit()
        org_ids = []
        for name in ("A", "B"):
            async with sessions() as db:
                actor = await db.get(User, "intended-user")
                result = await OrganizationLifecycleService().create(db, PlatformOrganizationCreate(
                    name=f"Organization {name}", initial_admin=InitialAdminInvitation(
                        name=f"Admin {name}", email=f"admin-{name.lower()}@example.com",
                    )), actor)
                org_ids.append(result.organization.id)
                invitation = await db.get(OrganizationInvitation, result.invitation.id)
                await accept_organization_invitation(db, invitation.token, AcceptInvitationRequest(password=test_password))
        async with sessions() as db:
            assert await db.scalar(text("SELECT count(*) FROM users WHERE is_platform_admin")) == 1
            login = await AuthService().login(
                db,
                LoginRequest(
                    email="superadmin@mycrm.com",
                    password=test_password,
                ),
            )
            assert login["user"]["is_platform_admin"] is True
            assert login["user"]["organization_id"] == ""
            normal_login = await AuthService().login(
                db,
                LoginRequest(
                    email="admin-a@example.com",
                    password=test_password,
                ),
            )
            super_role_id = await db.scalar(
                text("SELECT id FROM roles WHERE lower(replace(name,'_',' '))='super admin'")
            )

        app = FastAPI()
        register_exception_handlers(app)
        app.include_router(organizations.router, prefix="/organizations")
        app.include_router(roles.router, prefix="/roles")
        app.include_router(users.router, prefix="/users")

        async def session_dependency():
            async with sessions() as db:
                yield db

        app.dependency_overrides[get_db] = session_dependency
        headers = {"Cookie": f"{settings.AUTH_COOKIE_NAME}={login['access_token']}"}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            listed = await client.get("/organizations/all", headers=headers)
            assert listed.status_code == 200, listed.text
            profile = await client.get("/users/me/profile", headers=headers)
            assert profile.status_code == 200, profile.text
            assert profile.json()["id"] == "intended-user"
            assert set(org_ids).issubset({org["id"] for org in listed.json()})
            for org_id in org_ids:
                selected = {**headers, "X-Organization-ID": org_id}
                opened = await client.get("/organizations/current", headers=selected)
                assert opened.status_code == 200, opened.text
                assert opened.json()["id"] == org_id
                for endpoint in ("/users", "/roles", "/organizations/members"):
                    response = await client.get(endpoint, headers=selected)
                    assert response.status_code == 200, response.text
                custom = await client.post(
                    "/roles",
                    headers=selected,
                    json={
                        "name": "Selected organization role",
                        "permissions": ["leads:read"],
                    },
                )
                assert custom.status_code == 201, custom.text
                role_id = custom.json()["id"]
                updated = await client.put(
                    f"/roles/{role_id}",
                    headers=selected,
                    json={"description": "Updated by platform account"},
                )
                assert updated.status_code == 200, updated.text
                assigned = await client.post(
                    f"/roles/{role_id}/permissions",
                    headers=selected,
                    json=["leads:read", "leads:create"],
                )
                assert assigned.status_code == 200, assigned.text
                # Replacing overlapping grants through either endpoint must
                # flush deletes before inserting the same unique pairs.
                replaced = await client.put(
                    f"/roles/{role_id}",
                    headers=selected,
                    json={"permissions": ["leads:read", "leads:update"]},
                )
                assert replaced.status_code == 200, replaced.text
                assert set(replaced.json()["permissions"]) == {"leads:read", "leads:update"}
                created_user = await client.post(
                    "/users",
                    headers=selected,
                    json={
                        "name": "Organization member",
                        "email": f"member-{org_id}@example.com",
                        "role": role_id,
                        "password": test_password,
                    },
                )
                assert created_user.status_code == 201, created_user.text
                assert created_user.json()["organization_id"] == org_id
            normal = {"Authorization": f"Bearer {normal_login['access_token']}"}
            assert (await client.get("/organizations/all", headers=normal)).status_code == 403
            assert (
                await client.get("/roles", headers={**normal, "X-Organization-ID": org_ids[1]})
            ).status_code == 403
            for method, endpoint, body in (
                ("DELETE", "/users/intended-user", None),
                ("DELETE", "/organizations/members/intended-user", None),
                ("PUT", "/users/intended-user", {"role": "Admin"}),
                ("POST", "/users/intended-user/deactivate", None),
                (
                    "PUT",
                    f"/roles/users/{normal_login['user']['id']}/role?role_id={super_role_id}",
                    None,
                ),
                (
                    "POST",
                    "/users",
                    {
                        "name": "Unauthorized platform",
                        "email": "second@example.com",
                        "role": super_role_id,
                        "password": test_password,
                    },
                ),
            ):
                response = await client.request(method, endpoint, headers=normal, json=body)
                if endpoint == "/users" and method == "POST":
                    # User creation validates roles strictly within the tenant;
                    # a global role ID is an invalid request, never assignable.
                    assert response.status_code == 400, response.text
                    assert "Invalid role" in response.json()["message"]
                else:
                    assert response.status_code in {403, 404}, response.text

        # Direct database writes must not bypass the platform invariants.
        invalid_writes = [
            "UPDATE users SET is_platform_admin=false WHERE id='intended-user'",
            "UPDATE users SET is_active=false WHERE id='intended-user'",
            "DELETE FROM users WHERE id='intended-user'",
            "UPDATE users SET role='Super Admin' WHERE email='admin-a@example.com'",
            "UPDATE users SET email='SUPERADMIN@MYCRM.COM' WHERE email='admin-a@example.com'",
            "INSERT INTO users (id,name,email,hashed_password,role,is_platform_admin,is_active,is_verified) "
            "VALUES ('duplicate','Duplicate','duplicate@example.com','test-hash','Super Admin',true,true,true)",
            "INSERT INTO user_roles (id,user_id,role_id) SELECT 'invalid',u.id,r.id FROM users u,roles r "
            "WHERE u.email='admin-a@example.com' AND lower(replace(r.name,'_',' '))='super admin'",
        ]
        for statement in invalid_writes:
            async with sessions() as db:
                with pytest.raises(IntegrityError):
                    await db.execute(text(statement))
                    await db.commit()
                await db.rollback()
        async with sessions() as db:
            original = await db.get(Organization, "original-org")
            await db.delete(original)
            await db.commit()
            user = await db.get(User, "intended-user")
            assert user.is_platform_admin and user.organization_id is None and user.is_active
            assert (
                await db.scalars(select(User).where(User.is_platform_admin))
            ).one().id == user.id
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/organizations/all", headers=headers)
            assert response.status_code == 200
            assert set(org_ids) == {org["id"] for org in response.json()}
    finally:
        await engine.dispose()
        async with root.connect() as connection:
            await connection.execute(text(f'DROP DATABASE "{database}"'))
        await root.dispose()
