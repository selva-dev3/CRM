"""Real migrated PostgreSQL and authenticated HTTP requests; never production data."""

import asyncio
import os
from pathlib import Path
from uuid import uuid4

import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select, text, update
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.v1.routers import auth, invitations, organizations
from app.core.config import settings
from app.core.errors import register_exception_handlers
from app.core.rbac_matrix import SYSTEM_ROLE_PERMISSIONS
from app.core.security import get_password_hash
from app.db.session import get_db
from app.models import (
    AuditLog,
    CustomField,
    Organization,
    OrganizationDeletion,
    OrganizationFileCleanup,
    OrganizationInvitation,
    OrganizationSetting,
    OrganizationSubscription,
    Permission,
    RefreshToken,
    Role,
    RolePermission,
    SLAPolicy,
    User,
    UserInvitation,
    UserRole,
    UserSession,
)
from app.repositories.role_repository import RoleRepository
from app.schemas.crm_schemas import LoginRequest
from app.services.auth_service import AuthService
from app.services.organization_lifecycle_service import organization_lifecycle_service
from app.services.role_service import ALL_STANDARD_PERMISSIONS


@pytest_asyncio.fixture
async def lifecycle(monkeypatch):
    url = os.getenv("CRM_WORKFLOW_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set CRM_WORKFLOW_TEST_DATABASE_URL to the isolated local test database")
    parsed = make_url(url)
    assert parsed.host in {"localhost", "127.0.0.1"} and parsed.database == "crm_workflow_test"
    database = f"org_lifecycle_{uuid4().hex}"
    root = create_async_engine(url, isolation_level="AUTOCOMMIT")
    async with root.connect() as connection:
        await connection.execute(text(f'CREATE DATABASE "{database}"'))
    isolated_url = parsed.set(database=database).render_as_string(hide_password=False)
    monkeypatch.setattr(settings, "DATABASE_URL", isolated_url)
    monkeypatch.setattr(settings, "ORGANIZATION_DELETION_ENABLED", True)
    monkeypatch.setattr(
        "app.services.organization_lifecycle_service.s3_service.list_file_keys", lambda *args: []
    )
    monkeypatch.setattr(
        "app.services.organization_lifecycle_service.send_user_invite_email", lambda **_: True
    )
    config = Config()
    config.set_main_option("script_location", str(Path(__file__).resolve().parents[3] / "alembic"))
    engine = create_async_engine(isolated_url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    password = f"Test-{uuid4().hex}"
    try:
        await asyncio.to_thread(command.upgrade, config, "head")
        async with sessions() as db:
            repository = RoleRepository()
            await repository.seed_permissions(db, ALL_STANDARD_PERMISSIONS, commit=False)
            await repository.synchronize_system_roles(db)
            platform = User(
                id=str(uuid4()),
                email="superadmin@mycrm.com",
                name="Platform",
                hashed_password=get_password_hash(password),
                role="Super Admin",
                is_platform_admin=True,
                organization_id=None,
                is_active=True,
                is_verified=True,
            )
            db.add(platform)
            await db.commit()
            platform_id = platform.id
            login = await AuthService().login(
                db, LoginRequest(email=platform.email, password=password)
            )
        app = FastAPI()
        register_exception_handlers(app)
        app.include_router(auth.router, prefix="/auth")
        app.include_router(invitations.router, prefix="/organizations/invitations")
        app.include_router(organizations.router, prefix="/organizations")

        async def get_session():
            async with sessions() as db:
                yield db

        app.dependency_overrides[get_db] = get_session
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={"Authorization": f"Bearer {login['access_token']}"},
        ) as client:
            yield client, sessions, platform_id, password
    finally:
        await engine.dispose()
        async with root.connect() as connection:
            await connection.execute(text(f'DROP DATABASE "{database}" WITH (FORCE)'))
        await root.dispose()


async def create(client, name="Lifecycle organization", **extra):
    response = await client.post("/organizations", json={"name": name, **extra})
    assert response.status_code == 201, response.text
    return response.json()["organization"]


@pytest.mark.asyncio
async def test_create_scoped_roles_settings_subscription_and_same_session_switching(lifecycle):
    client, sessions, platform_id, _ = lifecycle
    first = await create(client, " Organization A ")
    second = await create(client, "Organization B")
    assert first["name"] == "Organization A" and first["members_count"] == 0
    for organization in (first, second):
        response = await client.get(
            "/organizations/current", headers={"X-Organization-ID": organization["id"]}
        )
        assert response.status_code == 200 and response.json()["id"] == organization["id"]
        async with sessions() as db:
            roles = list(
                await db.scalars(select(Role).where(Role.organization_id == organization["id"]))
            )
            assert {role.name for role in roles} == set(SYSTEM_ROLE_PERMISSIONS)
            assert len(roles) == 6
            for role in roles:
                grants = set(
                    await db.scalars(
                        select(Permission.key)
                        .join(RolePermission)
                        .where(RolePermission.role_id == role.id)
                    )
                )
                assert grants == SYSTEM_ROLE_PERMISSIONS[role.name]
            assert (
                await db.scalar(
                    select(func.count())
                    .select_from(OrganizationSetting)
                    .where(OrganizationSetting.organization_id == organization["id"])
                )
                == 1
            )
            subscription = await db.scalar(
                select(OrganizationSubscription).where(
                    OrganizationSubscription.organization_id == organization["id"]
                )
            )
            assert subscription.current_users == 0 and subscription.amount == 0
    async with sessions() as db:
        assert await db.scalar(select(func.count()).select_from(User)) == 1
        assert (await db.get(User, platform_id))._organization_id is None
    listed = (await client.get("/organizations/all")).json()
    assert {first["id"], second["id"]}.issubset({item["id"] for item in listed})


