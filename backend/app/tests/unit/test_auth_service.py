import base64
import hashlib
import hmac
import time
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import Any
from unittest.mock import ANY, AsyncMock, Mock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIException, ForbiddenError, NotFoundError
from app.models import (
    MagicLinkToken,
    Organization,
    PasswordReset,
    RefreshToken,
    Role,
    User,
    UserInvitation,
)
from app.repositories.auth_repository import AuthRepository
from app.schemas.crm_schemas import (
    AcceptInviteRequest,
    ApiKeyCreate,
    LoginRequest,
    OAuthLoginRequest,
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
TEST_REFRESH_VALUE = "refresh"
NEXT_REFRESH_VALUE = "next"


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
    repo.roles_by_ids = AsyncMock(
        return_value=[type("R", (), {"id": "role-1", "name": "Admin"})()]
    )

    result = await service.login(db, LoginRequest(email="alex@crm.com", password=VALID_INPUT))

    assert result["access_token"] == EXPECTED_ACCESS_VALUE
    assert result["token_type"] == EXPECTED_AUTH_SCHEME
    assert result["user"]["role"] == "Admin"
    assert "deals:all" in result["user"]["permissions"]


@pytest.mark.asyncio
async def test_login_returns_permissions_for_legacy_super_admin(monkeypatch):
    user = _make_user(role="super_admin")
    repo: Any = AuthRepository()
    repo.get_user_by_email = AsyncMock(return_value=user)
    repo.role_ids_for_user = AsyncMock(return_value=[])
    repo.role_ids_by_name = AsyncMock(return_value=["global-super"])
    repo.roles_by_ids = AsyncMock(
        return_value=[
            type(
                "R",
                (),
                {"id": "global-super", "name": "Super Admin", "organization_id": None},
            )()
        ]
    )
    repo.all_permission_keys = AsyncMock(
        return_value=["dashboard:read", "organization:read"]
    )
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)
    monkeypatch.setattr("app.services.auth_service.verify_password", lambda _pwd, _hashed: True)
    monkeypatch.setattr("app.services.auth_service.create_access_token", lambda _user_id: "token")

    result = await service.login(
        db, LoginRequest(email="alex@crm.com", password=VALID_INPUT)
    )

    assert result["user"]["role"] == "super_admin"
    assert result["user"]["permissions"] == ["dashboard:read", "organization:read"]


@pytest.mark.asyncio
async def test_request_magic_link_persists_only_token_digest(monkeypatch):
    user = _make_user()
    repo: Any = AuthRepository()
    repo.get_user_by_email = AsyncMock(return_value=user)
    repo.invalidate_magic_links = AsyncMock()
    repo.create_magic_link = AsyncMock()
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)
    send_email = Mock(return_value=True)
    monkeypatch.setattr("app.services.auth_service.send_magic_link_email", send_email)
    monkeypatch.setattr("app.services.auth_service.generate_random_code", lambda length: TEST_CODE)

    result = await service.request_magic_link(db, user.email)

    assert result["status"] == "success"
    repo.create_magic_link.assert_awaited_once()
    kwargs = repo.create_magic_link.await_args_list[-1].kwargs
    assert kwargs["user_id"] == user.id
    assert kwargs["token_digest"] == sha256(TEST_CODE.encode()).hexdigest()
    assert kwargs["token_digest"] != TEST_CODE
    send_email.assert_called_once_with(email_to=user.email, token=TEST_CODE, user_name=user.name)


@pytest.mark.asyncio
async def test_verify_magic_link_requires_active_persisted_token(monkeypatch):
    repo: Any = AuthRepository()
    repo.get_active_magic_link = AsyncMock(return_value=None)
    repo.get_first_user = AsyncMock(return_value=None)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(APIException) as exc_info:
        await service.verify_magic_link(db, TEST_CODE)

    assert exc_info.value.status_code == 401
    repo.get_first_user.assert_not_called()


