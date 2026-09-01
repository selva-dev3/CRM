from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import Any
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIException, NotFoundError
from app.models import PasswordReset, User, UserInvitation
from app.repositories.auth_repository import AuthRepository
from app.schemas.crm_schemas import (
    LoginRequest,
    PasswordResetConfirmRequest,
    PasswordResetRequest,
    RegisterRequest,
    TwoFactorVerifyRequest,
)
from app.services.auth_service import AuthService

VALID_INPUT = "secret"
INVALID_INPUT = "wrong"
MISSING_USER_INPUT = "x"
MALFORMED_STORED_VALUE = "malformed-hash"
REGISTRATION_INPUT = "password123"
EXPECTED_REGISTRATION_HASH = "h-password123"
OLD_STORED_VALUE = "old-hash"
TEST_CODE = "ABCDEFGHIJKLMN"
STORED_DIGEST = "digest"
NEW_INPUT = "new-password"
EXPECTED_ACCESS_VALUE = "token-user-1"
EXPECTED_AUTH_SCHEME = "bearer"


def _make_user(**overrides) -> User:
    defaults = {
        "id": "user-1",
        "name": "Alex Smith",
        "email": "alex@crm.com",
        "hashed_password": "hashed-secret",
        "role": "Admin",
        "organization_id": "org-1",
        "is_active": True,
        "created_at": datetime(2026, 8, 1, tzinfo=UTC),
    }
    defaults.update(overrides)
    return User(**defaults)


def _make_invitation(**overrides) -> UserInvitation:
    defaults = {
        "id": "inv-1",
        "email": "invite@crm.com",
        "token": TEST_CODE,
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
    repo: Any = AuthRepository()
    repo.get_user_by_email = AsyncMock(return_value=user)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    monkeypatch.setattr("app.services.auth_service.verify_password", lambda pwd, hashed: True)
    monkeypatch.setattr(
        "app.services.auth_service.create_access_token", lambda user_id: f"token-{user_id}"
    )
    repo.get_role_name_by_id = AsyncMock(return_value=None)
    repo.get_user_role_id = AsyncMock(return_value=None)
    repo.role_ids_for_user = AsyncMock(return_value=["role-1"])
    repo.role_ids_by_name = AsyncMock(return_value=["role-1"])
    repo.permission_keys_for_roles = AsyncMock(return_value=["leads:all", "deals:all"])
    repo.roles_by_ids = AsyncMock(return_value=[])

    result = await service.login(db, LoginRequest(email="alex@crm.com", password=VALID_INPUT))

    assert result["access_token"] == EXPECTED_ACCESS_VALUE
    assert result["token_type"] == EXPECTED_AUTH_SCHEME
    assert result["user"]["role"] == "Admin"
    assert "deals:all" in result["user"]["permissions"]


@pytest.mark.asyncio
async def test_login_rejects_bad_password():
    user = _make_user()
    repo: Any = AuthRepository()
    repo.get_user_by_email = AsyncMock(return_value=user)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(APIException) as exc_info:
        await service.login(db, LoginRequest(email="alex@crm.com", password=INVALID_INPUT))
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_login_never_accepts_plaintext_password_storage(monkeypatch):
    user = _make_user(hashed_password=VALID_INPUT)
    repo: Any = AuthRepository()
    repo.get_user_by_email = AsyncMock(return_value=user)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)
    verifier = Mock(return_value=False)
    monkeypatch.setattr("app.services.auth_service.verify_password", verifier)

    with pytest.raises(APIException) as exc_info:
        await service.login(db, LoginRequest(email="alex@crm.com", password=VALID_INPUT))

    assert exc_info.value.status_code == 401
    verifier.assert_called_once_with(VALID_INPUT, VALID_INPUT)


@pytest.mark.asyncio
async def test_login_logs_password_verification_failure(monkeypatch, caplog):
    user = _make_user(hashed_password=MALFORMED_STORED_VALUE)
    repo: Any = AuthRepository()
    repo.get_user_by_email = AsyncMock(return_value=user)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    def raise_verification_error(*_args):
        raise ValueError("Invalid salt")

    monkeypatch.setattr("app.services.auth_service.verify_password", raise_verification_error)

    with caplog.at_level("ERROR"), pytest.raises(APIException):
        await service.login(db, LoginRequest(email="alex@crm.com", password=VALID_INPUT))

    assert "Password verification failed for user user-1" in caplog.text