@pytest.mark.asyncio
@pytest.mark.parametrize("name", ["", "   ", "\t\n", "x" * 256])
async def test_invalid_names_and_privileged_fields_are_rejected(lifecycle, name):
    client, _, _, _ = lifecycle
    assert (await client.post("/organizations", json={"name": name})).status_code == 422
    assert (
        await client.post("/organizations", json={"name": "Safe", "is_platform_admin": True})
    ).status_code == 422


@pytest.mark.asyncio
async def test_duplicate_names_concurrent_and_case_insensitive(lifecycle):
    client, sessions, _, _ = lifecycle
    responses = await asyncio.gather(
        *[
            client.post("/organizations", json={"name": name})
            for name in ("Duplicate", " duplicate ")
        ]
    )
    assert sorted(r.status_code for r in responses) == [201, 409]
    async with sessions() as db:
        assert await db.scalar(select(func.count()).select_from(Organization)) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("role_name", list(SYSTEM_ROLE_PERMISSIONS))
async def test_every_tenant_role_blocked_and_cross_org_context_denied(lifecycle, role_name):
    client, sessions, _, password = lifecycle
    first, second = await create(client, "A"), await create(client, "B")
    async with sessions() as db:
        role = await db.scalar(
            select(Role).where(Role.organization_id == first["id"], Role.name == role_name)
        )
        user = User(
            name="Tenant",
            email="tenant@example.com",
            hashed_password=get_password_hash(password),
            role=role.id,
            organization_id=first["id"],
            is_active=True,
            is_verified=True,
        )
        db.add(user)
        await db.flush()
        db.add(UserRole(user_id=user.id, role_id=role.id))
        await db.commit()
        login = await AuthService().login(db, LoginRequest(email=user.email, password=password))
    headers = {"Authorization": f"Bearer {login['access_token']}"}
    assert (
        await client.post("/organizations", headers=headers, json={"name": "Forbidden"})
    ).status_code == 403
    assert (
        await client.delete(f"/organizations/{first['id']}", headers=headers)
    ).status_code == 403
    assert (
        await client.post(
            "/organizations/invitations/new-organization",
            headers=headers,
            json={"full_name": "Admin", "email": "new@example.com"},
        )
    ).status_code == 403
    assert (
        await client.get(
            "/organizations/current", headers={**headers, "X-Organization-ID": second["id"]}
        )
    ).status_code == 403


@pytest.mark.asyncio
async def test_public_registration_and_orphan_invitation_cannot_create(lifecycle):
    client, sessions, _, password = lifecycle
    response = await client.post(
        "/auth/register",
        json={
            "name": "Public",
            "email": "public@example.com",
            "password": password,
            "organization_name": "Public",
        },
    )
    assert response.status_code == 403
    async with sessions() as db:
        assert await db.scalar(select(func.count()).select_from(Organization)) == 0


@pytest.mark.asyncio
async def test_invitation_acceptance_assigns_exact_scoped_admin_and_is_single_use(lifecycle):
    client, sessions, _, password = lifecycle
    organization = await create(
        client, initial_admin={"name": "Initial Admin", "email": "initial@example.com"}
    )
    async with sessions() as db:
        invitation = await db.scalar(
            select(OrganizationInvitation).where(
                OrganizationInvitation.organization_id == organization["id"]
            )
        )
        token, role_id = invitation.token, invitation.role_id
    accepted = await client.post(
        f"/organizations/invitations/{token}/accept", json={"password": password}
    )
    assert accepted.status_code == 200, accepted.text
    accepted_user = accepted.json()["user"]
    assert accepted_user["is_platform_admin"] is False
    assert accepted_user["permissions"]
    assert accepted_user["organization_id"] == organization["id"]
    async with sessions() as db:
        user = await db.scalar(select(User).where(User.email == "initial@example.com"))
        assert not user.is_platform_admin and user.role == role_id
        assert (
            await db.scalar(select(UserRole.role_id).where(UserRole.user_id == user.id)) == role_id
        )
        assert (await db.get(Role, role_id)).organization_id == organization["id"]
        session = await db.scalar(select(UserSession).where(UserSession.user_id == user.id))
        refresh = await db.scalar(select(RefreshToken).where(RefreshToken.user_id == user.id))
        assert session.family_id == refresh.family_id
        assert session.expires_at is not None
        assert refresh.absolute_expires_at is not None
    assert (
        await client.post(f"/organizations/invitations/{token}/accept", json={"password": password})
    ).status_code == 400


