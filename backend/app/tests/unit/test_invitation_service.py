from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.schemas.organization_invitation_schemas import OrganizationInviteRequest
from app.services.invitation_service import create_organization_user_invitation


def _make_user(**overrides) -> User:
    defaults = {
        "id": "user-1",
        "name": "Alex Smith",
        "email": "alex@crm.com",
        "hashed_password": "hashed",
        "role": "role-1",
        "organization_id": "org-1",
        "is_active": True,
        "created_at": datetime(2026, 8, 1, tzinfo=timezone.utc),
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
async def test_create_organization_user_invitation_uses_current_user_org(monkeypatch):
    db = AsyncMock(spec=AsyncSession)
    db.scalar = AsyncMock(side_effect=[_make_org(), None, None, None])
    current_user = _make_user(organization_id="org-1")

    monkeypatch.setattr(
        "app.services.invitation_service.send_user_invite_email", lambda **kwargs: None
    )

    payload = OrganizationInviteRequest(email="new@crm.com", role="role-1")
    result = await create_organization_user_invitation(db, payload, current_user)

    assert result.token
    invitation = db.add.call_args_list[0].args[0]
    assert invitation.organization_id == "org-1"
    assert invitation.email == "new@crm.com"
    assert invitation.role_id == "role-1"


@pytest.mark.asyncio
async def test_create_organization_user_invitation_ignores_client_organization_id(monkeypatch):
    """A client-supplied organization_id must never be trusted — the invitation
    always lands in the authenticated user's current organization."""
    db = AsyncMock(spec=AsyncSession)
    db.scalar = AsyncMock(side_effect=[_make_org(), None, None, None])
    current_user = _make_user(organization_id="org-1")

    monkeypatch.setattr(
        "app.services.invitation_service.send_user_invite_email", lambda **kwargs: None
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
async def test_create_organization_user_invitation_rejects_existing_active_user(monkeypatch):
    db = AsyncMock(spec=AsyncSession)
    existing = _make_user(id="user-existing", email="taken@crm.com")
    db.scalar = AsyncMock(side_effect=[_make_org(), None, existing, None])
    current_user = _make_user(organization_id="org-1")

    monkeypatch.setattr(
        "app.services.invitation_service.send_user_invite_email", lambda **kwargs: None
    )

    payload = OrganizationInviteRequest(email="taken@crm.com", role="role-1")

    with pytest.raises(HTTPException) as exc_info:
        await create_organization_user_invitation(db, payload, current_user)
    assert exc_info.value.status_code == 409
    db.add.assert_not_called()