@pytest.mark.asyncio
async def test_verify_magic_link_consumes_token_and_authenticates_owner(monkeypatch):
    user = _make_user(id="magic-user")
    magic_link = MagicLinkToken(
        id="magic-1",
        user_id=user.id,
        token=sha256(TEST_CODE.encode()).hexdigest(),
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )
    repo: Any = AuthRepository()
    repo.get_active_magic_link = AsyncMock(return_value=magic_link)
    repo.get_user_by_id = AsyncMock(return_value=user)
    repo.create_refresh_token = AsyncMock(return_value=RefreshToken())
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)
    monkeypatch.setattr("app.services.auth_service.create_access_token", lambda user_id: user_id)
    monkeypatch.setattr("app.services.auth_service.generate_random_code", lambda length: "refresh")

    result = await service.verify_magic_link(db, TEST_CODE)

    assert result["access_token"] == user.id
    assert result["refresh_token"] == TEST_REFRESH_VALUE
    assert magic_link.is_used is True
    repo.get_user_by_id.assert_awaited_once_with(db, user.id)


@pytest.mark.asyncio
async def test_refresh_token_rejects_unknown_value():
    repo: Any = AuthRepository()
    repo.get_active_refresh_token = AsyncMock(return_value=None)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(APIException) as exc_info:
        await service.refresh_token(db, "unknown-refresh-token")

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_refresh_token_rotates_and_revokes_previous_token(monkeypatch):
    user = _make_user()
    stored_token = RefreshToken(
        id="refresh-1",
        user_id=user.id,
        token=sha256(TEST_REFRESH_VALUE.encode()).hexdigest(),
        expires_at=datetime.now(UTC) + timedelta(days=1),
    )
    repo: Any = AuthRepository()
    repo.get_active_refresh_token = AsyncMock(side_effect=[stored_token, None])
    repo.get_user_by_id = AsyncMock(return_value=user)
    repo.revoke_refresh_token = AsyncMock()
    repo.create_refresh_token = AsyncMock(return_value=RefreshToken())
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)
    monkeypatch.setattr(
        "app.services.auth_service.generate_random_code", lambda length: NEXT_REFRESH_VALUE
    )
    monkeypatch.setattr(
        "app.services.auth_service.create_access_token", lambda user_id: EXPECTED_ACCESS_VALUE
    )

    result = await service.refresh_token(db, TEST_REFRESH_VALUE)

    assert result["access_token"] == EXPECTED_ACCESS_VALUE
    assert result["refresh_token"] == NEXT_REFRESH_VALUE
    repo.revoke_refresh_token.assert_awaited_once_with(stored_token)
    db.commit.assert_awaited_once()

    with pytest.raises(APIException) as reused_token_error:
        await service.refresh_token(db, TEST_REFRESH_VALUE)
    assert reused_token_error.value.status_code == 401


