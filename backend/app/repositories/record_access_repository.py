from inspect import isawaitable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import RoleRecordScope, TeamMembership, UserRole


class RecordAccessRepository:
    async def role_id_for_user(self, db: AsyncSession, user_id: str) -> str | None:
        value = await db.scalar(select(UserRole.role_id).where(UserRole.user_id == user_id))
        return value if isinstance(value, str) else None

    async def scope_for_role(
        self, db: AsyncSession, role_id: str, module: str
    ) -> str | None:
        value = await db.scalar(
            select(RoleRecordScope.scope).where(
                RoleRecordScope.role_id == role_id,
                RoleRecordScope.module == module,
            )
        )
        return value if isinstance(value, str) else None

    async def team_ids_for_user(self, db: AsyncSession, user_id: str) -> frozenset[str]:
        rows = (
            await db.scalars(
                select(TeamMembership.team_id).where(TeamMembership.user_id == user_id)
            )
        ).all()
        if isawaitable(rows):
            rows = await rows
        return frozenset(value for value in rows if isinstance(value, str))

    async def user_ids_for_teams(
        self, db: AsyncSession, team_ids: frozenset[str]
    ) -> frozenset[str]:
        if not team_ids:
            return frozenset()
        rows = (
            await db.scalars(
                select(TeamMembership.user_id).where(TeamMembership.team_id.in_(team_ids))
            )
        ).all()
        if isawaitable(rows):
            rows = await rows
        return frozenset(value for value in rows if isinstance(value, str))


record_access_repository = RecordAccessRepository()
