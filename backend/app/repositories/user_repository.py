import builtins
from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Deal, Organization, Role, User, UserInvitation, UserQuota


class UserRepository:
    """DB query layer for the User/Invitation domain. No business logic here."""

    # --- Quotas ---
    async def get_quota(self, db: AsyncSession, user_id: str) -> UserQuota | None:
        res = await db.execute(select(UserQuota).where(UserQuota.user_id == user_id))
        return res.scalar_one_or_none()

    async def upsert_quota(
        self, db: AsyncSession, *, user_id: str, organization_id: str, target_amount: float
    ) -> UserQuota:
        quota = await self.get_quota(db, user_id)
        if quota:
            quota.target_amount = target_amount
            return quota
        new_quota = UserQuota(
            organization_id=organization_id,
            user_id=user_id,
            target_amount=target_amount,
        )
        db.add(new_quota)
        return new_quota

    async def total_won_revenue(self, db: AsyncSession, user_id: str) -> float:
        res = await db.execute(
            select(func.coalesce(func.sum(Deal.amount), 0.0)).where(
                Deal.assigned_to == user_id,
                Deal.stage == "Closed Won",
            )
        )
        return float(res.scalar() or 0.0)

    async def list(
        self,
        db: AsyncSession,
        *,
        page: int,
        limit: int,
        search: str | None = None,
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

    async def get_by_id(self, db: AsyncSession, user_id: str) -> User | None:
        result = await db.execute(select(User).where(User.id == user_id))
        return result.scalars().first()

    async def get_first(self, db: AsyncSession) -> User | None:
        result = await db.execute(select(User).limit(1))
        return result.scalars().first()

    async def get_by_email(self, db: AsyncSession, email: str) -> User | None:
        result = await db.execute(select(User).where(User.email.ilike(email)))
        return result.scalars().first()

    async def create(self, db: AsyncSession, *, data: dict) -> User:
        user = User(**data)
        db.add(user)
        return user

    async def delete(self, db: AsyncSession, user: User) -> None:
        await db.delete(user)

    async def list_by_ids(self, db: AsyncSession, ids: builtins.list[str]) -> builtins.list[User]:
        result = await db.execute(select(User).where(User.id.in_(ids)))
        return list(result.scalars().all())

    async def list_active_ids_by_org(self, db: AsyncSession, org_id: str) -> Sequence[str]:
        result = await db.execute(
            select(User.id).where(
                User.organization_id == org_id,
                User.is_active == True,  # noqa: E712
            )
        )
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
        token: str | None = None,
        status_filter: str | None = None,
    ) -> builtins.list[UserInvitation]:
        stmt = select(UserInvitation)
        if token and token.strip():
            stmt = stmt.where(UserInvitation.token == token.strip())
        elif status_filter and status_filter.strip():
            stmt = stmt.where(UserInvitation.status == status_filter.strip())
        stmt = stmt.order_by(UserInvitation.created_at.desc())
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_invitation_by_token(self, db: AsyncSession, token: str) -> UserInvitation | None:
        result = await db.execute(
            select(UserInvitation).where(UserInvitation.token == token.strip())
        )
        return result.scalars().first()

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
    ) -> builtins.list[UserInvitation]:
        stmt = select(UserInvitation).where(UserInvitation.email.ilike(email))
        if exclude_id:
            stmt = stmt.where(UserInvitation.id != exclude_id)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def create_invitation(self, db: AsyncSession, *, data: dict) -> UserInvitation:
        invitation = UserInvitation(**data)
        db.add(invitation)
        return invitation

    async def get_first_org(self, db: AsyncSession) -> Organization | None:
        result = await db.execute(select(Organization).limit(1))
        return result.scalars().first()

    async def create_org(self, db: AsyncSession, *, name: str) -> Organization:
        org = Organization(name=name)
        db.add(org)
        return org