@pytest.mark.asyncio
async def test_migrated_rbac_rejects_referenced_user_and_role_scope_changes(lifecycle):
    client, sessions, _, password = lifecycle
    organization = await create(
        client,
        "Scoped",
        initial_admin={"name": "Admin", "email": "scope-admin@example.com"},
    )
    other = await create(client, "Other")
    async with sessions() as db:
        invitation = await db.scalar(
            select(OrganizationInvitation).where(
                OrganizationInvitation.organization_id == organization["id"]
            )
        )
        token = invitation.token
    accepted = await client.post(
        f"/organizations/invitations/{token}/accept", json={"password": password}
    )
    assert accepted.status_code == 200, accepted.text
    user_id = accepted.json()["user"]["id"]

    async with sessions() as db:
        role_id = await db.scalar(
            select(UserRole.role_id).where(UserRole.user_id == user_id)
        )
        with pytest.raises(DBAPIError):
            await db.execute(
                update(User)
                .where(User.id == user_id)
                .values(organization_id=other["id"])
            )
            await db.flush()
        await db.rollback()

        with pytest.raises(DBAPIError):
            await db.execute(
                update(Role)
                .where(Role.id == role_id)
                .values(organization_id=other["id"])
            )
            await db.flush()
        await db.rollback()


@pytest.mark.asyncio
async def test_delete_preserves_platform_login_and_allows_zero_then_new_organization(lifecycle):
    client, sessions, platform_id, password = lifecycle
    organization = await create(
        client,
        initial_admin={"name": "Tenant Admin", "email": "delete-admin@example.com"},
    )
    async with sessions() as db:
        invitation = await db.scalar(
            select(OrganizationInvitation).where(
                OrganizationInvitation.organization_id == organization["id"]
            )
        )
        invitation_token = invitation.token
        db.add_all(
            [
                CustomField(
                    organization_id=organization["id"],
                    entity_type="leads",
                    field_name="custom",
                    label="Custom",
                ),
                SLAPolicy(organization_id=organization["id"], name="Tenant SLA"),
                UserInvitation(
                    organization_id=organization["id"],
                    email="pending@example.com",
                    token=str(uuid4()),
                ),
            ]
        )
        await db.commit()
    accepted = await client.post(
        f"/organizations/invitations/{invitation_token}/accept",
        json={"password": password},
    )
    assert accepted.status_code == 200, accepted.text
    tenant_user_id = accepted.json()["user"]["id"]
    deleted = await client.delete(
        f"/organizations/{organization['id']}", headers={"X-Organization-ID": organization["id"]}
    )
    assert deleted.status_code == 200, deleted.text
    operation_id = deleted.json()["operation_id"]
    assert deleted.json()["cleanup_status"] == "complete"
    assert (await client.get("/organizations/all")).json() == []
    assert (
        await client.get(
            "/organizations/current", headers={"X-Organization-ID": organization["id"]}
        )
    ).json()["code"] == "ORGANIZATION_UNAVAILABLE"
    assert (await client.delete(f"/organizations/{organization['id']}")).status_code == 404
    async with sessions() as db:
        assert (await db.get(User, platform_id))._organization_id is None
        assert await db.get(User, tenant_user_id) is None
        assert (
            await db.scalar(select(UserRole.id).where(UserRole.user_id == tenant_user_id))
            is None
        )
        login = await AuthService().login(
            db, LoginRequest(email="superadmin@mycrm.com", password=password)
        )
        assert login["user"]["is_platform_admin"]
        assert await db.get(OrganizationDeletion, operation_id)
        assert await db.scalar(select(AuditLog.id).where(AuditLog.action == "DELETE_ORGANIZATION"))
        for model in (
            Role,
            OrganizationSetting,
            OrganizationSubscription,
            CustomField,
            SLAPolicy,
            UserInvitation,
        ):
            assert (
                await db.scalar(
                    select(func.count())
                    .select_from(model)
                    .where(model.organization_id == organization["id"])
                )
                == 0
            )
    await create(client, "After final deletion")


@pytest.mark.asyncio
@pytest.mark.parametrize("stage", ["create_setting", "create_subscription"])
async def test_failed_provisioning_rolls_back(lifecycle, monkeypatch, stage):
    client, sessions, _, _ = lifecycle

    async def fail(*args, **kwargs):
        raise RuntimeError("Injected provisioning failure")

    monkeypatch.setattr(organization_lifecycle_service.organizations, stage, fail)
    response = await client.post("/organizations", json={"name": "Rollback"})
    assert response.status_code == 500
    async with sessions() as db:
        assert await db.scalar(select(func.count()).select_from(Organization)) == 0