@pytest.mark.asyncio
async def test_logout_revokes_active_refresh_token():
    stored_token = RefreshToken(
        id="refresh-1",
        user_id="user-1",
        token=sha256(TEST_REFRESH_VALUE.encode()).hexdigest(),
        expires_at=datetime.now(UTC) + timedelta(days=1),
    )
    repo: Any = AuthRepository()
    repo.get_active_refresh_token = AsyncMock(return_value=stored_token)
    repo.revoke_refresh_token = AsyncMock()
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.logout(db, TEST_REFRESH_VALUE)

    assert result["status"] == "success"
    repo.revoke_refresh_token.assert_awaited_once_with(stored_token)
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_logout_without_active_refresh_token_is_idempotent():
    repo: Any = AuthRepository()
    repo.get_active_refresh_token = AsyncMock(return_value=None)
    repo.revoke_refresh_token = AsyncMock()
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.logout(db, TEST_REFRESH_VALUE)

    assert result["status"] == "success"
    repo.revoke_refresh_token.assert_not_awaited()
    db.commit.assert_not_awaited()


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
async def test_get_user_role_name_preserves_legacy_super_admin_identity():
    repo: Any = AuthRepository()
    repo.get_user_role_id = AsyncMock(return_value="admin-role")
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    user = _make_user(role="super_admin")

    assert await service.get_user_role_name(db, user) == "super_admin"
    repo.get_user_role_id.assert_not_awaited()


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
async def test_2fa_setup_and_verification_use_user_secret():
    user = _make_user()
    service = _service_with(AuthRepository())
    db = AsyncMock(spec=AsyncSession)

    setup = await service.setup_2fa(db, user)
    assert len(setup["secret"]) == 32
    assert user.two_factor_secret != setup["secret"]
    assert user.two_factor_enabled is False

    secret = base64.b32decode(setup["secret"] + "=" * (-len(setup["secret"]) % 8))
    counter = int(time.time()) // 30
    digest = hmac.new(secret, counter.to_bytes(8, "big"), hashlib.sha1).digest()
    start = digest[-1] & 0x0F
    code = f"{(int.from_bytes(digest[start : start + 4], 'big') & 0x7FFFFFFF) % 1_000_000:06d}"

    assert await service.verify_2fa(db, user, TwoFactorVerifyRequest(code=code)) is not None
    assert user.two_factor_enabled is True

    with pytest.raises(APIException) as exc_info:
        await service.verify_2fa(db, user, TwoFactorVerifyRequest(code="000000"))
    assert exc_info.value.status_code == 400

    await service.disable_2fa(db, user)
    assert user.two_factor_secret is None
    assert user.two_factor_enabled is False


@pytest.mark.asyncio
async def test_google_oauth_requires_id_token():
    service = _service_with(AuthRepository())

    with pytest.raises(APIException) as exc_info:
        await service.google_oauth(
            AsyncMock(spec=AsyncSession), OAuthLoginRequest(provider="google", id_token="")
        )
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_oauth_rejects_unverified_identity(monkeypatch):
    repo: Any = AuthRepository()
    service = _service_with(repo)
    monkeypatch.setattr(
        service,
        "_verify_oauth_identity",
        AsyncMock(side_effect=APIException(status_code=401, message="Invalid identity token")),
    )
    repo.get_first_user = AsyncMock()

    with pytest.raises(APIException) as exc_info:
        await service.google_oauth(
            AsyncMock(spec=AsyncSession), OAuthLoginRequest(provider="google", id_token=TEST_CODE)
        )
    assert exc_info.value.status_code == 401
    repo.get_first_user.assert_not_called()


@pytest.mark.asyncio
async def test_current_user_me_requires_explicit_user():
    service = _service_with(AuthRepository())

    with pytest.raises(APIException) as exc_info:
        await service.get_current_user_me(AsyncMock(spec=AsyncSession))
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_revoke_session_not_found():
    repo: Any = AuthRepository()
    repo.get_session_by_id = AsyncMock(return_value=None)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(NotFoundError):
        await service.revoke_session(db, "session-x", _make_user())
    repo.get_session_by_id.assert_awaited_once_with(db, "session-x", "user-1")


@pytest.mark.asyncio
async def test_list_api_keys_is_tenant_scoped_and_never_returns_hash():
    repo: Any = AuthRepository()
    repo.list_api_keys = AsyncMock(
        return_value=[
            type(
                "K",
                (),
                {
                    "id": "key-1",
                    "name": "CRM key",
                    "key_hash": "stored-secret-hash",
                    "created_at": datetime.now(UTC),
                    "last_used": None,
                },
            )()
        ]
    )
    service = _service_with(repo)

    result = await service.list_api_keys(AsyncMock(spec=AsyncSession), _make_user())

    repo.list_api_keys.assert_awaited_once_with(ANY, "org-1")
    assert result[0]["api_key"] is None
    assert result[0]["key"] == "********"
    assert "stored-secret-hash" not in result[0].values()


