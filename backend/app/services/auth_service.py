import logging
from datetime import UTC, datetime, timedelta
from hashlib import sha256

from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import APIException, NotFoundError
from app.core.permissions import is_super_admin_role, is_super_admin_role_name
from app.core.security import (
    create_access_token,
    generate_random_code,
    get_password_hash,
    verify_password,
)
from app.models import User
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

    async def get_user_role_name(self, db: AsyncSession, user: User) -> str:
        """Resolve human-readable role name (e.g. 'Admin', 'Super Admin') for a user."""
        try:
            raw_role = (user.role or "").strip()

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
            role_ids = set(await self.repository.role_ids_for_user(db, user.id))
            role_lookup = (resolved_role_name or user.role or "").strip()
            if role_lookup:
                role_ids.update(await self.repository.role_ids_by_name(db, role_lookup))

            if is_super_admin_role_name(role_lookup):
                permission_keys.update(await self.repository.all_permission_keys(db))
                return sorted(permission_keys)

            if role_ids:
                keys = await self.repository.permission_keys_for_roles(db, list(role_ids))
                permission_keys.update(keys)
                roles = await self.repository.roles_by_ids(db, list(role_ids))
                if any(is_super_admin_role(r) for r in roles):
                    permission_keys.update(await self.repository.all_permission_keys(db))
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

        access_token = create_access_token(user.id)
        user_role_name = await self.get_user_role_name(db, user)
        user_permissions = await self.get_user_permissions(
            db, user, resolved_role_name=user_role_name
        )

        return {
            "access_token": access_token,
            "refresh_token": f"refresh_{user.id}",
            "token_type": "bearer",
            "expires_in": 86400,
            "user": {
                "id": user.id,
                "name": user.name,
                "email": user.email,
                "role": user_role_name,
                "organization_id": user.organization_id,
                "permissions": user_permissions,
            },
        }

    async def get_current_user_me(self, db: AsyncSession, user: User | None = None) -> dict:
        user = user or await self.repository.get_first_user(db)
        if not user:
            raise NotFoundError(message="User profile not found")

        user_role_name = await self.get_user_role_name(db, user)
        user_permissions = await self.get_user_permissions(
            db, user, resolved_role_name=user_role_name
        )

        return {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "role": user_role_name,
            "organization_id": user.organization_id,
            "permissions": user_permissions,
        }

    async def register(self, db: AsyncSession, payload: RegisterRequest) -> dict:
        try:
            existing = await self.repository.get_user_by_email(db, payload.email)
            if existing:
                raise APIException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    message="User with this email already exists",
                )

            org = await self.repository.create_org(db, name=payload.organization_name)
            await db.flush()

            try:
                hashed_pwd = get_password_hash(payload.password)
            except Exception as e:
                logger.exception("Password hashing failed during registration")
                raise APIException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    code="PASSWORD_HASHING_FAILED",
                    message="Unable to create account. Please try again later.",
                ) from e

            user = await self.repository.create_user(
                db,
                data={
                    "name": payload.name,
                    "email": payload.email,
                    "hashed_password": hashed_pwd,
                    "organization_id": org.id,
                    "role": "Admin",
                },
            )
            await db.commit()
            return {
                "message": "Registration successful",
                "user_id": user.id,
                "org_id": org.id,
                "name": user.name,
                "email": user.email,
                "role": user.role,
            }
        except APIException:
            await db.rollback()
            raise
        except Exception as e:
            await db.rollback()
            raise APIException(
                status_code=status.HTTP_400_BAD_REQUEST, message=f"Registration failed: {str(e)}"
            ) from e

    async def refresh_token(self, db: AsyncSession, refresh_token: str) -> dict:
        user = await self.repository.get_first_user(db)
        user_id = user.id if user else "usr-1"
        access_token = create_access_token(user_id)
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": 86400,
        }

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
        await self._commit(db, "Unable to update password")
        return {"message": "Password changed successfully", "status": "success"}

    async def setup_2fa(self) -> dict:
        return {
            "secret": "JBSWY3DPEHPK3PXP",
            "qr_code_url": "https://api.qrserver.com/v1/create-qr-code/?data=otpauth://totp/CRM:user",
        }

    async def verify_2fa(self, payload: TwoFactorVerifyRequest) -> dict:
        if payload.code != "123456":
            raise APIException(
                status_code=status.HTTP_400_BAD_REQUEST, message="Invalid 2FA authentication code"
            )
        return {"message": "2FA verified successfully", "status": "success"}

    async def disable_2fa(self) -> dict:
        return {"message": "2FA disabled successfully", "status": "success"}

    async def _oauth_issue_token(self, db: AsyncSession, refresh_value: str) -> dict:
        user = await self.repository.get_first_user(db)
        access_token = create_access_token(user.id if user else "usr-1")
        return {
            "access_token": access_token,
            "refresh_token": refresh_value,
            "token_type": "bearer",
            "expires_in": 86400,
        }

    async def google_oauth(self, db: AsyncSession, payload: OAuthLoginRequest) -> dict:
        if not payload.id_token:
            raise APIException(
                status_code=status.HTTP_400_BAD_REQUEST, message="Authorization code is required"
            )
        return await self._oauth_issue_token(db, "google_refresh")

    async def microsoft_oauth(self, db: AsyncSession, payload: OAuthLoginRequest) -> dict:
        if not payload.id_token:
            raise APIException(
                status_code=status.HTTP_400_BAD_REQUEST, message="Authorization code is required"
            )
        return await self._oauth_issue_token(db, "ms_refresh")

    async def get_auth_invitation_details(self, db: AsyncSession, token: str) -> dict:
        inv = await self.repository.get_invitation_by_token(db, token)
        if not inv:
            raise NotFoundError(message="Invitation not found or token invalid")
        accepted_any = await self.repository.get_invitation_by_email(
            db, inv.email, status="accepted"
        )
        if accepted_any:
            inv.status = "accepted"
        return {
            "id": inv.id,
            "email": inv.email,
            "role": inv.role,
            "status": inv.status,
            "organization_id": inv.organization_id,
            "created_at": str(inv.created_at),
        }

    async def accept_auth_user_invitation(
        self, db: AsyncSession, payload: AcceptInviteRequest
    ) -> dict:
        inv = await self.repository.get_invitation_by_token(db, payload.token)
        if not inv:
            raise NotFoundError(message="Invalid or expired invitation token")

        accepted_any = await self.repository.get_invitation_by_email(
            db, inv.email, status="accepted"
        )
        if inv.status == "accepted" or accepted_any:
            inv.status = "accepted"
            await db.commit()
            raise APIException(
                status_code=status.HTTP_400_BAD_REQUEST,
                message="Invitation has already been accepted",
            )

        try:
            org = await self.repository.get_first_org(db)
            if not org:
                org = await self.repository.create_org(db, name="Default Enterprise CRM")
                await db.flush()
            target_org_id = (
                inv.organization_id
                if inv.organization_id and len(inv.organization_id) > 5
                else org.id
            )

            user = await self.repository.get_user_by_email(db, inv.email)
            hashed_pwd = get_password_hash(payload.password)

            if user:
                user.name = payload.name
                user.hashed_password = hashed_pwd
                user.role = inv.role
                user.organization_id = target_org_id
                user.is_active = True
            else:
                user = await self.repository.create_user(
                    db,
                    data={
                        "name": payload.name,
                        "email": inv.email,
                        "hashed_password": hashed_pwd,
                        "role": inv.role,
                        "organization_id": target_org_id,
                        "is_active": True,
                    },
                )
                await db.flush()

            inv.status = "accepted"
            for other in await self.repository.list_invitations_by_email(
                db, inv.email, exclude_id=inv.id
            ):
                other.status = "accepted"

            await db.commit()

            access_token = create_access_token(user.id)
            user_role_name = await self.get_user_role_name(db, user)
            user_permissions = await self.get_user_permissions(
                db, user, resolved_role_name=user_role_name
            )

            return {
                "message": "Invitation accepted successfully! Your account is active.",
                "access_token": access_token,
                "token_type": "bearer",
                "user_id": user.id,
                "email": user.email,
                "name": user.name,
                "role": user_role_name,
                "status": "success",
                "user": {
                    "id": user.id,
                    "name": user.name,
                    "email": user.email,
                    "role": user_role_name,
                    "organization_id": user.organization_id,
                    "permissions": user_permissions,
                },
            }
        except Exception as e:
            await db.rollback()
            raise APIException(
                status_code=status.HTTP_400_BAD_REQUEST,
                message=f"Failed to accept invitation: {str(e)}",
            ) from e

    async def list_sessions(self, db: AsyncSession) -> list[dict]:
        sessions = await self.repository.list_sessions(db)
        return [
            {
                "session_id": s.id,
                "device": s.device_info,
                "ip": s.ip_address,
                "is_current": s.is_current,
            }
            for s in sessions
        ]

    async def revoke_session(self, db: AsyncSession, session_id: str) -> dict:
        session = await self.repository.get_session_by_id(db, session_id)
        if not session:
            raise NotFoundError(message=f"Session '{session_id}' not found")
        await self.repository.delete_session(db, session)
        await self._commit(db, "Failed to revoke session")
        return {"message": f"Session {session_id} revoked", "status": "success"}

    async def request_magic_link(self, db: AsyncSession, email: str) -> dict:
        email_clean = email.strip()
        user = await self.repository.get_user_by_email(db, email_clean)
        if not user:
            raise NotFoundError(message=f"User with email '{email_clean}' not found")

        magic_token = generate_random_code(14)
        send_magic_link_email(email_to=user.email, token=magic_token, user_name=user.name)
        return {"message": f"Magic link sent to {email_clean}", "status": "success"}

    async def verify_magic_link(self, db: AsyncSession, token: str) -> dict:
        if not token or len(token) < 5:
            raise APIException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                message="Invalid or expired magic link token",
            )
        user = await self.repository.get_first_user(db)
        access_token = create_access_token(user.id if user else "usr-1")
        return {
            "access_token": access_token,
            "refresh_token": "magic_refresh",
            "token_type": "bearer",
            "expires_in": 86400,
        }

    async def list_api_keys(self, db: AsyncSession) -> list[dict]:
        keys = await self.repository.list_api_keys(db)
        return [
            {
                "id": k.id,
                "name": k.name,
                "api_key": k.key_hash,
                "created_at": str(k.created_at),
                "last_used": str(k.last_used),
            }
            for k in keys
        ]

    async def create_api_key(self, db: AsyncSession, payload: ApiKeyCreate) -> dict:
        try:
            org = await self.repository.get_first_org(db)
            if not org:
                org = await self.repository.create_org(db, name="Default Enterprise CRM")
                await db.flush()

            api_key_str = f"crm_live_{generate_random_code(24)}"
            key = await self.repository.create_api_key(
                db,
                data={
                    "organization_id": org.id,
                    "name": payload.name,
                    "key_hash": api_key_str,
                },
            )
            await self._commit(db, "Failed to create API key")
            return {
                "id": key.id,
                "name": key.name,
                "api_key": key.key_hash,
                "created_at": str(key.created_at),
            }
        except Exception as e:
            await db.rollback()
            raise APIException(status_code=status.HTTP_400_BAD_REQUEST, message=str(e)) from e


auth_service = AuthService()
