from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError
from app.models import SubscriptionPlan, User
from app.models.rbac import Role
from app.schemas.organization_invitation_schemas import OrganizationInviteRequest
from app.services.invitation_service import (
    _require_free_plan,
    _resolve_invitation_role,
    create_organization_user_invitation,
    get_and_validate_invitation_by_token,
    list_organization_invitations,
)


@pytest.mark.asyncio
async def test_require_free_plan_fails_when_database_catalog_is_missing():
    db = AsyncMock(spec=AsyncSession)
    db.scalar.return_value = None

    with pytest.raises(HTTPException) as exc_info:
        await _require_free_plan(db)

    assert exc_info.value.status_code == 503


@pytest.mark.asyncio
async def test_require_free_plan_returns_active_database_record():
    plan = SubscriptionPlan(id="plan-free", name="Free", slug="free", is_active=True)
    db = AsyncMock(spec=AsyncSession)
    db.scalar.return_value = plan

    assert await _require_free_plan(db) is plan


@pytest.mark.asyncio
async def test_platform_admin_lists_invitations_in_selected_organization():
    user = _make_user(organization_id=None, is_platform_admin=True)
    user.__dict__["_request_organization_id"] = "org-selected"
    db = AsyncMock(spec=AsyncSession)
    count_result = MagicMock()
    count_result.scalar.return_value = 0
    rows_result = MagicMock()
    rows_result.scalars.return_value.all.return_value = []
    db.execute = AsyncMock(side_effect=[count_result, rows_result])

    result = await list_organization_invitations(db, user)

    assert result.total == 0
    statements = [str(call.args[0]) for call in db.execute.await_args_list]
    assert all("organization_invitations.organization_id" in statement for statement in statements)


def _make_role(**overrides) -> Role:
    values = {
        "id": "role-1",
        "name": "role-1",
        "organization_id": "org-1",
        "is_system_role": False,
    }
    values.update(overrides)
    return Role(**values)


def _make_user(**overrides) -> User:
    defaults = {
        "id": "user-1",
        "name": "Alex Smith",
        "email": "alex@crm.com",
        "hashed_password": "hashed",
        "role": "role-1",
        "organization_id": "org-1",
        "is_active": True,
        "created_at": datetime(2026, 8, 1, tzinfo=UTC),
    }
    defaults.update(overrides)
    return User(**defaults)


def _make_org(**overrides):
    defaults = {
        "id": "org-1",
        "name": "Acme Inc",
        "status": "active",
        "is_active": True,
    }
    defaults.update(overrides)
    return type("Org", (), defaults)()


@pytest.mark.asyncio
@pytest.mark.parametrize("is_system_role", [True, False])
async def test_resolve_invitation_role_assigns_system_and_custom_roles(is_system_role):
    db = AsyncMock(spec=AsyncSession)
    role = _make_role(
        name="Sales Manager",
        organization_id="org-1",
        is_system_role=is_system_role,
    )
    db.scalar.return_value = role

    result = await _resolve_invitation_role(
        db,
        _make_user(),
        role.id,
        target_organization_id="org-1",
    )

    assert result is role


@pytest.mark.asyncio
async def test_resolve_invitation_role_rejects_foreign_tenant_role():
    db = AsyncMock(spec=AsyncSession)
    db.scalar.return_value = _make_role(organization_id="org-2")

    with pytest.raises(HTTPException) as exc_info:
        await _resolve_invitation_role(
            db,
            _make_user(organization_id="org-1"),
            "role-1",
            target_organization_id="org-1",
        )

    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_list_organization_invitations_is_tenant_scoped():
    count_result = MagicMock()
    count_result.scalar.return_value = 0
    list_result = MagicMock()
    list_result.scalars.return_value.all.return_value = []
    db = AsyncMock(spec=AsyncSession)
    db.execute.side_effect = [count_result, list_result]

    result = await list_organization_invitations(db, _make_user(organization_id="org-1"))

    assert result.total == 0
    for call in db.execute.await_args_list:
        assert "organization_invitations.organization_id" in str(call.args[0])