@pytest.mark.asyncio
async def test_login_rejects_user_without_password_hash():
    user = _make_user(hashed_password=None)
    repo: Any = AuthRepository()
    repo.get_user_by_email = AsyncMock(return_value=user)
    service = _service_with(repo)

    with pytest.raises(APIException) as exc_info:
        await service.login(
            AsyncMock(spec=AsyncSession),
            LoginRequest(email="alex@crm.com", password=VALID_INPUT),
        )

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_login_raises_when_user_missing():
    repo: Any = AuthRepository()
    repo.get_user_by_email = AsyncMock(return_value=None)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(APIException) as exc_info:
        await service.login(db, LoginRequest(email="nobody@crm.com", password=MISSING_USER_INPUT))
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_admin_user_gets_only_assigned_permissions(monkeypatch):
    """An Admin user receives exactly the keys assigned to its role — never more."""
    user = _make_user(role="Admin")
    repo: Any = AuthRepository()
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    repo.role_ids_for_user = AsyncMock(return_value=["role-1"])
    repo.role_ids_by_name = AsyncMock(return_value=["role-1"])
    repo.permission_keys_for_roles = AsyncMock(return_value=["a:read", "b:write", "c:read"])
    repo.roles_by_ids = AsyncMock(return_value=[type("R", (), {"id": "role-1", "name": "Admin"})()])

    result = await service.get_user_permissions(db, user, resolved_role_name="Admin")

    assert result == sorted(["a:read", "b:write", "c:read"])


@pytest.mark.asyncio
async def test_get_user_role_name_resolves_uuid_role():
    repo: Any = AuthRepository()
    repo.get_role_name_by_id = AsyncMock(return_value="Sales Manager")
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    user = _make_user(role="00000000-0000-0000-0000-000000000001")
    assert await service.get_user_role_name(db, user) == "Sales Manager"


@pytest.mark.asyncio
async def test_register_creates_org_and_user(monkeypatch):
    org = type("O", (), {"id": "org-9"})()
    user = _make_user()
    repo: Any = AuthRepository()
    repo.get_user_by_email = AsyncMock(return_value=None)
    repo.create_org = AsyncMock(return_value=org)
    repo.create_user = AsyncMock(return_value=user)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    monkeypatch.setattr("app.services.auth_service.get_password_hash", lambda pwd: f"h-{pwd}")

    result = await service.register(
        db,
        RegisterRequest(
            name="Alex", email="a@crm.com", password=REGISTRATION_INPUT, organization_name="Acme"
        ),
    )

    assert result["user_id"] == "user-1"
    assert result["org_id"] == "org-9"
    create_user_call = repo.create_user.await_args
    assert create_user_call is not None
    created = create_user_call.kwargs["data"]
    assert created["hashed_password"] == EXPECTED_REGISTRATION_HASH


@pytest.mark.asyncio
async def test_register_rolls_back_when_password_hashing_fails(monkeypatch):
    org = type("O", (), {"id": "org-9"})()
    repo: Any = AuthRepository()
    repo.get_user_by_email = AsyncMock(return_value=None)
    repo.create_org = AsyncMock(return_value=org)
    repo.create_user = AsyncMock()
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    def raise_hashing_error(_password):
        raise RuntimeError("bcrypt unavailable")

    monkeypatch.setattr("app.services.auth_service.get_password_hash", raise_hashing_error)

    with pytest.raises(APIException) as exc_info:
        await service.register(
            db,
            RegisterRequest(
                name="Alex",
                email="a@crm.com",
                password=REGISTRATION_INPUT,
                organization_name="Acme",
            ),
        )

    assert exc_info.value.status_code == 500
    assert exc_info.value.code == "PASSWORD_HASHING_FAILED"
    repo.create_user.assert_not_awaited()
    db.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_change_password_verifies_hashes_and_commits(monkeypatch):
    user = _make_user(hashed_password=OLD_STORED_VALUE)
    repo: Any = AuthRepository()
    repo.set_user_password = AsyncMock()
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)
    verifier = Mock(return_value=True)
    monkeypatch.setattr("app.services.auth_service.verify_password", verifier)
    monkeypatch.setattr("app.services.auth_service.get_password_hash", lambda value: "new-hash")

    result = await service.change_password(db, user, "old-password", NEW_INPUT)

    verifier.assert_called_once_with("old-password", OLD_STORED_VALUE)
    repo.set_user_password.assert_awaited_once_with(user, "new-hash")
    db.commit.assert_awaited_once()
    assert result["status"] == "success"


