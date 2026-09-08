from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import SecretStr
from sqlalchemy import inspect

from app.api.v1.deps import apply_organization_context, require_platform_admin
from app.core.errors import ConflictError, ForbiddenError
from app.core.permissions import (
    effective_organization_id,
    ensure_can_assign_role,
    ensure_tenant_managed_user,
)
from app.models import User
from app.services.auth_service import AuthService
from app.services.organization_service import OrganizationDomainService
from app.services.platform_admin_service import PlatformAdminService


def platform_user():
    return User(
        id="platform",
        name="Platform",
        email="platform@example.com",
        role="Super Admin",
        is_platform_admin=True,
        organization_id=None,
        is_active=True,
    )


@pytest.mark.asyncio
async def test_platform_context_does_not_change_persisted_membership():
    user = platform_user()
    db = SimpleNamespace(
        get=AsyncMock(return_value=SimpleNamespace(is_active=True, status="active"))
    )
    await apply_organization_context(db, user, "org-a")
    assert effective_organization_id(user) == "org-a"
    assert user.organization_id == "org-a"
    assert user._organization_id is None
    assert inspect(user).attrs._organization_id.history.added == [None]
    await apply_organization_context(db, user, "org-b")
    assert user.organization_id == "org-b"
    assert user._organization_id is None
    await apply_organization_context(db, user, None)
    assert user.organization_id is None
    assert effective_organization_id(user) is None


@pytest.mark.asyncio
async def test_normal_user_cannot_spoof_organization_header():
    user = User(id="tenant", organization_id="org-a", is_platform_admin=False)
    db = SimpleNamespace(get=AsyncMock())
    with pytest.raises(ForbiddenError):
        await apply_organization_context(db, user, "org-b")
    db.get.assert_not_awaited()


@pytest.mark.asyncio
async def test_platform_user_can_authenticate_without_an_organization():
    db = SimpleNamespace(get=AsyncMock())
    await AuthService._validate_session_principal(db, platform_user())
    await apply_organization_context(db, platform_user(), None)
    db.get.assert_not_awaited()


@pytest.mark.asyncio
async def test_platform_context_rejects_inactive_or_missing_organization():
    for org in (None, SimpleNamespace(is_active=False, status="inactive")):
        db = SimpleNamespace(get=AsyncMock(return_value=org))
        with pytest.raises(ForbiddenError):
            await apply_organization_context(db, platform_user(), "unavailable")


@pytest.mark.asyncio
async def test_platform_endpoint_rejects_normal_admin_and_api_keys():
    for user in (
        User(role="Admin", is_platform_admin=False),
        SimpleNamespace(is_platform_admin=True, _api_key_scopes={"api:write"}),
    ):
        with pytest.raises(ForbiddenError):
            await require_platform_admin(user)
    assert await require_platform_admin(platform_user())


@pytest.mark.parametrize("actor_is_platform", [False, True])
def test_no_actor_can_create_second_platform_account_through_role_assignment(actor_is_platform):
    with pytest.raises(ForbiddenError):
        ensure_can_assign_role(actor_is_super_admin=actor_is_platform, target_is_super_admin=True)


def test_platform_user_protection_is_independent_of_email():
    with pytest.raises(ForbiddenError):
        ensure_tenant_managed_user(platform_user())


@pytest.mark.asyncio
async def test_member_removal_cannot_delete_platform_user():
    repo = SimpleNamespace(
        get_user_by_id=AsyncMock(return_value=platform_user()), delete_user=AsyncMock()
    )
    actor = User(id="tenant-admin", organization_id="org-a", role="Admin")
    with pytest.raises(ForbiddenError):
        await OrganizationDomainService(repo).remove_member(MagicMock(), "platform", actor)
    repo.delete_user.assert_not_awaited()


@pytest.mark.asyncio
async def test_provisioning_requires_matching_existing_identity():
    repo = SimpleNamespace(
        lock_platform_provisioning=AsyncMock(),
        get_platform_admin=AsyncMock(return_value=platform_user()),
        get_unique_email_owner=AsyncMock(return_value=None),
    )
    db = SimpleNamespace(rollback=AsyncMock())
    with pytest.raises(ConflictError):
        await PlatformAdminService(repo).provision(
            db,
            email="platform@example.com",
            password=SecretStr("test-only-bootstrap-value"),
            existing_user_id="wrong-id",
        )
    db.rollback.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("commit_fails", [False, True])
async def test_first_platform_provisioning_commits_or_propagates_failure(commit_fails):
    user = platform_user()
    repo = SimpleNamespace(
        lock_platform_provisioning=AsyncMock(),
        get_platform_admin=AsyncMock(return_value=None),
        get_unique_email_owner=AsyncMock(return_value=None),
        create_user=AsyncMock(return_value=user),
        assign_user_role=AsyncMock(),
        revoke_all_user_sessions=AsyncMock(),
        invalidate_password_resets=AsyncMock(),
        invalidate_magic_links=AsyncMock(),
    )
    service = PlatformAdminService(repo)
    service.roles = SimpleNamespace(
        get_global_role_by_names=AsyncMock(return_value=SimpleNamespace(id="global-role"))
    )
    failure = RuntimeError("Commit failed")
    db = SimpleNamespace(
        flush=AsyncMock(),
        commit=AsyncMock(side_effect=failure if commit_fails else None),
        rollback=AsyncMock(),
    )

    async def provision():
        return await service.provision(
            db, email="platform@example.com", password=SecretStr("test-only-bootstrap-value")
        )

    if commit_fails:
        with pytest.raises(RuntimeError, match="Commit failed"):
            await provision()
        db.rollback.assert_awaited_once()
    else:
        assert await provision() == user.id
        db.commit.assert_awaited_once()
        db.rollback.assert_not_awaited()
    created = repo.create_user.call_args.kwargs["data"]
    assert created["is_platform_admin"] is True
    assert created["organization_id"] is None
    assert created["hashed_password"].startswith("$2")


@pytest.mark.asyncio
async def test_email_conflict_never_merges_users():
    repo = SimpleNamespace(
        lock_platform_provisioning=AsyncMock(),
        get_platform_admin=AsyncMock(return_value=platform_user()),
        get_unique_email_owner=AsyncMock(return_value=SimpleNamespace(id="another-user")),
    )
    db = SimpleNamespace(rollback=AsyncMock(), commit=AsyncMock())
    with pytest.raises(ConflictError, match="another account"):
        await PlatformAdminService(repo).provision(
            db,
            email="platform@example.com",
            password=SecretStr("test-only-bootstrap-value"),
            existing_user_id="platform",
        )
    db.commit.assert_not_awaited()
    db.rollback.assert_awaited_once()