@pytest.mark.asyncio
async def test_create_organization_user_invitation_uses_current_user_org(monkeypatch):
    db = AsyncMock(spec=AsyncSession)
    db.scalar = AsyncMock(side_effect=[_make_org(), None, None, None, None, None])
    current_user = _make_user(organization_id="org-1")

    monkeypatch.setattr(
        "app.services.invitation_service.send_user_invite_email", lambda **kwargs: None
    )
    # Role resolution is DB-backed since the RBAC hardening; stub it so this
    # test stays focused on org derivation from the authenticated user.
    monkeypatch.setattr(
        "app.services.invitation_service._resolve_invitation_role",
        AsyncMock(return_value=_make_role()),
    )
    monkeypatch.setattr(
        "app.repositories.organization_lifecycle_repository.OrganizationLifecycleRepository.lock_invitation_organization",
        AsyncMock(return_value=_make_org()),
    )

    payload = OrganizationInviteRequest(email="new@crm.com", role="role-1")
    result = await create_organization_user_invitation(db, payload, current_user)

    assert result.token
    invitation = db.add.call_args_list[0].args[0]
    assert invitation.organization_id == "org-1"
    assert invitation.email == "new@crm.com"
    assert invitation.role_id == "role-1"


@pytest.mark.asyncio
async def test_create_invitation_rejects_organization_deleted_before_parent_lock(monkeypatch):
    db = AsyncMock(spec=AsyncSession)
    db.scalar = AsyncMock(return_value=_make_org())
    resolve_role = AsyncMock(return_value=_make_role())
    monkeypatch.setattr("app.services.invitation_service._resolve_invitation_role", resolve_role)
    monkeypatch.setattr(
        "app.repositories.organization_lifecycle_repository.OrganizationLifecycleRepository.lock_invitation_email",
        AsyncMock(),
    )
    monkeypatch.setattr(
        "app.repositories.organization_lifecycle_repository.OrganizationLifecycleRepository.lock_invitation_organization",
        AsyncMock(return_value=None),
    )

    with pytest.raises(HTTPException) as exc_info:
        await create_organization_user_invitation(
            db,
            OrganizationInviteRequest(email="new@crm.com", role="role-1"),
            _make_user(organization_id="org-1"),
        )

    assert exc_info.value.status_code == 404
    resolve_role.assert_not_awaited()
    db.add.assert_not_called()
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_expired_invitation_status_update_is_conditional_against_concurrent_management():
    invitation = SimpleNamespace(
        id="invitation-1",
        token="expired-token",  # noqa: S106 - synthetic expired invitation fixture
        status="Pending",
        expires_at=datetime.now(UTC) - timedelta(minutes=1),
    )
    db = AsyncMock(spec=AsyncSession)
    db.scalar = AsyncMock(return_value=invitation)

    with pytest.raises(HTTPException) as exc_info:
        await get_and_validate_invitation_by_token(db, "expired-token")

    assert exc_info.value.status_code == 410
    assert invitation.status == "Pending"
    db.commit.assert_awaited_once()
    statement = db.execute.await_args.args[0]
    sql = str(statement)
    assert "organization_invitations.id" in sql
    assert "organization_invitations.token" in sql
    assert "organization_invitations.status" in sql
    assert "organization_invitations.expires_at" in sql
    assert statement.get_execution_options()["synchronize_session"] is False


