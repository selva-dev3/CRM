import base64
import hashlib
import hmac
import json
import logging
import secrets
import time
import uuid
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from urllib.parse import quote

import httpx
from cryptography.fernet import Fernet, InvalidToken
from fastapi import status
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import APIException, ConflictError, ForbiddenError, NotFoundError
from app.core.permissions import (
    SUPER_ADMIN_ROLE_NAMES,
    is_global_super_admin_role,
    is_super_admin_role_name,
)
from app.core.security import (
    create_access_token,
    generate_random_code,
    get_password_hash,
    verify_password,
)
from app.models import Organization, Role, User, UserInvitation
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
from app.services.email_service import send_magic_link_email, send_reset_password_email

logger = logging.getLogger(__name__)


class AuthService:
    """Business logic for authentication, registration, SSO, 2FA and sessions."""

    def __init__(self, repository: AuthRepository | None = None) -> None:
        self.repository = repository or AuthRepository()

    async def _commit(self, db: AsyncSession, error_message: str) -> None:
        try:
            await db.commit()
        except Exception as e:
            await db.rollback()
            raise APIException(
                status_code=status.HTTP_400_BAD_REQUEST, message=error_message
            ) from e

    async def _create_refresh_token(
        self, db: AsyncSession, user_id: str, *, is_persistent: bool = True,
        family_id: str | None = None, generation: int = 0,
        absolute_expires_at: datetime | None = None,
    ) -> str:
        refresh_token = generate_random_code(48)
        now = datetime.now(UTC)
        absolute_expires_at = absolute_expires_at or (
            now + timedelta(days=settings.REFRESH_TOKEN_ABSOLUTE_EXPIRE_DAYS)
        )
        expires_at = min(
            now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS), absolute_expires_at
        )
        await self.repository.create_refresh_token(
            db,
            user_id=user_id,
            token_digest=sha256(refresh_token.encode("utf-8")).hexdigest(),
            expires_at=expires_at,
            is_persistent=is_persistent,
            family_id=family_id or uuid.uuid4().hex,
            generation=generation,
            absolute_expires_at=absolute_expires_at,
        )
        return refresh_token

    async def _create_access_token(
        self, db: AsyncSession, user_id: str, *, family_id: str | None = None
    ) -> str:
        access_token = create_access_token(user_id)
        expires_at = datetime.now(UTC) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        await self.repository.create_access_session(
            db,
            token_digest=sha256(access_token.encode("utf-8")).hexdigest(),
            user_id=user_id,
            family_id=family_id,
            expires_at=expires_at,
        )
        return access_token

    async def issue_session_tokens(
        self, db: AsyncSession, user_id: str, *, is_persistent: bool = True
    ) -> tuple[str, str]:
        """Stage one access/refresh token family in the caller's transaction."""
        family_id = uuid.uuid4().hex
        access_token = await self._create_access_token(db, user_id, family_id=family_id)
        refresh_token = await self._create_refresh_token(
            db, user_id, is_persistent=is_persistent, family_id=family_id
        )
        return access_token, refresh_token

    async def get_user_role_name(self, db: AsyncSession, user: User) -> str:
        """Resolve human-readable role name (e.g. 'Admin', 'Super Admin') for a user."""
        if getattr(user, "is_platform_admin", False) is True:
            return "Super Admin"
        try:
            raw_role = (user.role or "").strip()

            if is_super_admin_role_name(raw_role):
                return raw_role

            if len(raw_role) == 36 and "-" in raw_role:
                role_db = await self.repository.get_role_name_by_id(db, raw_role)
                if role_db:
                    return role_db

            user_role_id = await self.repository.get_user_role_id(db, user.id)
            if user_role_id:
                role_db = await self.repository.get_role_name_by_id(db, user_role_id)
                if role_db:
                    return role_db

            if raw_role:
                return raw_role
        except Exception:
            logger.warning("Failed to resolve user role name", exc_info=True)
        return "Admin"

    async def get_user_permissions(
        self, db: AsyncSession, user: User, resolved_role_name: str = ""
    ) -> list[str]:
        """Resolve a user's effective permission keys from the RBAC tables.

        Permissions are derived exclusively from the relationship graph
        ``User -> UserRole -> Role -> RolePermission -> Permission`` (plus a
        case-insensitive lookup of the legacy ``User.role`` string so existing
        role-name assignments keep working). Only the ``super_admin`` role (by
        name) is treated as unrestricted and granted every known permission key.
        Every other role — including Admin and other system roles — resolves to
        exactly the keys explicitly assigned through role_permissions; the
        ``super_admin:manage`` permission key or the ``all`` sentinel do NOT
        implicitly expand a non-super_admin role. There is intentionally no
        grant-all fallback: an unknown/unmapped user or a resolution failure
        yields an empty set (deny by default), matching fail-closed authorization.
        """
        permission_keys = set()
        try:
            if getattr(user, "is_platform_admin", False) is True:
                return sorted(await self.repository.all_permission_keys(db))
            organization_id = self._require_organization_id(user)
            role_ids = set(await self.repository.role_ids_for_user(db, user.id))
            raw_role = (user.role or "").strip()
            role_lookup = (resolved_role_name or raw_role).strip()
            if len(raw_role) == 36 and "-" in raw_role:
                role_ids.add(raw_role)
            elif is_super_admin_role_name(raw_role):
                for alias in sorted(SUPER_ADMIN_ROLE_NAMES):
                    role_ids.update(
                        await self.repository.role_ids_by_name(
                            db, alias, organization_id, global_only=True
                        )
                    )
            elif role_lookup:
                role_ids.update(
                    await self.repository.role_ids_by_name(db, role_lookup, organization_id)
                )

            if role_ids:
                roles = await self.repository.roles_by_ids(db, list(role_ids), organization_id)
                authorized_role_ids = [role.id for role in roles]
                if not authorized_role_ids:
                    return []
                if any(is_global_super_admin_role(role) for role in roles):
                    return sorted(await self.repository.all_permission_keys(db))
                keys = await self.repository.permission_keys_for_roles(db, authorized_role_ids)
                permission_keys.update(keys)
        except Exception:
            logger.exception("Failed to resolve permissions for user %s", getattr(user, "id", None))
            permission_keys.clear()

        return sorted(permission_keys)

    async def login(self, db: AsyncSession, payload: LoginRequest) -> dict:
        user = await self.repository.get_user_by_email(db, payload.email)
        if not user:
            raise APIException(
                status_code=status.HTTP_401_UNAUTHORIZED, message="Invalid email or password"
            )

        valid_pass = False
        if user.hashed_password:
            try:
                valid_pass = verify_password(payload.password, user.hashed_password)
            except Exception:
                logger.exception("Password verification failed for user %s", user.id)

        if not valid_pass:
            raise APIException(
                status_code=status.HTTP_401_UNAUTHORIZED, message="Invalid email or password"
            )

        await self._validate_session_principal(db, user)
        if user.two_factor_enabled:
            if not payload.two_factor_code:
                raise APIException(
                    status_code=status.HTTP_428_PRECONDITION_REQUIRED,
                    code="TWO_FACTOR_REQUIRED",
                    message="Enter the authentication code from your authenticator app",
                )
            if not self._is_valid_totp(user, payload.two_factor_code):
                raise APIException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    code="INVALID_TWO_FACTOR_CODE",
                    message="Invalid two-factor authentication code",
                )

        family_id = uuid.uuid4().hex
        access_token = await self._create_access_token(db, user.id, family_id=family_id)
        refresh_token = await self._create_refresh_token(
            db, user.id, is_persistent=payload.remember_me, family_id=family_id
        )
        await self._commit(db, "Unable to create refresh token")
        user_role_name = await self.get_user_role_name(db, user)
        user_permissions = await self.get_user_permissions(
            db, user, resolved_role_name=user_role_name
        )

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            "persistent_access": payload.remember_me,
            "user": {
                "id": user.id,
                "name": user.name,
                "email": user.email,
                "role": user_role_name,
                "organization_id": user.organization_id or "",
                "is_platform_admin": getattr(user, "is_platform_admin", False) is True,
                "permissions": user_permissions,
            },
        }

    async def get_current_user_me(self, db: AsyncSession, user: User | None = None) -> dict:
        if not user:
            raise APIException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                message="Authenticated user is required",
            )

        user_role_name = await self.get_user_role_name(db, user)
        user_permissions = await self.get_user_permissions(
            db, user, resolved_role_name=user_role_name
        )

        return {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "role": user_role_name,
            "organization_id": user.organization_id or "",
            "is_platform_admin": getattr(user, "is_platform_admin", False) is True,
            "permissions": user_permissions,
        }

    async def register(self, db: AsyncSession, payload: RegisterRequest) -> dict:
        raise ForbiddenError(
            message="Organization registration is invitation-only. Contact the platform administrator.",
            code="ORGANIZATION_REGISTRATION_DISABLED",
        )

    async def refresh_token(
        self, db: AsyncSession, refresh_token: str, access_token: str | None = None
    ) -> dict:
        token_digest = sha256(refresh_token.strip().encode("utf-8")).hexdigest()
        stored_token = await self.repository.get_active_refresh_token(
            db, token_digest=token_digest, now=datetime.now(UTC)
        )
        if not stored_token:
            reused = await self.repository.get_refresh_token(db, token_digest)
            if reused and reused.family_id:
                await self.repository.revoke_refresh_family(db, reused.family_id)
                await self._commit(db, "Unable to revoke replayed refresh session")
            raise APIException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                message="Invalid or expired refresh token",
            )
        user = await self.repository.get_user_by_id(db, stored_token.user_id)
        if not user:
            raise APIException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                message="Invalid or expired refresh token",
            )
        await self._validate_session_principal(db, user)
        await self.repository.revoke_refresh_token(stored_token)
        if access_token:
            previous_session = await self.repository.get_session_by_access_token(
                db, sha256(access_token.strip().encode("utf-8")).hexdigest()
            )
            if previous_session:
                await self.repository.revoke_access_session(previous_session)
        next_refresh_token = await self._create_refresh_token(
            db,
            user.id,
            is_persistent=stored_token.is_persistent,
            family_id=stored_token.family_id,
            generation=(stored_token.generation or 0) + 1,
            absolute_expires_at=stored_token.absolute_expires_at,
        )
        next_access_token = await self._create_access_token(
            db, user.id, family_id=stored_token.family_id
        )
        await self._commit(db, "Unable to rotate refresh token")
        return {
            "access_token": next_access_token,
            "refresh_token": next_refresh_token,
            "token_type": "bearer",
            "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            "persistent_access": stored_token.is_persistent,
        }

    async def logout(
        self, db: AsyncSession, refresh_token: str | None, access_token: str | None = None
    ) -> dict:
        """Revoke the current refresh token when present; logout remains idempotent."""
        changed = False
        if refresh_token:
            token_digest = sha256(refresh_token.strip().encode("utf-8")).hexdigest()
            stored_token = await self.repository.get_active_refresh_token(
                db, token_digest=token_digest, now=datetime.now(UTC)
            )
            if stored_token:
                await self.repository.revoke_refresh_token(stored_token)
                await self.repository.revoke_refresh_family(db, stored_token.family_id)
                changed = True
            elif access_token:
                current = await self.repository.get_session_by_access_token(
                    db, sha256(access_token.strip().encode("utf-8")).hexdigest()
                )
                if current and current.family_id:
                    await self.repository.revoke_refresh_family(db, current.family_id)
                    changed = True
        if access_token:
            session = await self.repository.get_session_by_access_token(
                db, sha256(access_token.strip().encode("utf-8")).hexdigest()
            )
            if session and session.is_current:
                await self.repository.revoke_access_session(session)
                changed = True
        if changed:
            await self._commit(db, "Unable to revoke authentication session")
        return {"message": "Logged out successfully", "status": "success"}

    async def forgot_password(self, db: AsyncSession, payload: PasswordResetRequest) -> dict:
        response = {
            "message": "If an account exists for that email, a password reset link has been sent",
            "status": "success",
        }
        email_clean = payload.email.strip()
        user = await self.repository.get_user_by_email(db, email_clean)
        if not user:
            return response

        reset_token = generate_random_code(14)
        token_digest = sha256(reset_token.encode("utf-8")).hexdigest()
        expires_at = datetime.now(UTC) + timedelta(minutes=settings.RESET_TOKEN_EXPIRE_MINUTES)

        await self.repository.invalidate_password_resets(db, user.id)
        await self.repository.create_password_reset(
            db,
            user_id=user.id,
            token_digest=token_digest,
            expires_at=expires_at,
        )
        await self._commit(db, "Unable to create password reset request")

        send_reset_password_email(email_to=user.email, token=reset_token, user_name=user.name)
        return response

    async def reset_password(
        self,
        db: AsyncSession,
        payload: PasswordResetConfirmRequest,
    ) -> dict:
        token_digest = sha256(payload.token.strip().encode("utf-8")).hexdigest()
        password_reset = await self.repository.get_active_password_reset(
            db,
            token_digest=token_digest,
            now=datetime.now(UTC),
        )
        if not password_reset:
            raise APIException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="INVALID_RESET_TOKEN",
                message="This password reset link is invalid or has expired",
            )

        user = await self.repository.get_user_by_id(db, password_reset.user_id)
        if not user:
            raise APIException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="INVALID_RESET_TOKEN",
                message="This password reset link is invalid or has expired",
            )

        await self.repository.set_user_password(user, get_password_hash(payload.new_password))
        await self.repository.mark_password_reset_used(password_reset)
        await self.repository.revoke_all_user_sessions(db, user.id)
        await self._commit(db, "Unable to update password")
        return {"message": "Password updated successfully", "status": "success"}

    async def change_password(
        self,
        db: AsyncSession,
        current_user: User,
        old_password: str,
        new_password: str,
    ) -> dict:
        try:
            old_password_valid = bool(current_user.hashed_password) and verify_password(
                old_password, current_user.hashed_password
            )
        except Exception:
            logger.exception("Password verification failed for user %s", current_user.id)
            old_password_valid = False

        if not old_password_valid:
            raise APIException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="INVALID_CURRENT_PASSWORD",
                message="Current password is incorrect",
            )

        await self.repository.set_user_password(current_user, get_password_hash(new_password))
        await self.repository.revoke_all_user_sessions(db, current_user.id)
        await self._commit(db, "Unable to update password")
        return {"message": "Password changed successfully", "status": "success"}

    @staticmethod
    def _two_factor_cipher() -> Fernet:
        key = base64.urlsafe_b64encode(hashlib.sha256(settings.SECRET_KEY.encode()).digest())
        return Fernet(key)

    @staticmethod
    async def _validate_session_principal(db: AsyncSession, user: User) -> None:
        if not user.is_active:
            raise APIException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                code="AUTH_ACCOUNT_INACTIVE",
                message="This account is inactive",
            )
        if getattr(user, "is_platform_admin", False) is True:
            return
        organization = await db.get(Organization, user.organization_id)
        if not organization or not organization.is_active or organization.status != "active":
            raise ForbiddenError(message="User organization is inactive or unavailable")

    def _is_valid_totp(self, user: User, code: str) -> bool:
        if not user.two_factor_secret or not code.isdigit() or len(code) != 6:
            return False
        try:
            secret = self._two_factor_cipher().decrypt(user.two_factor_secret.encode()).decode()
        except (InvalidToken, ValueError):
            return False

        key = base64.b32decode(secret + "=" * (-len(secret) % 8), casefold=True)
        counter = int(time.time()) // 30
        for offset in (-1, 0, 1):
            digest = hmac.new(key, (counter + offset).to_bytes(8, "big"), hashlib.sha1).digest()
            start = digest[-1] & 0x0F
            value = int.from_bytes(digest[start : start + 4], "big") & 0x7FFFFFFF
            if hmac.compare_digest(code, f"{value % 1_000_000:06d}"):
                return True
        return False

    async def setup_2fa(self, db: AsyncSession, user: User) -> dict:
        secret = base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")
        user.two_factor_secret = self._two_factor_cipher().encrypt(secret.encode()).decode("ascii")
        user.two_factor_enabled = False
        await self._commit(db, "Unable to save 2FA setup")
        label = quote(f"CRM:{user.email}")
        issuer = quote("Enterprise CRM")
        otp_uri = f"otpauth://totp/{label}?secret={secret}&issuer={issuer}"
        return {
            "secret": secret,
            "otp_uri": otp_uri,
        }

    async def verify_2fa(
        self, db: AsyncSession, user: User, payload: TwoFactorVerifyRequest
    ) -> dict:
        if not self._is_valid_totp(user, payload.code):
            raise APIException(
                status_code=status.HTTP_400_BAD_REQUEST, message="Invalid 2FA authentication code"
            )
        user.two_factor_enabled = True
        await self._commit(db, "Unable to save 2FA verification")
        return {"message": "2FA verified successfully", "status": "success"}

    async def disable_2fa(self, db: AsyncSession, user: User) -> dict:
        user.two_factor_secret = None
        user.two_factor_enabled = False
        await self._commit(db, "Unable to disable 2FA")
        return {"message": "2FA disabled successfully", "status": "success"}

    async def _verify_oauth_identity(self, provider: str, id_token: str) -> dict:
        if provider == "google":
            client_id = settings.GOOGLE_OAUTH_CLIENT_ID
            if not client_id:
                raise APIException(status_code=503, message="Google OAuth is not configured")
            try:
                async with httpx.AsyncClient(timeout=5) as client:
                    response = await client.get(
                        "https://oauth2.googleapis.com/tokeninfo", params={"id_token": id_token}
                    )
                response.raise_for_status()
                claims = response.json()
            except (httpx.HTTPError, ValueError) as exc:
                raise APIException(
                    status_code=401, message="Invalid Google identity token"
                ) from exc
            if claims.get("aud") != client_id or claims.get("iss") not in {
                "accounts.google.com",
                "https://accounts.google.com",
            }:
                raise APIException(status_code=401, message="Invalid Google identity token")
        elif provider == "microsoft":
            client_id = settings.MICROSOFT_OAUTH_CLIENT_ID
            if not client_id:
                raise APIException(status_code=503, message="Microsoft OAuth is not configured")
            discovery_url = (
                f"https://login.microsoftonline.com/{settings.MICROSOFT_OAUTH_TENANT}"
                "/v2.0/.well-known/openid-configuration"
            )
            try:
                async with httpx.AsyncClient(timeout=5) as client:
                    metadata_response = await client.get(discovery_url)
                    metadata_response.raise_for_status()
                    metadata = metadata_response.json()
                    jwks_response = await client.get(metadata["jwks_uri"])
                    jwks_response.raise_for_status()
                    jwks = jwks_response.json()
                header = jwt.get_unverified_header(id_token)
                key = next(key for key in jwks["keys"] if key.get("kid") == header.get("kid"))
                claims = jwt.decode(id_token, key, algorithms=["RS256"], audience=client_id)
            except (httpx.HTTPError, KeyError, StopIteration, JWTError, ValueError) as exc:
                raise APIException(
                    status_code=401, message="Invalid Microsoft identity token"
                ) from exc
            issuer = str(claims.get("iss", ""))
            if not issuer.startswith("https://login.microsoftonline.com/") or not issuer.endswith(
                "/v2.0"
            ):
                raise APIException(status_code=401, message="Invalid Microsoft identity token")
        else:
            raise APIException(status_code=400, message="Unsupported OAuth provider")

        email = claims.get("email") or claims.get("preferred_username")
        verified = claims.get("email_verified", True)
        if isinstance(verified, str):
            verified = verified.strip().lower() == "true"
        if not email or verified is not True:
            raise APIException(status_code=401, message="OAuth identity has no verified email")
        return {"email": str(email).lower()}

    async def _oauth_issue_token(
        self, db: AsyncSession, provider: str, id_token: str, two_factor_code: str | None = None
    ) -> dict:
        identity = await self._verify_oauth_identity(provider, id_token)
        user = await self.repository.get_user_by_email(db, identity["email"])
        if not user or not user.is_active:
            raise APIException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                message="No active CRM account is linked to this OAuth identity",
            )
        await self._validate_session_principal(db, user)
        if user.two_factor_enabled:
            if not two_factor_code or not self._is_valid_totp(user, two_factor_code):
                raise APIException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    code="INVALID_TWO_FACTOR_CODE",
                    message="Valid two-factor authentication is required",
                )
        family_id = uuid.uuid4().hex
        refresh_token = await self._create_refresh_token(db, user.id, family_id=family_id)
        access_token = await self._create_access_token(db, user.id, family_id=family_id)
        await self._commit(db, "Unable to create refresh token")
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        }

    async def google_oauth(self, db: AsyncSession, payload: OAuthLoginRequest) -> dict:
        if not payload.id_token:
            raise APIException(
                status_code=status.HTTP_400_BAD_REQUEST, message="Authorization code is required"
            )
        return await self._oauth_issue_token(db, "google", payload.id_token, payload.two_factor_code)

    async def microsoft_oauth(self, db: AsyncSession, payload: OAuthLoginRequest) -> dict:
        if not payload.id_token:
            raise APIException(
                status_code=status.HTTP_400_BAD_REQUEST, message="Authorization code is required"
            )
        return await self._oauth_issue_token(db, "microsoft", payload.id_token, payload.two_factor_code)

    async def get_auth_invitation_details(self, db: AsyncSession, token: str) -> dict:
        inv = await self.repository.get_invitation_by_token(db, token)
        if not inv:
            raise NotFoundError(message="Invitation not found or token invalid")
        role = await self._resolve_user_invitation_role(db, inv)
        return {
            "id": inv.id,
            "email": inv.email,
            "role": role.name,
            "status": inv.status,
            "organization_id": inv.organization_id,
            "created_at": str(inv.created_at),
        }

    async def _resolve_user_invitation_role(
        self, db: AsyncSession, invitation: UserInvitation
    ) -> Role:
        organization_id = (invitation.organization_id or "").strip()
        if not organization_id:
            raise APIException(
                status_code=status.HTTP_400_BAD_REQUEST,
                message="Invitation has no associated organization and cannot be accepted",
            )

        organization = await self.repository.get_organization_by_id(db, organization_id)
        if not organization:
            raise APIException(
                status_code=status.HTTP_400_BAD_REQUEST,
                message="Invitation organization no longer exists",
            )
        if not organization.is_active or (organization.status or "").strip().lower() != "active":
            raise ForbiddenError(message="Invitation organization is inactive")

        role = await self.repository.get_role_for_organization(db, invitation.role, organization_id)
        if not role:
            raise APIException(
                status_code=status.HTTP_400_BAD_REQUEST,
                message="Invitation role is invalid for this organization",
            )
        from app.core.permissions import ensure_can_assign_role, is_super_admin_role

        ensure_can_assign_role(actor_is_super_admin=False, target_is_super_admin=is_super_admin_role(role))
        return role

    async def accept_auth_user_invitation(
        self, db: AsyncSession, payload: AcceptInviteRequest
    ) -> dict:
        inv = await self.repository.get_invitation_by_token(db, payload.token, for_update=True)
        if not inv:
            raise NotFoundError(message="Invalid or expired invitation token")

        if inv.status != "pending":
            message = (
                "Invitation has already been accepted"
                if inv.status == "accepted"
                else "Invitation is no longer active"
            )
            raise APIException(
                status_code=status.HTTP_400_BAD_REQUEST,
                message=message,
            )

        role = await self._resolve_user_invitation_role(db, inv)
        target_org_id = inv.organization_id

        try:
            user = await self.repository.get_user_by_email(db, inv.email)
            if user and user.organization_id != target_org_id:
                raise ForbiddenError(
                    message="An existing user cannot be moved to another organization by invitation"
                )
            if user and user.is_active:
                raise ConflictError(
                    code="ACTIVE_ACCOUNT_EXISTS",
                    message="An active account already exists for this invitation email",
                )
            if user and user.two_factor_enabled:
                raise ConflictError(
                    code="INVITATION_ACCOUNT_REQUIRES_RECOVERY",
                    message="This account must complete account recovery before accepting an invitation",
                )

            try:
                hashed_pwd = get_password_hash(payload.password)
            except Exception as e:
                logger.exception("Password hashing failed during invitation acceptance")
                raise APIException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    code="PASSWORD_HASHING_FAILED",
                    message="Unable to create account. Please try again later.",
                ) from e

            is_new_user = user is None
            if user:
                user.name = payload.name
                user.hashed_password = hashed_pwd
                user.role = role.id
                user.is_active = True
            else:
                user = await self.repository.create_user(
                    db,
                    data={
                        "name": payload.name,
                        "email": inv.email,
                        "hashed_password": hashed_pwd,
                        "role": role.id,
                        "organization_id": target_org_id,
                        "is_active": True,
                    },
                )

            user.is_verified = True
            if is_new_user:
                await db.flush()
            await self.repository.assign_user_role(db, user_id=user.id, role_id=role.id)
            family_id = uuid.uuid4().hex
            refresh_token = await self._create_refresh_token(db, user.id, family_id=family_id)
            access_token = await self._create_access_token(db, user.id, family_id=family_id)
            inv.status = "accepted"
            await db.commit()

            user_permissions = await self.get_user_permissions(
                db, user, resolved_role_name=role.name
            )

            return {
                "message": "Invitation accepted successfully! Your account is active.",
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_type": "bearer",
                "user_id": user.id,
                "email": user.email,
                "name": user.name,
                "role": role.name,
                "is_verified": user.is_verified,
                "two_factor_enabled": user.two_factor_enabled,
                "status": "success",
                "user": {
                    "id": user.id,
                    "name": user.name,
                    "email": user.email,
                    "role": role.name,
                    "organization_id": user.organization_id,
                    "permissions": user_permissions,
                    "is_verified": user.is_verified,
                    "two_factor_enabled": user.two_factor_enabled,
                },
            }
        except APIException:
            await db.rollback()
            raise
        except Exception as e:
            await db.rollback()
            logger.exception("Unexpected failure during invitation acceptance")
            raise APIException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                code="INVITATION_ACCEPTANCE_FAILED",
                message="Unable to accept invitation. Please try again later.",
            ) from e

    async def list_sessions(self, db: AsyncSession, current_user: User) -> list[dict]:
        sessions = await self.repository.list_sessions(db, current_user.id)
        return [
            {
                "session_id": s.id,
                "device": s.device_info,
                "ip": s.ip_address,
                "is_current": s.is_current,
            }
            for s in sessions
        ]

    async def revoke_session(self, db: AsyncSession, session_id: str, current_user: User) -> dict:
        session = await self.repository.get_session_by_id(db, session_id, current_user.id)
        if not session:
            raise NotFoundError(message=f"Session '{session_id}' not found")
        if session.family_id:
            await self.repository.revoke_refresh_family(db, session.family_id)
        await self.repository.revoke_access_session(session)
        await self.repository.delete_session(db, session)
        await self._commit(db, "Failed to revoke session")
        return {"message": f"Session {session_id} revoked", "status": "success"}

    async def request_magic_link(self, db: AsyncSession, email: str) -> dict:
        email_clean = email.strip()
        response = {
            "message": "If an account exists for that email, a magic link has been sent",
            "status": "success",
        }
        user = await self.repository.get_user_by_email(db, email_clean)
        if not user:
            return response

        magic_token = generate_random_code(14)
        expires_at = datetime.now(UTC) + timedelta(minutes=settings.MAGIC_LINK_EXPIRE_MINUTES)
        await self.repository.invalidate_magic_links(db, user.id)
        await self.repository.create_magic_link(
            db,
            user_id=user.id,
            token_digest=sha256(magic_token.encode("utf-8")).hexdigest(),
            expires_at=expires_at,
        )
        await self._commit(db, "Unable to create magic link")
        send_magic_link_email(email_to=user.email, token=magic_token, user_name=user.name)
        return response

    async def verify_magic_link(
        self, db: AsyncSession, token: str, two_factor_code: str | None = None
    ) -> dict:
        if not token or len(token) < 5:
            raise APIException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                message="Invalid or expired magic link token",
            )
        token_digest = sha256(token.strip().encode("utf-8")).hexdigest()
        magic_link = await self.repository.get_active_magic_link(
            db, token_digest=token_digest, now=datetime.now(UTC)
        )
        if not magic_link:
            raise APIException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                message="Invalid or expired magic link token",
            )
        user = await self.repository.get_user_by_id(db, magic_link.user_id)
        if not user:
            raise APIException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                message="Invalid or expired magic link token",
            )
        await self._validate_session_principal(db, user)
        if user.two_factor_enabled:
            if not two_factor_code or not self._is_valid_totp(user, two_factor_code):
                raise APIException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    code="INVALID_TWO_FACTOR_CODE",
                    message="Valid two-factor authentication is required",
                )
        await self.repository.consume_magic_link(magic_link)
        family_id = uuid.uuid4().hex
        refresh_token = await self._create_refresh_token(db, user.id, family_id=family_id)
        access_token = await self._create_access_token(db, user.id, family_id=family_id)
        await self._commit(db, "Unable to complete magic link login")
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        }

    @staticmethod
    def _require_organization_id(user: User) -> str:
        organization_id = getattr(user, "organization_id", None)
        if not organization_id:
            raise ForbiddenError(message="Authenticated user has no current organization")
        return organization_id

    async def list_api_keys(self, db: AsyncSession, current_user: User) -> list[dict]:
        organization_id = self._require_organization_id(current_user)
        keys = await self.repository.list_api_keys(db, organization_id)
        return [
            {
                "id": k.id,
                "name": k.name,
                "api_key": None,
                "key": "********",
                "created_at": str(k.created_at),
                "last_used": str(k.last_used),
                "is_active": k.is_active,
                "scopes": self._parse_api_key_scopes(k.scopes),
            }
            for k in keys
        ]

    async def create_api_key(
        self, db: AsyncSession, payload: ApiKeyCreate, current_user: User
    ) -> dict:
        try:
            organization_id = self._require_organization_id(current_user)
            scopes = self._validate_api_key_scopes(payload.scopes)
            api_key_str = f"crm_live_{generate_random_code(24)}"
            key = await self.repository.create_api_key(
                db,
                data={
                    "organization_id": organization_id,
                    "name": payload.name,
                    "key_hash": sha256(api_key_str.encode("utf-8")).hexdigest(),
                    "created_by": current_user.id,
                    "scopes": json.dumps(scopes),
                },
            )
            await self._commit(db, "Failed to create API key")
            return {
                "id": key.id,
                "name": key.name,
                "api_key": api_key_str,
                "created_at": str(key.created_at),
                "scopes": scopes,
            }
        except APIException:
            raise
        except Exception as e:
            await db.rollback()
            raise APIException(status_code=status.HTTP_400_BAD_REQUEST, message=str(e)) from e

    @staticmethod
    def _parse_api_key_scopes(raw: str | None) -> list[str]:
        if not raw:
            return []
        try:
            value = json.loads(raw)
        except ValueError:
            value = [item.strip() for item in raw.split(",")]
        return [item for item in value if isinstance(item, str) and item]

    @staticmethod
    def _validate_api_key_scopes(scopes: list[str]) -> list[str]:
        normalized = list(dict.fromkeys(scope.strip().lower() for scope in scopes if scope.strip()))
        if not normalized or any(
            len(scope) > 100
            or ":" not in scope
            or not all(part.replace("-", "").replace("_", "").isalnum() for part in scope.split(":"))
            for scope in normalized
        ):
            raise APIException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                code="INVALID_API_KEY_SCOPE",
                message="API key scopes must be non-empty colon-delimited permission names",
            )
        return normalized

    async def revoke_api_key(self, db: AsyncSession, key_id: str, current_user: User) -> dict:
        organization_id = self._require_organization_id(current_user)
        key = await self.repository.get_api_key(
            db, key_id=key_id, organization_id=organization_id
        )
        if key is None:
            raise NotFoundError(message="API key not found")
        key.is_active = False
        await self._commit(db, "Failed to revoke API key")
        return {"message": "API key revoked", "status": "success"}


auth_service = AuthService()


def api_key_scope_allows(current_user: User, permission: str) -> bool:
    """Apply the API-key scope restriction used after authoritative RBAC."""
    normalized_permission = permission.lower()
    api_key_scopes = getattr(current_user, "_api_key_scopes", None)
    if api_key_scopes is None:
        return True
    broad_scope = "api:read" if normalized_permission.endswith(":read") else "api:write"
    return normalized_permission in api_key_scopes or broad_scope in api_key_scopes