@pytest.mark.asyncio
async def test_failed_deletion_rolls_back_dependencies_audit_and_manifest(lifecycle, monkeypatch):
    client, sessions, _, _ = lifecycle
    organization = await create(client)

    async def fail(*args, **kwargs):
        raise RuntimeError("Injected deletion failure")

    monkeypatch.setattr(organization_lifecycle_service.organizations, "delete", fail)
    response = await client.delete(f"/organizations/{organization['id']}")
    assert response.status_code == 500
    async with sessions() as db:
        assert await db.get(Organization, organization["id"])
        assert await db.scalar(select(func.count()).select_from(OrganizationDeletion)) == 0
        assert await db.scalar(select(func.count()).select_from(OrganizationFileCleanup)) == 0
        assert (
            await db.scalar(
                select(func.count())
                .select_from(Role)
                .where(Role.organization_id == organization["id"])
            )
            == 6
        )


@pytest.mark.asyncio
async def test_provider_billing_blocks_deletion(lifecycle):
    client, sessions, _, _ = lifecycle
    organization = await create(client)
    async with sessions() as db:
        subscription = await db.scalar(
            select(OrganizationSubscription).where(
                OrganizationSubscription.organization_id == organization["id"]
            )
        )
        subscription.subscription_id = "sub_controlled_test"
        await db.commit()
    response = await client.delete(f"/organizations/{organization['id']}")
    assert (
        response.status_code == 409 and response.json()["code"] == "ORGANIZATION_BILLING_PROTECTED"
    )


@pytest.mark.asyncio
async def test_populated_crm_deletion_revokes_tenant_session_and_preserves_other_tenant(
    lifecycle, monkeypatch
):
    from app.models import (
        Company,
        Contact,
        Deal,
        DealProduct,
        Document,
        Lead,
        Product,
        Quote,
        UserSession,
    )
    from app.services.organization_cleanup_service import cleanup_organization_files

    client, sessions, platform_id, password = lifecycle
    organization, survivor = await create(client, "Populated"), await create(client, "Survivor")
    async with sessions() as db:
        role_id = await db.scalar(
            select(Role.id).where(Role.organization_id == organization["id"], Role.name == "Admin")
        )
        user = User(
            name="Tenant",
            email="delete-me@example.com",
            hashed_password=get_password_hash(password),
            role=role_id,
            organization_id=organization["id"],
            is_active=True,
            is_verified=True,
        )
        db.add(user)
        await db.flush()
        user_id = user.id
        company = Company(organization_id=organization["id"], name="Company")
        contact = Contact(
            organization_id=organization["id"], name="Contact", email="contact@example.com"
        )
        product = Product(
            organization_id=organization["id"], name="Product", sku="controlled-product"
        )
        retained = Company(organization_id=survivor["id"], name="Retained")
        db.add_all([company, contact, product, retained])
        await db.flush()
        retained_id = retained.id
        deal = Deal(
            organization_id=organization["id"],
            title="Deal",
            assigned_to=user.id,
            company_id=company.id,
            contact_id=contact.id,
        )
        db.add(deal)
        await db.flush()
        db.add_all(
            [
                Lead(
                    organization_id=organization["id"],
                    title="Converted",
                    company="Company",
                    contact_name="Contact",
                    email="lead@example.com",
                    converted_company_id=company.id,
                    converted_contact_id=contact.id,
                    converted_deal_id=deal.id,
                ),
                Quote(
                    organization_id=organization["id"],
                    quote_number="Q-test",
                    automatic_deal_id=deal.id,
                    company_id=company.id,
                    contact_id=contact.id,
                ),
                DealProduct(deal_id=deal.id, product_id=product.id),
                Document(
                    organization_id=organization["id"],
                    filename="controlled.txt",
                    s3_key="controlled/tenant-file.txt",
                    uploaded_by=user.id,
                ),
            ]
        )
        await db.commit()
        login = await AuthService().login(db, LoginRequest(email=user.email, password=password))
    response = await client.delete(f"/organizations/{organization['id']}")
    assert response.status_code == 200, response.text
    assert response.json()["cleanup_status"] == "pending"
    tenant = await client.get(
        "/organizations/current", headers={"Authorization": f"Bearer {login['access_token']}"}
    )
    assert tenant.status_code == 401
    assert (
        await client.get("/organizations/current", headers={"X-Organization-ID": survivor["id"]})
    ).status_code == 200
    deleted_keys = []
    monkeypatch.setattr(
        "app.services.organization_cleanup_service.s3_service.delete_file",
        lambda key: deleted_keys.append(key) or True,
    )
    async with sessions() as db:
        assert await db.get(User, user_id) is None
        assert (
            await db.scalar(
                select(func.count()).select_from(UserSession).where(UserSession.user_id == user_id)
            )
            == 0
        )
        assert await db.get(User, platform_id)
        assert (await db.get(Company, retained_id)).name == "Retained"
        for model in (Company, Contact, Deal, Lead, Product, Quote, Document):
            assert (
                await db.scalar(
                    select(func.count())
                    .select_from(model)
                    .where(model.organization_id == organization["id"])
                )
                == 0
            )
        assert await cleanup_organization_files(db) == 1
        assert await cleanup_organization_files(db) == 0
    assert deleted_keys == ["controlled/tenant-file.txt"]
    status = await client.get(f"/organizations/deletions/{response.json()['operation_id']}")
    assert status.json()["cleanup_status"] == "complete"


