from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    ApiKey,
    Organization,
    Permission,
    Role,
    RolePermission,
    User,
    UserInvitation,
    UserRole,
    UserSession,
)


class AuthRepository:
    """DB query layer for the Auth domain. No business logic here."""

    async def get_user_by_email(self, db: AsyncSession, email: str) -> Optional[User]:
        result = await db.execute(select(User).where(User.email.ilike(email)))
        return result.scalars().first()

    async def get_first_user(self, db: AsyncSession) -> Optional[User]:
        result = await db.execute(select(User).limit(1))
        return result.scalars().first()

    async def create_user(self, db: AsyncSession, *, data: dict) -> User:
        user = User(**data)
        db.add(user)
        return user

    async def get_first_org(self, db: AsyncSession) -> Optional[Organization]:
        result = await db.execute(select(Organization).limit(1))
        return result.scalars().first()

    async def create_org(self, db: AsyncSession, *, name: str) -> Organization:
        org = Organization(name=name)
        db.add(org)
        return org

    async def get_invitation_by_token(
        self, db: AsyncSession, token: str
    ) -> Optional[UserInvitation]:
        result = await db.execute(
            select(UserInvitation).where(UserInvitation.token == token.strip())
        )
        return result.scalars().first()

    async def get_invitation_by_email(
        self, db: AsyncSession, email: str, *, status: Optional[str] = None
    ) -> Optional[UserInvitation]:
        stmt = select(UserInvitation).where(UserInvitation.email.ilike(email))
        if status:
            stmt = stmt.where(UserInvitation.status == status)
        result = await db.execute(stmt.limit(1))
        return result.scalars().first()

    async def list_invitations_by_email(
        self, db: AsyncSession, email: str, *, exclude_id: Optional[str] = None
    ) -> list[UserInvitation]:
        stmt = select(UserInvitation).where(UserInvitation.email.ilike(email))
        if exclude_id:
            stmt = stmt.where(UserInvitation.id != exclude_id)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_role_name_by_id(self, db: AsyncSession, role_id: str) -> Optional[str]:
        result = await db.execute(select(Role.name).where(Role.id == role_id))
        return result.scalars().first()

    async def get_user_role_id(self, db: AsyncSession, user_id: str) -> Optional[str]:
        result = await db.execute(select(UserRole.role_id).where(UserRole.user_id == user_id))
        return result.scalars().first()

    async def all_permission_keys(self, db: AsyncSession) -> list[str]:
        result = await db.execute(select(Permission.key))
        return [key for key in result.scalars().all() if key]

    async def role_ids_for_user(self, db: AsyncSession, user_id: str) -> list[str]:
        result = await db.execute(select(UserRole.role_id).where(UserRole.user_id == user_id))
        return [role_id for role_id in result.scalars().all() if role_id]

    async def role_ids_by_name(self, db: AsyncSession, role_name: str) -> list[str]:
        result = await db.execute(
            select(Role.id).where(func.lower(Role.name) == role_name.strip().lower())
        )
        return [role_id for role_id in result.scalars().all() if role_id]

    async def roles_by_ids(self, db: AsyncSession, role_ids: list[str]) -> list[Role]:
        result = await db.execute(select(Role).where(Role.id.in_(list(role_ids))))
        return list(result.scalars().all())

    async def permission_keys_for_roles(self, db: AsyncSession, role_ids: list[str]) -> list[str]:
        result = await db.execute(
            select(Permission.key)
            .join(RolePermission, Permission.id == RolePermission.permission_id)
            .where(RolePermission.role_id.in_(list(role_ids)))
        )
        return [key for key in result.scalars().all() if key]

    async def list_sessions(self, db: AsyncSession) -> list[UserSession]:
        result = await db.execute(select(UserSession).limit(10))
        return list(result.scalars().all())

    async def get_session_by_id(self, db: AsyncSession, session_id: str) -> Optional[UserSession]:
        result = await db.execute(select(UserSession).where(UserSession.id == session_id))
        return result.scalars().first()

    async def delete_session(self, db: AsyncSession, session: UserSession) -> None:
        await db.delete(session)

    async def list_api_keys(self, db: AsyncSession) -> list[ApiKey]:
        result = await db.execute(select(ApiKey).limit(10))
        return list(result.scalars().all())

    async def create_api_key(self, db: AsyncSession, *, data: dict) -> ApiKey:
        key = ApiKey(**data)
        db.add(key)
        return key