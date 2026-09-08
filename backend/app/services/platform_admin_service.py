"""Explicit offline provisioning; never called by registration or startup."""

from pydantic import EmailStr, SecretStr, TypeAdapter
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError
from app.core.logging import get_logger
from app.core.security import get_password_hash
from app.repositories.auth_repository import AuthRepository
from app.repositories.role_repository import RoleRepository

logger = get_logger(__name__)


class PlatformAdminService:
    def __init__(self, repository: AuthRepository | None = None) -> None:
        self.repository = repository or AuthRepository()
        self.roles = RoleRepository()

    async def provision(
        self,
        db: AsyncSession,
        *,
        email: str,
        password: SecretStr,
        existing_user_id: str | None = None,
    ) -> str:
        """Preserve an existing identity; never merge accounts or guess an email conflict."""
        normalized_email = str(TypeAdapter(EmailStr).validate_python(email)).lower()
        if not 8 <= len(password.get_secret_value().encode()) <= 72:
            raise ConflictError(message="Initial password must contain between 8 and 72 bytes")
        try:
            await self.repository.lock_platform_provisioning(db)
            user = await self.repository.get_platform_admin(db)
            email_owner = await self.repository.get_unique_email_owner(db, normalized_email)
            if user and existing_user_id != user.id:
                raise ConflictError(
                    message="Confirm the existing platform user ID before updating credentials"
                )
            if user and email_owner and email_owner.id != user.id:
                raise ConflictError(
                    message="The requested email belongs to another account; no accounts were merged"
                )
            if not user and existing_user_id:
                user = await self.repository.get_user_by_id(db, existing_user_id)
                if not user or (email_owner and email_owner.id != user.id):
                    raise ConflictError(
                        message="The intended existing account could not be resolved safely"
                    )
            if not user and email_owner:
                raise ConflictError(
                    message="Confirm the existing email owner's user ID before conversion"
                )
            role = await self.roles.get_global_role_by_names(db, ("super admin", "super_admin"))
            if not role:
                raise ConflictError(
                    message="Global Super Admin role must be initialized before provisioning"
                )
            hashed_password = get_password_hash(password.get_secret_value())
            if user:
                if not user.is_platform_admin:
                    # Scope integrity rejects a platform account retaining a
                    # tenant mapping. Clear it before changing the user scope;
                    # rollback restores both if provisioning later fails.
                    await self.repository.clear_user_roles(db, user_id=user.id)
                    await db.flush()
                user.email = normalized_email
                user.hashed_password = hashed_password
                user.is_platform_admin = True
                user.organization_id = None
                user.role = "Super Admin"
                user.is_active = True
                user.is_verified = True
            else:
                user = await self.repository.create_user(
                    db,
                    data={
                        "name": "Super Admin",
                        "email": normalized_email,
                        "hashed_password": hashed_password,
                        "is_platform_admin": True,
                        "organization_id": None,
                        "role": "Super Admin",
                        "is_active": True,
                        "is_verified": True,
                    },
                )
            await db.flush()
            await self.repository.assign_user_role(db, user_id=user.id, role_id=role.id)
            await self.repository.revoke_all_user_sessions(db, user.id)
            await self.repository.invalidate_password_resets(db, user.id)
            await self.repository.invalidate_magic_links(db, user.id)
            await db.commit()
            return user.id
        except Exception:
            try:
                await db.rollback()
            except Exception:
                logger.error("Platform provisioning rollback failed")
            raise