@pytest.mark.asyncio
async def test_cross_tenant_references_and_shared_storage_block_deletion(lifecycle):
    from app.models import Company, Document

    client, sessions, platform_id, _ = lifecycle
    first, second = await create(client, "First"), await create(client, "Second")
    async with sessions() as db:
        parent = Company(organization_id=first["id"], name="Parent")
        db.add(parent)
        await db.flush()
        child = Company(organization_id=second["id"], name="Child", parent_company_id=parent.id)
        db.add(child)
        await db.commit()
        child_id = child.id
    blocked = await client.delete(f"/organizations/{first['id']}")
    assert (
        blocked.status_code == 409 and blocked.json()["code"] == "ORGANIZATION_DEPENDENCY_CONFLICT"
    )
    async with sessions() as db:
        child = await db.get(Company, child_id)
        child.parent_company_id = None
        db.add_all(
            [
                Document(
                    organization_id=org["id"],
                    filename="Shared",
                    s3_key="controlled/shared.txt",
                    uploaded_by=platform_id,
                )
                for org in (first, second)
            ]
        )
        await db.commit()
    blocked = await client.delete(f"/organizations/{first['id']}")
    assert blocked.status_code == 409 and blocked.json()["code"] == "ORGANIZATION_STORAGE_CONFLICT"
    async with sessions() as db:
        assert await db.scalar(select(func.count()).select_from(Organization)) == 2
        assert await db.scalar(select(func.count()).select_from(OrganizationDeletion)) == 0


@pytest.mark.asyncio
async def test_cleanup_failures_are_durable_and_retryable(lifecycle, monkeypatch):
    from app.models import Document
    from app.services.organization_cleanup_service import cleanup_organization_files

    client, sessions, platform_id, _ = lifecycle
    organization = await create(client)
    async with sessions() as db:
        db.add(
            Document(
                organization_id=organization["id"],
                filename="File",
                s3_key="controlled/retry.txt",
                uploaded_by=platform_id,
            )
        )
        await db.commit()
    response = await client.delete(f"/organizations/{organization['id']}")
    assert response.status_code == 200, response.text
    operation_id = response.json()["operation_id"]
    monkeypatch.setattr(
        "app.services.organization_cleanup_service.s3_service.delete_file", lambda _: False
    )
    async with sessions() as db:
        item = await db.scalar(select(OrganizationFileCleanup))
        item.attempts = 4
        await db.commit()
        assert await cleanup_organization_files(db) == 0
    assert (await client.get(f"/organizations/deletions/{operation_id}")).json()[
        "cleanup_status"
    ] == "failed"
    assert (await client.post(f"/organizations/deletions/{operation_id}/retry")).json()[
        "cleanup_status"
    ] == "pending"
    monkeypatch.setattr(
        "app.services.organization_cleanup_service.s3_service.delete_file", lambda _: True
    )
    async with sessions() as db:
        assert await cleanup_organization_files(db) == 1


@pytest.mark.asyncio
async def test_deletion_readiness_gate_and_unauthenticated_requests(lifecycle, monkeypatch):
    client, sessions, _, _ = lifecycle
    organization = await create(client)
    monkeypatch.setattr(settings, "ORGANIZATION_DELETION_ENABLED", False)
    response = await client.delete(f"/organizations/{organization['id']}")
    assert response.status_code == 503
    for method, url in [
        ("POST", "/organizations"),
        ("DELETE", f"/organizations/{organization['id']}"),
    ]:
        request = client.build_request(method, url, json={"name": "Unauthorized"})
        request.headers.pop("Authorization", None)
        assert (await client.send(request)).status_code == 401
    async with sessions() as db:
        assert await db.get(Organization, organization["id"])


