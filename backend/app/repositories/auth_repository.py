from datetime import datetime

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    ApiKey,
    AuditLog,
    MagicLinkToken,
    Organization,
    OrganizationSetting,
    OrganizationSubscription,
    PasswordReset,
    Permission,
    RefreshToken,
    Role,
    RolePermission,
    User,
    UserInvitation,
    UserRole,
    UserSession,
)


class AuthRepository:
    """DB query layer for the Auth domain. No business logic here."""

    async def get_user_by_email(self, db: AsyncSession, email: str) -> User | None:
        result = await db.execute(select(User).where(User.email.ilike(email)))
        return result.scalars().first()

    async def get_first_user(self, db: AsyncSession) -> User | None:
        result = await db.execute(select(User).limit(1))
        return result.scalars().first()

    async def create_user(self, db: AsyncSession, *, data: dict) -> User:
        user = User(**data)
        db.add(user)
        return user

    async def get_user_by_id(self, db: AsyncSession, user_id: str) -> User | None:
        return await db.get(User, user_id)

    async def invalidate_magic_links(self, db: AsyncSession, user_id: str) -> None:
        await db.execute(
            update(MagicLinkToken)
            .where(MagicLinkToken.user_id == user_id, MagicLinkToken.is_used.is_(False))
            .values(is_used=True)
        )

    async def create_magic_link(
        self,
        db: AsyncSession,
        *,
        user_id: str,
        token_digest: str,
        expires_at: datetime,
    ) -> MagicLinkToken:
        magic_link = MagicLinkToken(
            user_id=user_id,
            token=token_digest,
            expires_at=expires_at,
        )
        db.add(magic_link)
        return magic_link

    async def get_active_magic_link(
        self,
        db: AsyncSession,
        *,
        token_digest: str,
        now: datetime,
    ) -> MagicLinkToken | None:
        result = await db.execute(
            select(MagicLinkToken)
            .where(
                MagicLinkToken.token == token_digest,
                MagicLinkToken.is_used.is_(False),
                MagicLinkToken.expires_at > now,
            )
            .with_for_update()
        )
        return result.scalars().first()

    async def consume_magic_link(self, magic_link: MagicLinkToken) -> None:
        magic_link.is_used = True

    async def create_refresh_token(
        self,
        db: AsyncSession,
        *,
        user_id: str,
        token_digest: str,
        expires_at: datetime,
    ) -> RefreshToken:
        refresh_token = RefreshToken(
            user_id=user_id,
            token=token_digest,
            expires_at=expires_at,
        )
        db.add(refresh_token)
        return refresh_token

    async def get_active_refresh_token(
        self,
        db: AsyncSession,
        *,
        token_digest: str,
        now: datetime,
    ) -> RefreshToken | None:
        result = await db.execute(
            select(RefreshToken)
            .where(
                RefreshToken.token == token_digest,
                RefreshToken.is_revoked.is_(False),
                RefreshToken.expires_at > now,
            )
            .with_for_update()
        )
        return result.scalars().first()

    async def revoke_refresh_token(self, refresh_token: RefreshToken) -> None:
        refresh_token.is_revoked = True

    async def get_session_by_access_token(
        self, db: AsyncSession, token_digest: str
    ) -> UserSession | None:
        return await db.get(UserSession, token_digest)

    async def create_access_session(
        self, db: AsyncSession, *, token_digest: str, user_id: str
    ) -> UserSession:
        session = UserSession(id=token_digest, user_id=user_id, is_current=True)
        db.add(session)
        return session

    async def revoke_access_session(self, session: UserSession) -> None:
        session.is_current = False

    async def invalidate_password_resets(self, db: AsyncSession, user_id: str) -> None:
        await db.execute(
            update(PasswordReset)
            .where(PasswordReset.user_id == user_id, PasswordReset.is_used.is_(False))
            .values(is_used=True)
        )

    async def create_password_reset(
        self,
        db: AsyncSession,
        *,
        user_id: str,
        token_digest: str,
        expires_at: datetime,
    ) -> PasswordReset:
        password_reset = PasswordReset(
            user_id=user_id,
            token=token_digest,
            expires_at=expires_at,
        )
        db.add(password_reset)
        return password_reset

    async def get_active_password_reset(
        self,
        db: AsyncSession,
        *,
        token_digest: str,
        now: datetime,
    ) -> PasswordReset | None:
        result = await db.execute(
            select(PasswordReset)
            .where(
                PasswordReset.token == token_digest,
                PasswordReset.is_used.is_(False),
                PasswordReset.expires_at > now,
            )
            .with_for_update()
        )
        return result.scalars().first()

    async def set_user_password(self, user: User, hashed_password: str) -> None:
        user.hashed_password = hashed_password

    async def mark_password_reset_used(self, password_reset: PasswordReset) -> None:
        password_reset.is_used = True

    async def get_first_org(self, db: AsyncSession) -> Organization | None:
        result = await db.execute(select(Organization).limit(1))
        return result.scalars().first()

    async def create_org(self, db: AsyncSession, *, name: str) -> Organization:
        org = Organization(name=name)
        db.add(org)
        return org

    async def create_organization_setting(
        self, db: AsyncSession, *, organization_id: str, timezone: str, currency: str
    ) -> OrganizationSetting:
        setting = OrganizationSetting(
            organization_id=organization_id,
            timezone=timezone,
            currency=currency,
        )
        db.add(setting)
        return setting

    async def create_organization_subscription(
        self, db: AsyncSession, *, organization_id: str, currency: str
    ) -> OrganizationSubscription:
        subscription = OrganizationSubscription(
            organization_id=organization_id,
            status="active",
            billing_cycle="Monthly",
            amount=0,
            currency=currency,
            payment_provider="Stripe",
            max_users=3,
            current_users=1,
            storage_limit_gb=5,
            storage_used_gb=0,
            ai_credits=50,
        )
        db.add(subscription)
        return subscription

    async def record_organization_initialization(
        self, db: AsyncSession, *, organization_id: str, user_id: str
    ) -> AuditLog:
        audit = AuditLog(
            organization_id=organization_id,
            user_id=user_id,
            action="organization.initialized",
            details="Organization, settings, subscription, administrator and RBAC mapping created",
        )
        db.add(audit)
        return audit

    async def get_invitation_by_token(
        self, db: AsyncSession, token: str, *, for_update: bool = False
    ) -> UserInvitation | None:
        stmt = select(UserInvitation).where(UserInvitation.token == token.strip())
        if for_update:
            stmt = stmt.with_for_update()
        result = await db.execute(stmt)
        return result.scalars().first()

    async def get_organization_by_id(
        self, db: AsyncSession, organization_id: str
    ) -> Organization | None:
        return await db.get(Organization, organization_id)

    async def get_role_for_organization(
        self, db: AsyncSession, role_value: str, organization_id: str
    ) -> Role | None:
        ownership_filter = (Role.organization_id.is_(None)) | (
            Role.organization_id == organization_id
        )
        result = await db.execute(
            select(Role).where(Role.id == role_value, ownership_filter).limit(1)
        )
        role = result.scalars().first()
        if role:
            return role

        result = await db.execute(
            select(Role)
            .where(
                func.lower(Role.name) == role_value.strip().lower(),
                ownership_filter,
            )
            .order_by(Role.organization_id.is_(None))
            .limit(1)
        )
        return result.scalars().first()

    async def assign_user_role(self, db: AsyncSession, *, user_id: str, role_id: str) -> UserRole:
        # User.role is singular throughout the application. Replace every
        # mapping so stale rows cannot retain permissions from an older role.
        await db.execute(delete(UserRole).where(UserRole.user_id == user_id))
        mapping = UserRole(user_id=user_id, role_id=role_id)
        db.add(mapping)
        return mapping

    async def get_invitation_by_email(
        self, db: AsyncSession, email: str, *, status: str | None = None
    ) -> UserInvitation | None:
        stmt = select(UserInvitation).where(UserInvitation.email.ilike(email))
        if status:
            stmt = stmt.where(UserInvitation.status == status)
        result = await db.execute(stmt.limit(1))
        return result.scalars().first()

    async def list_invitations_by_email(
        self, db: AsyncSession, email: str, *, exclude_id: str | None = None
    ) -> list[UserInvitation]:
        stmt = select(UserInvitation).where(UserInvitation.email.ilike(email))
        if exclude_id:
            stmt = stmt.where(UserInvitation.id != exclude_id)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_role_name_by_id(self, db: AsyncSession, role_id: str) -> str | None:
        result = await db.execute(select(Role.name).where(Role.id == role_id))
        return result.scalars().first()

    async def get_user_role_id(self, db: AsyncSession, user_id: str) -> str | None:
        result = await db.execute(select(UserRole.role_id).where(UserRole.user_id == user_id))
        return result.scalars().first()

    async def all_permission_keys(self, db: AsyncSession) -> list[str]:
        result = await db.execute(select(Permission.key))
        return [key for key in result.scalars().all() if key]

    async def role_ids_for_user(self, db: AsyncSession, user_id: str) -> list[str]:
        result = await db.execute(select(UserRole.role_id).where(UserRole.user_id == user_id))
        return [role_id for role_id in result.scalars().all() if role_id]

    async def role_ids_by_name(
        self,
        db: AsyncSession,
        role_name: str,
        organization_id: str,
        *,
        global_only: bool = False,
    ) -> list[str]:
        ownership_filter = (
            Role.organization_id.is_(None)
            if global_only
            else (Role.organization_id.is_(None)) | (Role.organization_id == organization_id)
        )
        result = await db.execute(
            select(Role.id).where(
                func.lower(Role.name) == role_name.strip().lower(),
                ownership_filter,
            )
        )
        return [role_id for role_id in result.scalars().all() if role_id]

    async def roles_by_ids(
        self, db: AsyncSession, role_ids: list[str], organization_id: str
    ) -> list[Role]:
        result = await db.execute(
            select(Role).where(
                Role.id.in_(list(role_ids)),
                (Role.organization_id.is_(None)) | (Role.organization_id == organization_id),
            )
        )
        return list(result.scalars().all())

    async def permission_keys_for_roles(self, db: AsyncSession, role_ids: list[str]) -> list[str]:
        result = await db.execute(
            select(Permission.key)
            .join(RolePermission, Permission.id == RolePermission.permission_id)
            .where(RolePermission.role_id.in_(list(role_ids)))
        )
        return [key for key in result.scalars().all() if key]

    async def list_sessions(self, db: AsyncSession, user_id: str) -> list[UserSession]:
        result = await db.execute(
            select(UserSession).where(UserSession.user_id == user_id).limit(10)
        )
        return list(result.scalars().all())

    async def get_session_by_id(
        self, db: AsyncSession, session_id: str, user_id: str
    ) -> UserSession | None:
        result = await db.execute(
            select(UserSession).where(
                UserSession.id == session_id,
                UserSession.user_id == user_id,
            )
        )
        return result.scalars().first()

    async def delete_session(self, db: AsyncSession, session: UserSession) -> None:
        await db.delete(session)

    async def list_api_keys(self, db: AsyncSession, organization_id: str) -> list[ApiKey]:
        result = await db.execute(
            select(ApiKey).where(ApiKey.organization_id == organization_id).limit(10)
        )
        return list(result.scalars().all())

    async def create_api_key(self, db: AsyncSession, *, data: dict) -> ApiKey:
        key = ApiKey(**data)
        db.add(key)
        return key