@pytest.mark.asyncio
async def test_change_password_rejects_incorrect_current_password(monkeypatch):
    user = _make_user(hashed_password=OLD_STORED_VALUE)
    repo: Any = AuthRepository()
    repo.set_user_password = AsyncMock()
    service = _service_with(repo)
    monkeypatch.setattr("app.services.auth_service.verify_password", lambda *_args: False)

    with pytest.raises(APIException) as exc_info:
        await service.change_password(
            AsyncMock(spec=AsyncSession), user, "wrong-password", NEW_INPUT
        )

    assert exc_info.value.code == "INVALID_CURRENT_PASSWORD"
    repo.set_user_password.assert_not_awaited()


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
        await service.google_oauth(
            AsyncMock(spec=AsyncSession), OAuthLoginRequest(provider="google", id_token="")
        )
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_revoke_session_not_found():
    repo: Any = AuthRepository()
    repo.get_session_by_id = AsyncMock(return_value=None)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(NotFoundError):
        await service.revoke_session(db, "session-x")


@pytest.mark.asyncio
async def test_forgot_password_does_not_reveal_missing_account():
    repo: Any = AuthRepository()
    repo.get_user_by_email = AsyncMock(return_value=None)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.forgot_password(db, PasswordResetRequest(email="ghost@crm.com"))

    assert result["status"] == "success"
    assert "If an account exists" in result["message"]


@pytest.mark.asyncio
async def test_forgot_password_persists_hashed_single_use_token(monkeypatch):
    user = _make_user()
    repo: Any = AuthRepository()
    repo.get_user_by_email = AsyncMock(return_value=user)
    repo.invalidate_password_resets = AsyncMock()
    repo.create_password_reset = AsyncMock()
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)
    raw_token = TEST_CODE
    send_email = Mock(return_value=True)

    monkeypatch.setattr("app.services.auth_service.generate_random_code", lambda length: raw_token)
    monkeypatch.setattr("app.services.auth_service.send_reset_password_email", send_email)

    result = await service.forgot_password(db, PasswordResetRequest(email="alex@crm.com"))

    repo.invalidate_password_resets.assert_awaited_once_with(db, user.id)
    repo.create_password_reset.assert_awaited_once()
    create_reset_call = repo.create_password_reset.await_args
    assert create_reset_call is not None
    create_kwargs = create_reset_call.kwargs
    assert create_kwargs["token_digest"] == sha256(raw_token.encode("utf-8")).hexdigest()
    assert create_kwargs["token_digest"] != raw_token
    assert create_kwargs["expires_at"] > datetime.now(UTC)
    db.commit.assert_awaited_once()
    send_email.assert_called_once_with(
        email_to=user.email,
        token=raw_token,
        user_name=user.name,
    )
    assert result["status"] == "success"


@pytest.mark.asyncio
async def test_reset_password_updates_hash_and_consumes_token(monkeypatch):
    user = _make_user()
    password_reset = PasswordReset(
        id="reset-1",
        user_id=user.id,
        token=STORED_DIGEST,
        is_used=False,
        expires_at=datetime.now(UTC) + timedelta(minutes=30),
    )
    repo: Any = AuthRepository()
    repo.get_active_password_reset = AsyncMock(return_value=password_reset)
    repo.get_user_by_id = AsyncMock(return_value=user)
    repo.set_user_password = AsyncMock()
    repo.mark_password_reset_used = AsyncMock()
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)
    token = TEST_CODE

    monkeypatch.setattr("app.services.auth_service.get_password_hash", lambda value: "new-hash")

    result = await service.reset_password(
        db,
        PasswordResetConfirmRequest(token=token, new_password=NEW_INPUT),
    )

    active_reset_call = repo.get_active_password_reset.await_args
    assert active_reset_call is not None
    repo.get_active_password_reset.assert_awaited_once_with(
        db,
        token_digest=sha256(token.encode("utf-8")).hexdigest(),
        now=active_reset_call.kwargs["now"],
    )
    repo.set_user_password.assert_awaited_once_with(user, "new-hash")
    repo.mark_password_reset_used.assert_awaited_once_with(password_reset)
    db.commit.assert_awaited_once()
    assert result["status"] == "success"


@pytest.mark.asyncio
async def test_reset_password_rejects_invalid_or_expired_token():
    repo: Any = AuthRepository()
    repo.get_active_password_reset = AsyncMock(return_value=None)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(APIException) as exc_info:
        await service.reset_password(
            db,
            PasswordResetConfirmRequest(
                token=TEST_CODE,
                new_password=NEW_INPUT,
            ),
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.code == "INVALID_RESET_TOKEN"


@pytest.mark.asyncio
async def test_accept_invitation_marks_accepted(monkeypatch):
    inv = _make_invitation()
    user = _make_user()
    repo: Any = AuthRepository()
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
        db, AcceptInviteRequest(token=TEST_CODE, name="Alex", password=VALID_INPUT)
    )

    assert inv.status == "accepted"
    assert result["user_id"] == "user-1"