@pytest.mark.asyncio
async def test_migration_aborts_on_existing_duplicate_names_without_rewriting(lifecycle):
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    client, sessions, _, _ = lifecycle
    organization = await create(client, "Keep Original")
    # Load the repository migration by path, without changing historical files.
    import importlib.util

    path = (
        Path(__file__).resolve().parents[3]
        / "alembic/versions/s2b3c4d5e6f7_organization_lifecycle.py"
    )
    spec = importlib.util.spec_from_file_location("lifecycle_migration_test", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    async with sessions() as db:
        await db.execute(text("DROP INDEX uq_organizations_normalized_name"))
        db.add(Organization(id=str(uuid4()), name=" keep original "))
        await db.flush()
        connection = await db.connection()

        def upgrade(sync_connection):
            with Operations.context(MigrationContext.configure(sync_connection)):
                migration.upgrade()

        with pytest.raises(RuntimeError, match="Duplicate organization names"):
            await connection.run_sync(upgrade)
        await db.rollback()
    async with sessions() as db:
        assert await db.scalar(select(func.count()).select_from(Organization)) == 1
        assert (await db.get(Organization, organization["id"])).name == "Keep Original"
        assert await db.scalar(text("SELECT to_regclass('uq_organizations_normalized_name')"))


@pytest.mark.asyncio
async def test_invitation_acceptance_cannot_change_organization_metadata(lifecycle):
    client, sessions, _, password = lifecycle
    organization = await create(
        client,
        "Platform chosen name",
        initial_admin={"name": "Invitee", "email": "readonly@example.com"},
    )
    async with sessions() as db:
        invitation = await db.scalar(
            select(OrganizationInvitation).where(
                OrganizationInvitation.organization_id == organization["id"]
            )
        )
        invitation.role_id = await db.scalar(
            select(Role.id).where(
                Role.organization_id == organization["id"], Role.name == "Read Only"
            )
        )
        token = invitation.token
        await db.commit()
    response = await client.post(
        f"/organizations/invitations/{token}/accept",
        json={
            "password": password,
            "organization_name": "Hijacked",
            "domain": "untrusted.example.com",
            "industry": "Injected",
            "country": "Injected",
            "city": "Injected",
            "phone": "123",
        },
    )
    assert response.status_code == 200, response.text
    async with sessions() as db:
        org = await db.get(Organization, organization["id"])
        assert org.name == "Platform chosen name"
        assert org.domain is None and org.industry is None and org.phone is None
        assert org.country is None and org.city is None


@pytest.mark.asyncio
async def test_tenant_invitation_cannot_take_over_initial_admin_invitation(lifecycle, monkeypatch):
    client, sessions, _, password = lifecycle
    first = await create(
        client, "First", initial_admin={"name": "Initial", "email": "initial@example.com"}
    )
    second = await create(client, "Second")
    async with sessions() as db:
        role_id = await db.scalar(
            select(Role.id).where(Role.organization_id == second["id"], Role.name == "Admin")
        )
        user = User(
            name="Other admin",
            email="other-admin@example.com",
            hashed_password=get_password_hash(password),
            role=role_id,
            organization_id=second["id"],
            is_active=True,
            is_verified=True,
        )
        db.add(user)
        await db.flush()
        db.add(UserRole(user_id=user.id, role_id=role_id))
        await db.commit()
        login = await AuthService().login(db, LoginRequest(email=user.email, password=password))
        invite = await db.scalar(
            select(OrganizationInvitation).where(
                OrganizationInvitation.organization_id == first["id"]
            )
        )
        old_id, old_token, old_role = invite.id, invite.token, invite.role_id
    response = await client.post(
        "/organizations/invitations",
        headers={"Authorization": f"Bearer {login['access_token']}"},
        json={"email": "initial@example.com", "full_name": "Hijacked", "role": "Admin"},
    )
    assert response.status_code == 409, response.text
    async with sessions() as db:
        invite = await db.get(OrganizationInvitation, old_id)
        assert (invite.organization_id, invite.token, invite.role_id) == (
            first["id"],
            old_token,
            old_role,
        )
    monkeypatch.setattr("app.services.invitation_service.send_user_invite_email", lambda **_: True)
    responses = await asyncio.gather(
        client.post(
            "/organizations",
            json={
                "name": "Concurrent provisioning",
                "initial_admin": {"name": "Admin", "email": "race@example.com"},
            },
        ),
        client.post(
            "/organizations/invitations",
            headers={"Authorization": f"Bearer {login['access_token']}"},
            json={"email": "race@example.com", "full_name": "Member", "role": "Admin"},
        ),
    )
    assert sorted(response.status_code for response in responses) == [201, 409], [
        response.text for response in responses
    ]
    async with sessions() as db:
        assert (
            await db.scalar(
                select(func.count())
                .select_from(OrganizationInvitation)
                .where(OrganizationInvitation.email == "race@example.com")
            )
            == 1
        )


@pytest.mark.asyncio
async def test_deletion_waits_for_inflight_upload_and_inventories_its_object(
    lifecycle, monkeypatch
):
    import io
    import threading

    from fastapi import UploadFile
    from starlette.datastructures import Headers

    from app.services.document_service import DocumentService
    from app.services.organization_storage_service import lock_organization_storage

    client, sessions, platform_id, _ = lifecycle
    organization = await create(client, "Upload race")
    started, release = threading.Event(), threading.Event()
    keys = []

    def upload(file, *, object_name, **kwargs):
        keys.append(object_name)
        started.set()
        if not release.wait(5):
            raise RuntimeError("Test upload was not released")
        return object_name

    monkeypatch.setattr("app.services.document_service.s3_service.upload_file", upload)
    monkeypatch.setattr(
        "app.services.document_service.s3_service.generate_presigned_url",
        lambda key: "https://unused.example.com/" + key,
    )

    async def upload_document():
        async with sessions() as db:
            actor = await db.get(User, platform_id)
            actor.__dict__["_request_organization_id"] = organization["id"]
            return await DocumentService().upload_document(
                db,
                UploadFile(
                    io.BytesIO(b"file"),
                    filename="race.txt",
                    headers=Headers({"content-type": "text/plain"}),
                ),
                actor,
            )

    uploading = asyncio.create_task(upload_document())
    deleting = None
    try:
        assert await asyncio.to_thread(started.wait, 3)
        deleting = asyncio.create_task(client.delete(f"/organizations/{organization['id']}"))
        # Event-based upload barrier proves the writer holds the parent before deletion.
        await asyncio.sleep(0.1)
        assert not deleting.done()
        release.set()
        await uploading
        response = await deleting
        assert response.status_code == 200, response.text
        async with sessions() as db:
            manifest = list(await db.scalars(select(OrganizationFileCleanup.object_key)))
            assert manifest == keys
            from app.core.errors import ForbiddenError

            with pytest.raises(ForbiddenError):
                await lock_organization_storage(db, organization["id"])
    finally:
        release.set()
        await asyncio.gather(uploading, *([deleting] if deleting else []), return_exceptions=True)


@pytest.mark.asyncio
async def test_deletion_inventories_unreferenced_tenant_objects(lifecycle, monkeypatch):
    client, sessions, _, _ = lifecycle
    organization = await create(client, "Unreferenced upload")
    object_key = f"documents/{organization['id']}/unreferenced.txt"
    monkeypatch.setattr(
        "app.services.organization_lifecycle_service.s3_service.list_file_keys",
        lambda prefix, limit, known_keys=None: (
            [object_key]
            if object_key.startswith(prefix) and object_key not in (known_keys or set())
            else []
        ),
    )
    response = await client.delete(f"/organizations/{organization['id']}")
    assert response.status_code == 200, response.text
    async with sessions() as db:
        assert list(await db.scalars(select(OrganizationFileCleanup.object_key))) == [object_key]


@pytest.mark.asyncio
async def test_invitation_roles_stay_scoped_and_member_limit_is_serialized(lifecycle, monkeypatch):
    client, sessions, _, password = lifecycle
    monkeypatch.setattr("app.services.invitation_service.send_user_invite_email", lambda **_: True)
    organization = await create(client, "Scoped invitations")
    async with sessions() as db:
        scoped_id = await db.scalar(
            select(Role.id).where(Role.organization_id == organization["id"], Role.name == "Admin")
        )
        org = await db.get(Organization, organization["id"])
        org.max_users = 1
        await db.commit()
    tokens = []
    for index, value in enumerate(("Admin", scoped_id)):
        response = await client.post(
            "/organizations/invitations",
            headers={"X-Organization-ID": organization["id"]},
            json={"email": f"member{index}@example.com", "full_name": "Member", "role": value},
        )
        assert response.status_code == 201, response.text
        token = response.json()["token"]
        tokens.append(token)
        status = await client.get(f"/organizations/invitations/{token}")
        assert status.json()["role"] == "Admin"
    async with sessions() as db:
        assert set(
            await db.scalars(
                select(OrganizationInvitation.role_id).where(
                    OrganizationInvitation.organization_id == organization["id"]
                )
            )
        ) == {scoped_id}
    responses = await asyncio.gather(
        *[
            client.post(f"/organizations/invitations/{token}/accept", json={"password": password})
            for token in tokens
        ]
    )
    assert sorted(response.status_code for response in responses) == [200, 409], [
        response.text for response in responses
    ]
    assert (
        next(response for response in responses if response.status_code == 200).json()["user"][
            "role"
        ]
        == "Admin"
    )
    async with sessions() as db:
        users = list(
            await db.scalars(select(User).where(User._organization_id == organization["id"]))
        )
        assert len(users) == 1 and users[0].role == scoped_id
        assert (
            await db.scalar(select(UserRole.role_id).where(UserRole.user_id == users[0].id))
            == scoped_id
        )
        subscription = await db.scalar(
            select(OrganizationSubscription).where(
                OrganizationSubscription.organization_id == organization["id"]
            )
        )
        assert subscription.current_users == 1


@pytest.mark.asyncio
async def test_safe_legacy_storage_ids_are_supported_and_overlapping_owners_block(
    lifecycle, monkeypatch
):
    client, sessions, _, _ = lifecycle
    async with sessions() as db:
        db.add_all(
            [
                Organization(id="org-1", name="Legacy"),
                Organization(id="org-1_other", name="Collision"),
            ]
        )
        await db.commit()
    blocked = await client.delete("/organizations/org-1")
    assert blocked.status_code == 409 and blocked.json()["code"] == "ORGANIZATION_STORAGE_CONFLICT"
    async with sessions() as db:
        # Controlled fixture only: remove the synthetic collision so the legacy
        # tenant's ownership is unambiguous.
        await db.delete(await db.get(Organization, "org-1_other"))
        await db.commit()
    key = "documents/org-1/unreferenced.txt"
    monkeypatch.setattr(
        "app.services.organization_lifecycle_service.s3_service.list_file_keys",
        lambda prefix, limit, known_keys=None: (
            [key] if key.startswith(prefix) and key not in (known_keys or set()) else []
        ),
    )
    response = await client.delete("/organizations/org-1")
    assert response.status_code == 200, response.text
    async with sessions() as db:
        assert await db.get(Organization, "org-1") is None
        assert list(await db.scalars(select(OrganizationFileCleanup.object_key))) == [key]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "field", ["customer_id", "checkout_operation_id", "invoice_id", "payment_provider"]
)
async def test_provider_linkage_without_completed_checkout_blocks_delete(lifecycle, field):
    client, sessions, _, _ = lifecycle
    organization = await create(client)
    async with sessions() as db:
        subscription = await db.scalar(
            select(OrganizationSubscription).where(
                OrganizationSubscription.organization_id == organization["id"]
            )
        )
        setattr(subscription, field, "controlled-provider-reference")
        await db.commit()
    response = await client.delete(f"/organizations/{organization['id']}")
    assert (
        response.status_code == 409 and response.json()["code"] == "ORGANIZATION_BILLING_PROTECTED"
    )