@pytest.mark.asyncio
async def test_create_organization_user_invitation_ignores_client_organization_id(monkeypatch):
    """A client-supplied organization_id must never be trusted — the invitation
    always lands in the authenticated user's current organization."""
    db = AsyncMock(spec=AsyncSession)
    db.scalar = AsyncMock(side_effect=[_make_org(), None, None, None, None, None])
    current_user = _make_user(organization_id="org-1")

    monkeypatch.setattr(
        "app.services.invitation_service.send_user_invite_email", lambda **kwargs: None
    )
    monkeypatch.setattr(
        "app.services.invitation_service._resolve_invitation_role",
        AsyncMock(return_value=_make_role()),
    )
    monkeypatch.setattr(
        "app.repositories.organization_lifecycle_repository.OrganizationLifecycleRepository.lock_invitation_organization",
        AsyncMock(return_value=_make_org()),
    )

    # organization_id is not part of the request contract anymore; even if a
    # client sneaks it into the body it is ignored by the schema.
    payload = OrganizationInviteRequest(
        email="new@crm.com",
        role="role-1",
        organization_id="org-hacked",
    )
    result = await create_organization_user_invitation(db, payload, current_user)

    invitation = db.add.call_args_list[0].args[0]
    assert invitation.organization_id == "org-1"
    assert result.message


@pytest.mark.asyncio
async def test_create_organization_user_invitation_requires_current_org():
    db = AsyncMock(spec=AsyncSession)
    current_user = _make_user(organization_id=None)
    payload = OrganizationInviteRequest(email="new@crm.com", role="role-1")

    with pytest.raises(HTTPException) as exc_info:
        await create_organization_user_invitation(db, payload, current_user)
    assert exc_info.value.status_code == 403
    db.add.assert_not_called()


@pytest.mark.asyncio
async def test_create_organization_user_invitation_rejects_inactive_org():
    db = AsyncMock(spec=AsyncSession)
    db.scalar = AsyncMock(side_effect=[_make_org(status="inactive"), None, None, None])
    current_user = _make_user(organization_id="org-1")
    payload = OrganizationInviteRequest(email="new@crm.com", role="role-1")

    with pytest.raises(HTTPException) as exc_info:
        await create_organization_user_invitation(db, payload, current_user)
    assert exc_info.value.status_code == 403
    db.add.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("is_active", [True, False])
async def test_create_organization_user_invitation_rejects_existing_account(monkeypatch, is_active):
    db = AsyncMock(spec=AsyncSession)
    existing = _make_user(id="user-existing", email="taken@crm.com", is_active=is_active)
    db.scalar = AsyncMock(side_effect=[_make_org(), None, None, None, None, existing])
    current_user = _make_user(organization_id="org-1")

    monkeypatch.setattr(
        "app.services.invitation_service.send_user_invite_email", lambda **kwargs: None
    )
    monkeypatch.setattr(
        "app.services.invitation_service._resolve_invitation_role",
        AsyncMock(return_value=_make_role()),
    )
    monkeypatch.setattr(
        "app.repositories.organization_lifecycle_repository.OrganizationLifecycleRepository.lock_invitation_organization",
        AsyncMock(return_value=_make_org()),
    )

    payload = OrganizationInviteRequest(email="taken@crm.com", role="role-1")

    with pytest.raises(HTTPException) as exc_info:
        await create_organization_user_invitation(db, payload, current_user)
    assert exc_info.value.status_code == 409
    db.add.assert_not_called()


@pytest.mark.asyncio
async def test_create_organization_invitation_rejects_pending_legacy_invitation(monkeypatch):
    db = AsyncMock(spec=AsyncSession)
    db.scalar = AsyncMock(side_effect=[_make_org(), None, None, "legacy-invitation"])
    monkeypatch.setattr(
        "app.services.invitation_service._resolve_invitation_role",
        AsyncMock(return_value=_make_role()),
    )
    monkeypatch.setattr(
        "app.repositories.organization_lifecycle_repository.OrganizationLifecycleRepository.lock_invitation_organization",
        AsyncMock(return_value=_make_org()),
    )
    with pytest.raises(ConflictError, match="pending invitation"):
        await create_organization_user_invitation(
            db, OrganizationInviteRequest(email="new@crm.com", role="role-1"), _make_user()
        )
    db.add.assert_not_called()
    db.commit.assert_not_awaited()
