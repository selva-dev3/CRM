from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIException, NotFoundError
from app.models import User, UserInvitation
from app.repositories.auth_repository import AuthRepository
from app.schemas.crm_schemas import LoginRequest, RegisterRequest, TwoFactorVerifyRequest
from app.services.auth_service import AuthService


def _make_user(**overrides) -> User:
    defaults = {
        "id": "user-1",
        "name": "Alex Smith",
        "email": "alex@crm.com",
        "hashed_password": "hashed-secret",
        "role": "Admin",
        "organization_id": "org-1",
        "is_active": True,
        "created_at": datetime(2026, 8, 1, tzinfo=timezone.utc),
    }
    defaults.update(overrides)
    return User(**defaults)


def _make_invitation(**overrides) -> UserInvitation:
    defaults = {
        "id": "inv-1",
        "email": "invite@crm.com",
        "token": "ABCDEFGHIJKLMN",
        "role": "Sales Executive",
        "organization_id": "org-1",
        "status": "pending",
    }
    defaults.update(overrides)
    return UserInvitation(**defaults)


def _service_with(repo: AuthRepository) -> AuthService:
    return AuthService(repository=repo)


@pytest.mark.asyncio
async def test_login_returns_token_and_user(monkeypatch):
    user = _make_user(role="Admin")
    repo = AuthRepository()
    repo.get_user_by_email = AsyncMock(return_value=user)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    monkeypatch.setattr(
        "app.services.auth_service.verify_password", lambda pwd, hashed: True
    )
    monkeypatch.setattr(
        "app.services.auth_service.create_access_token", lambda user_id: f"token-{user_id}"
    )
    repo.get_role_name_by_id = AsyncMock(return_value=None)
    repo.get_user_role_id = AsyncMock(return_value=None)
    repo.role_ids_for_user = AsyncMock(return_value=["role-1"])
    repo.role_ids_by_name = AsyncMock(return_value=["role-1"])
    repo.permission_keys_for_roles = AsyncMock(return_value=["leads:all", "deals:all"])

    result = await service.login(db, LoginRequest(email="alex@crm.com", password="secret"))

    assert result["access_token"] == "token-user-1"
    assert result["token_type"] == "bearer"
    assert result["user"]["role"] == "Admin"
    assert "deals:all" in result["user"]["permissions"]


@pytest.mark.asyncio
async def test_login_rejects_bad_password():
    user = _make_user()
    repo = AuthRepository()
    repo.get_user_by_email = AsyncMock(return_value=user)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(APIException) as exc_info:
        await service.login(db, LoginRequest(email="alex@crm.com", password="wrong"))
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_login_raises_when_user_missing():
    repo = AuthRepository()
    repo.get_user_by_email = AsyncMock(return_value=None)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(APIException) as exc_info:
        await service.login(db, LoginRequest(email="nobody@crm.com", password="x"))
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_admin_user_gets_all_permissions(monkeypatch):
    user = _make_user(role="Admin")
    repo = AuthRepository()
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    repo.role_ids_for_user = AsyncMock(return_value=["role-1"])
    repo.role_ids_by_name = AsyncMock(return_value=["role-1"])
    repo.permission_keys_for_roles = AsyncMock(return_value=["a:read", "b:write", "c:read"])

    result = await service.get_user_permissions(db, user, resolved_role_name="Admin")

    assert result == sorted(["a:read", "b:write", "c:read"])


@pytest.mark.asyncio
async def test_get_user_role_name_resolves_uuid_role():
    repo = AuthRepository()
    repo.get_role_name_by_id = AsyncMock(return_value="Sales Manager")
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    user = _make_user(role="00000000-0000-0000-0000-000000000001")
    assert await service.get_user_role_name(db, user) == "Sales Manager"


@pytest.mark.asyncio
async def test_register_creates_org_and_user(monkeypatch):
    org = type("O", (), {"id": "org-9"})()
    user = _make_user()
    repo = AuthRepository()
    repo.get_user_by_email = AsyncMock(return_value=None)
    repo.create_org = AsyncMock(return_value=org)
    repo.create_user = AsyncMock(return_value=user)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    monkeypatch.setattr("app.services.auth_service.get_password_hash", lambda pwd: f"h-{pwd}")

    result = await service.register(db, RegisterRequest(name="Alex", email="a@crm.com", password="secret", organization_name="Acme"))

    assert result["user_id"] == "user-1"
    assert result["org_id"] == "org-9"
    created = repo.create_user.await_args.kwargs["data"]
    assert created["hashed_password"] == "h-secret"


@pytest.mark.asyncio
async def test_verify_2fa_accepts_correct_code():
    service = _service_with(AuthRepository())
    assert await service.verify_2fa(TwoFactorVerifyRequest(code="123456")) is not None

    with pytest.raises(APIException) as exc_info:
        await service.verify_2fa(TwoFactorVerifyRequest(code="000000"))
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_google_oauth_requires_id_token():
    service = _service_with(AuthRepository())

    from app.schemas.crm_schemas import OAuthLoginRequest

    with pytest.raises(APIException) as exc_info:
        await service.google_oauth(AsyncMock(spec=AsyncSession), OAuthLoginRequest(provider="google", id_token=""))
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_revoke_session_not_found():
    repo = AuthRepository()
    repo.get_session_by_id = AsyncMock(return_value=None)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(NotFoundError):
        await service.revoke_session(db, "session-x")


@pytest.mark.asyncio
async def test_forgot_password_not_found():
    repo = AuthRepository()
    repo.get_user_by_email = AsyncMock(return_value=None)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    from app.schemas.crm_schemas import PasswordResetRequest

    with pytest.raises(NotFoundError):
        await service.forgot_password(db, PasswordResetRequest(email="ghost@crm.com"))


@pytest.mark.asyncio
async def test_accept_invitation_marks_accepted(monkeypatch):
    inv = _make_invitation()
    user = _make_user()
    repo = AuthRepository()
    repo.get_invitation_by_token = AsyncMock(return_value=inv)
    repo.get_invitation_by_email = AsyncMock(return_value=None)
    repo.get_first_org = AsyncMock(return_value=type("O", (), {"id": "org-1"})())
    repo.get_user_by_email = AsyncMock(return_value=None)
    repo.create_user = AsyncMock(return_value=user)
    repo.list_invitations_by_email = AsyncMock(return_value=[])
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    monkeypatch.setattr("app.services.auth_service.get_password_hash", lambda pwd: "hashed")
    monkeypatch.setattr("app.services.auth_service.create_access_token", lambda user_id: "tok")
    repo.get_user_role_id = AsyncMock(return_value=None)
    repo.all_permission_keys = AsyncMock(return_value=[])

    from app.schemas.crm_schemas import AcceptInviteRequest

    result = await service.accept_auth_user_invitation(
        db, AcceptInviteRequest(token="ABCDEFGHIJKLMN", name="Alex", password="secret")
    )

    assert inv.status == "accepted"
    assert result["user_id"] == "user-1"