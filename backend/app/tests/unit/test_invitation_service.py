from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.schemas.organization_invitation_schemas import OrganizationInviteRequest
from app.services.invitation_service import create_organization_user_invitation


def _make_user(**overrides) -> User:
    defaults = {
        "id": "user-1",
        "name": "Super Admin",
        "email": "superadmin@gmail.com",
        "hashed_password": "hashed",
        "role": "super_admin",
        "organization_id": None,
        "is_active": True,
        "created_at": datetime(2026, 8, 1, tzinfo=UTC),
    }
    defaults.update(overrides)
    return User(**defaults)


def _make_org(**overrides):
    defaults = {"id": "org-1", "name": "Acme Inc", "status": "active", "is_active": True}
    defaults.update(overrides)
    return type("Org", (), defaults)()


def _make_sub(**overrides):
    defaults = {"id": "sub-1"}
    defaults.update(overrides)
    return type("Sub", (), defaults)()


def _make_role(**overrides):
    defaults = {"id": "role-1", "name": "Sales Manager", "organization_id": None, "is_system_role": False}
    defaults.update(overrides)
    return type("Role", (), defaults)()


async def test_superadmin_can_target_requested_org(monkeypatch):
    mock_email = Mock()
    monkeypatch.setattr("app.services.invitation_service.send_user_invite_email", mock_email)
    db = AsyncMock(spec=AsyncSession)
    current_user = _make_user()
    db.scalar.side_effect = [
        _make_org(),          # org lookup for target
        _make_sub(),          # subscription lookup
        _make_role(),         # role lookup
        None,                 # no existing user
        None,                 # no existing pending invitation
    ]
    payload = OrganizationInviteRequest(
        email="member@acme.com",
        full_name="Jane Smith",
        role="role-1",
        organization_id="org-1",
    )

    result = await create_organization_user_invitation(db, payload, current_user)

    assert result.message == "Invitation sent successfully to member@acme.com"
    assert result.token.startswith("inv_")
    added_invitation = db.add.call_args_list[0][0][0]
    assert added_invitation.organization_id == "org-1"
    assert added_invitation.role_id == "role-1"
    mock_email.assert_called_once()
    assert mock_email.call_args.kwargs["email_to"] == "member@acme.com"


async def test_non_superadmin_foreign_org_rejected(monkeypatch):
    mock_email = Mock()
    monkeypatch.setattr("app.services.invitation_service.send_user_invite_email", mock_email)
    db = AsyncMock(spec=AsyncSession)
    current_user = _make_user(role="Admin", email="admin@acme.com", organization_id="org-1")
    payload = OrganizationInviteRequest(email="member@acme.com", role="role-1", organization_id="org-999")

    with pytest.raises(HTTPException) as exc_info:
        await create_organization_user_invitation(db, payload, current_user)

    assert exc_info.value.status_code == 403
    db.scalar.assert_not_called()
    mock_email.assert_not_called()


async def test_non_superadmin_without_org_id_derives_own_org(monkeypatch):
    mock_email = Mock()
    monkeypatch.setattr("app.services.invitation_service.send_user_invite_email", mock_email)
    db = AsyncMock(spec=AsyncSession)
    current_user = _make_user(role="Admin", email="admin@acme.com", organization_id="org-1")
    db.scalar.side_effect = [
        _make_org(),          # own org lookup
        None,                 # no subscription
        _make_role(),         # role lookup
        None,                 # no existing user
        None,                 # no existing pending invitation
    ]
    payload = OrganizationInviteRequest(email="member@acme.com", role="role-1")

    result = await create_organization_user_invitation(db, payload, current_user)

    assert result.token.startswith("inv_")
    added_invitation = db.add.call_args_list[0][0][0]
    assert added_invitation.organization_id == "org-1"


async def test_non_superadmin_sending_org_id_rejected(monkeypatch):
    mock_email = Mock()
    monkeypatch.setattr("app.services.invitation_service.send_user_invite_email", mock_email)
    db = AsyncMock(spec=AsyncSession)
    current_user = _make_user(role="Admin", email="admin@acme.com", organization_id="org-1")
    payload = OrganizationInviteRequest(email="member@acme.com", role="role-1", organization_id="org-1")

    with pytest.raises(HTTPException) as exc_info:
        await create_organization_user_invitation(db, payload, current_user)

    assert exc_info.value.status_code == 403
    db.scalar.assert_not_called()
    mock_email.assert_not_called()