@pytest.mark.asyncio
async def test_online_prefix_inventory_is_bounded_before_storage_calls(lifecycle, monkeypatch):
    from app.models import Lead

    client, sessions, _, _ = lifecycle
    organization = await create(client)
    async with sessions() as db:
        db.add_all(
            [
                Lead(
                    organization_id=organization["id"],
                    title=f"Lead {index}",
                    company="Test",
                    contact_name="Test",
                    email=f"lead{index}@example.com",
                )
                for index in range(70)
            ]
        )
        await db.commit()
    calls = []
    monkeypatch.setattr(
        "app.services.organization_lifecycle_service.s3_service.list_file_keys",
        lambda prefix, limit, known_keys=None: calls.append(prefix) or [],
    )
    response = await client.delete(f"/organizations/{organization['id']}")
    assert (
        response.status_code == 409 and response.json()["code"] == "ORGANIZATION_STORAGE_CONFLICT"
    )
    assert calls == []


@pytest.mark.asyncio
async def test_acceptance_serializes_invite_create_resend_and_cancel(lifecycle, monkeypatch):
    from app.repositories.auth_repository import AuthRepository

    client, sessions, _, password = lifecycle
    organization = await create(client)
    monkeypatch.setattr("app.services.invitation_service.send_user_invite_email", lambda **_: True)
    original_assign = AuthRepository.assign_user_role
    for index, action in enumerate(("create", "resend", "cancel")):
        email = f"concurrent{index}@example.com"
        invited = await client.post(
            "/organizations/invitations",
            headers={"X-Organization-ID": organization["id"]},
            json={"email": email, "full_name": "Member", "role": "Admin"},
        )
        assert invited.status_code == 201, invited.text
        token = invited.json()["token"]
        async with sessions() as db:
            invitation_id = await db.scalar(
                select(OrganizationInvitation.id).where(OrganizationInvitation.token == token)
            )
        entered, release = asyncio.Event(), asyncio.Event()

        async def paused_assign(self, db, entered=entered, release=release, **kwargs):
            mapping = await original_assign(self, db, **kwargs)
            entered.set()
            await release.wait()
            return mapping

        monkeypatch.setattr(AuthRepository, "assign_user_role", paused_assign)
        accepting = asyncio.create_task(
            client.post(f"/organizations/invitations/{token}/accept", json={"password": password})
        )
        competing = None
        try:
            await asyncio.wait_for(entered.wait(), 3)
            if action == "create":
                competing = asyncio.create_task(
                    client.post(
                        "/organizations/invitations",
                        headers={"X-Organization-ID": organization["id"]},
                        json={"email": email, "full_name": "Member", "role": "Admin"},
                    )
                )
            else:
                competing = asyncio.create_task(
                    client.post(
                        f"/organizations/invitations/{invitation_id}/{action}",
                        headers={"X-Organization-ID": organization["id"]},
                    )
                )
            await asyncio.sleep(0.05)
            assert not competing.done()
            release.set()
            assert (await accepting).status_code == 200
            response = await competing
            assert response.status_code == (409 if action == "create" else 400), response.text
            async with sessions() as db:
                assert (await db.get(OrganizationInvitation, invitation_id)).status == "Accepted"
                assert (
                    await db.scalar(
                        select(func.count())
                        .select_from(OrganizationInvitation)
                        .where(OrganizationInvitation.email == email)
                    )
                    == 1
                )
        finally:
            release.set()
            await asyncio.gather(
                accepting, *([competing] if competing else []), return_exceptions=True
            )
