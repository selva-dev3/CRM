from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Organization, Role, User, UserInvitation


class UserRepository:
    """DB query layer for the User/Invitation domain. No business logic here."""

    async def list(
        self,
        db: AsyncSession,
        *,
        page: int,
        limit: int,
        search: Optional[str] = None,
    ) -> list[User]:
        stmt = select(User)
        cleaned_search = (
            search.strip() if search and isinstance(search, str) and search.strip() else None
        )
        if cleaned_search:
            pattern = f"%{cleaned_search}%"
            stmt = stmt.where(User.name.ilike(pattern) | User.email.ilike(pattern))
        actual_page = page if isinstance(page, int) else 1
        actual_limit = limit if isinstance(limit, int) else 20
        stmt = stmt.offset((actual_page - 1) * actual_limit).limit(actual_limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_by_id(self, db: AsyncSession, user_id: str) -> Optional[User]:
        result = await db.execute(select(User).where(User.id == user_id))
        return result.scalars().first()

    async def get_first(self, db: AsyncSession) -> Optional[User]:
        result = await db.execute(select(User).limit(1))
        return result.scalars().first()

    async def get_by_email(self, db: AsyncSession, email: str) -> Optional[User]:
        result = await db.execute(select(User).where(User.email.ilike(email)))
        return result.scalars().first()

    async def create(self, db: AsyncSession, *, data: dict) -> User:
        user = User(**data)
        db.add(user)
        return user

    async def delete(self, db: AsyncSession, user: User) -> None:
        await db.delete(user)

    async def list_by_ids(self, db: AsyncSession, ids: list[str]) -> list[User]:
        result = await db.execute(select(User).where(User.id.in_(ids)))
        return list(result.scalars().all())

    async def role_name_map(self, db: AsyncSession, role_ids: set) -> dict:
        role_map: dict = {}
        if role_ids:
            result = await db.execute(
                select(Role).where((Role.id.in_(role_ids)) | (Role.name.in_(role_ids)))
            )
            for role in result.scalars().all():
                role_map[role.id] = role.name
                role_map[role.name] = role.name
        return role_map

    async def list_invitations(
        self,
        db: AsyncSession,
        *,
        token: Optional[str] = None,
        status_filter: Optional[str] = None,
    ) -> list[UserInvitation]:
        stmt = select(UserInvitation)
        if token and token.strip():
            stmt = stmt.where(UserInvitation.token == token.strip())
        elif status_filter and status_filter.strip():
            stmt = stmt.where(UserInvitation.status == status_filter.strip())
        stmt = stmt.order_by(UserInvitation.created_at.desc())
        result = await db.execute(stmt)
        return list(result.scalars().all())

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

    async def create_invitation(self, db: AsyncSession, *, data: dict) -> UserInvitation:
        invitation = UserInvitation(**data)
        db.add(invitation)
        return invitation

    async def get_first_org(self, db: AsyncSession) -> Optional[Organization]:
        result = await db.execute(select(Organization).limit(1))
        return result.scalars().first()

    async def create_org(self, db: AsyncSession, *, name: str) -> Organization:
        org = Organization(name=name)
        db.add(org)
        return org