@pytest.mark.asyncio
async def test_create_api_key_uses_current_org_and_stores_only_digest(monkeypatch):
    repo: Any = AuthRepository()
    repo.create_api_key = AsyncMock(
        return_value=type(
            "K",
            (),
            {"id": "key-1", "name": "CRM key", "created_at": datetime.now(UTC)},
        )()
    )
    service = _service_with(repo)
    monkeypatch.setattr("app.services.auth_service.generate_random_code", lambda _length: TEST_CODE)

    result = await service.create_api_key(
        AsyncMock(spec=AsyncSession), ApiKeyCreate(name="CRM key"), _make_user()
    )

    raw_key = f"crm_live_{TEST_CODE}"
    stored = repo.create_api_key.await_args.kwargs["data"]
    assert result["api_key"] == raw_key
    assert stored["key_hash"] == sha256(raw_key.encode("utf-8")).hexdigest()
    assert stored["organization_id"] == "org-1"
    assert stored["created_by"] == "user-1"


@pytest.mark.asyncio
async def test_create_api_key_without_current_org_stays_forbidden():
    service = _service_with(AuthRepository())

    with pytest.raises(ForbiddenError):
        await service.create_api_key(
            AsyncMock(spec=AsyncSession),
            ApiKeyCreate(name="CRM key"),
            _make_user(organization_id=None),
        )


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
@pytest.mark.parametrize("is_system_role", [True, False])
async def test_accept_invitation_assigns_system_and_custom_roles(monkeypatch, is_system_role):
    role = Role(
        id="role-sales-manager",
        name="Sales Manager",
        organization_id=None if is_system_role else "org-1",
        is_system_role=is_system_role,
    )
    inv = _make_invitation(role=role.id)
    user = _make_user(role=role.id)
    repo: Any = AuthRepository()
    repo.get_invitation_by_token = AsyncMock(return_value=inv)
    repo.get_organization_by_id = AsyncMock(
        return_value=Organization(id="org-1", name="Acme", status="active", is_active=True)
    )
    repo.get_role_for_organization = AsyncMock(return_value=role)
    repo.get_user_by_email = AsyncMock(return_value=None)
    repo.create_user = AsyncMock(return_value=user)
    repo.assign_user_role = AsyncMock()
    service = _service_with(repo)
    service._create_refresh_token = AsyncMock(return_value=TEST_REFRESH_VALUE)
    service.get_user_permissions = AsyncMock(return_value=["users:read"])
    db = AsyncMock(spec=AsyncSession)

    monkeypatch.setattr("app.services.auth_service.get_password_hash", lambda pwd: "hashed")
    monkeypatch.setattr("app.services.auth_service.create_access_token", lambda user_id: "tok")

    result = await service.accept_auth_user_invitation(
        db, AcceptInviteRequest(token=TEST_CODE, name="Alex", password=VALID_INPUT)
    )

    assert inv.status == "accepted"
    assert result["user_id"] == "user-1"
    assert result["role"] == "Sales Manager"
    assert result["refresh_token"] == TEST_REFRESH_VALUE
    assert result["user"]["permissions"] == ["users:read"]
    repo.get_invitation_by_token.assert_awaited_once_with(db, TEST_CODE, for_update=True)
    repo.get_role_for_organization.assert_awaited_once_with(db, role.id, "org-1")
    repo.assign_user_role.assert_awaited_once_with(db, user_id="user-1", role_id=role.id)
    created = repo.create_user.await_args.kwargs["data"]
    assert created["organization_id"] == "org-1"
    assert created["role"] == role.id
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_accept_invitation_rejects_cross_organization_role():
    inv = _make_invitation(role="other-org-role")
    repo: Any = AuthRepository()
    repo.get_invitation_by_token = AsyncMock(return_value=inv)
    repo.get_organization_by_id = AsyncMock(
        return_value=Organization(id="org-1", name="Acme", status="active", is_active=True)
    )
    repo.get_role_for_organization = AsyncMock(return_value=None)
    repo.get_user_by_email = AsyncMock()
    service = _service_with(repo)

    with pytest.raises(APIException) as exc_info:
        await service.accept_auth_user_invitation(
            AsyncMock(spec=AsyncSession),
            AcceptInviteRequest(token=TEST_CODE, name="Alex", password=VALID_INPUT),
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.message == "Invitation role is invalid for this organization"
    repo.get_user_by_email.assert_not_awaited()


@pytest.mark.asyncio
async def test_accept_invitation_rejects_existing_user_from_another_organization():
    role = Role(
        id="role-sales-manager",
        name="Sales Manager",
        organization_id="org-1",
        is_system_role=False,
    )
    repo: Any = AuthRepository()
    repo.get_invitation_by_token = AsyncMock(return_value=_make_invitation(role=role.id))
    repo.get_organization_by_id = AsyncMock(
        return_value=Organization(id="org-1", name="Acme", status="active", is_active=True)
    )
    repo.get_role_for_organization = AsyncMock(return_value=role)
    repo.get_user_by_email = AsyncMock(return_value=_make_user(organization_id="org-2"))
    repo.assign_user_role = AsyncMock()
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(ForbiddenError) as exc_info:
        await service.accept_auth_user_invitation(
            db,
            AcceptInviteRequest(token=TEST_CODE, name="Alex", password=VALID_INPUT),
        )

    assert exc_info.value.status_code == 403
    repo.assign_user_role.assert_not_awaited()
    db.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_accept_invitation_reports_password_hashing_failure(monkeypatch):
    role = Role(
        id="role-sales-manager",
        name="Sales Manager",
        organization_id="org-1",
        is_system_role=False,
    )
    invitation = _make_invitation(role=role.id)
    repo: Any = AuthRepository()
    repo.get_invitation_by_token = AsyncMock(return_value=invitation)
    repo.get_organization_by_id = AsyncMock(
        return_value=Organization(id="org-1", name="Acme", status="active", is_active=True)
    )
    repo.get_role_for_organization = AsyncMock(return_value=role)
    repo.get_user_by_email = AsyncMock(return_value=None)
    repo.create_user = AsyncMock()
    repo.assign_user_role = AsyncMock()
    service = _service_with(repo)
    service._create_refresh_token = AsyncMock()
    db = AsyncMock(spec=AsyncSession)

    def raise_hashing_error(_password):
        raise RuntimeError("bcrypt unavailable")

    monkeypatch.setattr("app.services.auth_service.get_password_hash", raise_hashing_error)

    with pytest.raises(APIException) as exc_info:
        await service.accept_auth_user_invitation(
            db,
            AcceptInviteRequest(token=TEST_CODE, name="Alex", password=VALID_INPUT),
        )

    assert exc_info.value.status_code == 500
    assert exc_info.value.code == "PASSWORD_HASHING_FAILED"
    assert exc_info.value.message == "Unable to create account. Please try again later."
    assert invitation.status == "pending"
    repo.create_user.assert_not_awaited()
    repo.assign_user_role.assert_not_awaited()
    service._create_refresh_token.assert_not_awaited()
    db.commit.assert_not_awaited()
    db.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_invitation_details_resolves_role_name_without_cross_invite_status():
    role = Role(
        id="role-sales-manager",
        name="Sales Manager",
        organization_id=None,
        is_system_role=True,
    )
    inv = _make_invitation(role=role.id)
    repo: Any = AuthRepository()
    repo.get_invitation_by_token = AsyncMock(return_value=inv)
    repo.get_organization_by_id = AsyncMock(
        return_value=Organization(id="org-1", name="Acme", status="active", is_active=True)
    )
    repo.get_role_for_organization = AsyncMock(return_value=role)
    service = _service_with(repo)

    result = await service.get_auth_invitation_details(AsyncMock(spec=AsyncSession), TEST_CODE)

    assert result["role"] == "Sales Manager"
    assert result["status"] == "pending"