async def test_user_without_org_rejected(monkeypatch):
    mock_email = Mock()
    monkeypatch.setattr("app.services.invitation_service.send_user_invite_email", mock_email)
    db = AsyncMock(spec=AsyncSession)
    current_user = _make_user(role="Admin", email="admin@acme.com", organization_id=None)
    payload = OrganizationInviteRequest(email="member@acme.com", role="role-1")

    with pytest.raises(HTTPException) as exc_info:
        await create_organization_user_invitation(db, payload, current_user)

    assert exc_info.value.status_code == 403
    db.scalar.assert_not_called()
    mock_email.assert_not_called()


async def test_target_org_not_found_rejected(monkeypatch):
    mock_email = Mock()
    monkeypatch.setattr("app.services.invitation_service.send_user_invite_email", mock_email)
    db = AsyncMock(spec=AsyncSession)
    current_user = _make_user()
    db.scalar.side_effect = [None]
    payload = OrganizationInviteRequest(email="member@acme.com", role="role-1", organization_id="org-missing")

    with pytest.raises(HTTPException) as exc_info:
        await create_organization_user_invitation(db, payload, current_user)

    assert exc_info.value.status_code == 404
    mock_email.assert_not_called()


async def test_inactive_target_org_rejected(monkeypatch):
    mock_email = Mock()
    monkeypatch.setattr("app.services.invitation_service.send_user_invite_email", mock_email)
    db = AsyncMock(spec=AsyncSession)
    current_user = _make_user()
    db.scalar.side_effect = [_make_org(status="inactive", is_active=False)]
    payload = OrganizationInviteRequest(email="member@acme.com", role="role-1", organization_id="org-1")

    with pytest.raises(HTTPException) as exc_info:
        await create_organization_user_invitation(db, payload, current_user)

    assert exc_info.value.status_code == 403
    mock_email.assert_not_called()


async def test_invalid_role_rejected(monkeypatch):
    mock_email = Mock()
    monkeypatch.setattr("app.services.invitation_service.send_user_invite_email", mock_email)
    db = AsyncMock(spec=AsyncSession)
    current_user = _make_user()
    db.scalar.side_effect = [
        _make_org(),          # org lookup
        None,                 # no subscription
        None,                 # role lookup -> not found
    ]
    payload = OrganizationInviteRequest(email="member@acme.com", role="role-unknown", organization_id="org-1")

    with pytest.raises(HTTPException) as exc_info:
        await create_organization_user_invitation(db, payload, current_user)

    assert exc_info.value.status_code == 400
    mock_email.assert_not_called()


async def test_role_from_other_org_rejected(monkeypatch):
    mock_email = Mock()
    monkeypatch.setattr("app.services.invitation_service.send_user_invite_email", mock_email)
    db = AsyncMock(spec=AsyncSession)
    current_user = _make_user()
    db.scalar.side_effect = [
        _make_org(),          # org lookup
        None,                 # no subscription
        _make_role(organization_id="org-2"),  # role belongs to another org
    ]
    payload = OrganizationInviteRequest(email="member@acme.com", role="role-1", organization_id="org-1")

    with pytest.raises(HTTPException) as exc_info:
        await create_organization_user_invitation(db, payload, current_user)

    assert exc_info.value.status_code == 400
    mock_email.assert_not_called()


async def test_system_role_rejected(monkeypatch):
    mock_email = Mock()
    monkeypatch.setattr("app.services.invitation_service.send_user_invite_email", mock_email)
    db = AsyncMock(spec=AsyncSession)
    current_user = _make_user()
    db.scalar.side_effect = [
        _make_org(),          # org lookup
        None,                 # no subscription
        _make_role(is_system_role=True),  # protected system role
    ]
    payload = OrganizationInviteRequest(email="member@acme.com", role="role-1", organization_id="org-1")

    with pytest.raises(HTTPException) as exc_info:
        await create_organization_user_invitation(db, payload, current_user)

    assert exc_info.value.status_code == 403
    mock_email.assert_not_called()


async def test_existing_active_user_rejected(monkeypatch):
    mock_email = Mock()
    monkeypatch.setattr("app.services.invitation_service.send_user_invite_email", mock_email)
    db = AsyncMock(spec=AsyncSession)
    current_user = _make_user()
    existing_active = _make_user(id="user-2", email="member@acme.com", role="Admin", organization_id="org-1")
    db.scalar.side_effect = [
        _make_org(),          # org lookup
        None,                 # no subscription
        _make_role(),         # role lookup
        existing_active,      # existing active user
    ]
    payload = OrganizationInviteRequest(email="member@acme.com", role="role-1", organization_id="org-1")

    with pytest.raises(HTTPException) as exc_info:
        await create_organization_user_invitation(db, payload, current_user)

    assert exc_info.value.status_code == 409
    mock_email.assert_not_called()
