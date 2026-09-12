from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Team, TeamMembership, User


class TeamRepository:
    async def list(
        self, db: AsyncSession, organization_id: str, *, search: str | None, offset: int, limit: int
    ):
        count = (
            select(func.count()).select_from(Team).where(Team.organization_id == organization_id)
        )
        query = select(Team).where(Team.organization_id == organization_id)
        if search:
            pattern = f"%{search.strip()}%"
            condition = or_(Team.name.ilike(pattern), Team.description.ilike(pattern))
            query, count = query.where(condition), count.where(condition)
        rows = (await db.scalars(query.order_by(Team.name).offset(offset).limit(limit))).all()
        total = int((await db.scalar(count)) or 0)
        member_counts = (
            dict(
                (
                    await db.execute(
                        select(TeamMembership.team_id, func.count())
                        .where(TeamMembership.team_id.in_([r.id for r in rows]))
                        .group_by(TeamMembership.team_id)
                    )
                ).all()
            )
            if rows
            else {}
        )
        return rows, total, member_counts

    async def get(self, db: AsyncSession, team_id: str, organization_id: str):
        return await db.scalar(
            select(Team).where(Team.id == team_id, Team.organization_id == organization_id)
        )

    async def members(self, db: AsyncSession, team_id: str):
        return (
            await db.execute(
                select(User, TeamMembership.is_primary)
                .join(TeamMembership, TeamMembership.user_id == User.id)
                .where(TeamMembership.team_id == team_id)
                .order_by(User.name)
            )
        ).all()

    async def user(self, db: AsyncSession, user_id: str, organization_id: str):
        return await db.scalar(
            select(User).where(
                User.id == user_id,
                User._organization_id == organization_id,
                User.is_active.is_(True),
            )
        )

    async def add_member(self, db: AsyncSession, team_id: str, user_id: str, is_primary: bool):
        membership = await db.scalar(
            select(TeamMembership).where(
                TeamMembership.team_id == team_id, TeamMembership.user_id == user_id
            )
        )
        if is_primary:
            await db.execute(
                update(TeamMembership)
                .where(TeamMembership.user_id == user_id)
                .values(is_primary=False)
            )
        if membership:
            membership.is_primary = is_primary
        else:
            db.add(TeamMembership(team_id=team_id, user_id=user_id, is_primary=is_primary))

    async def remove_member(self, db: AsyncSession, team_id: str, user_id: str):
        await db.execute(
            delete(TeamMembership).where(
                TeamMembership.team_id == team_id, TeamMembership.user_id == user_id
            )
        )


team_repository = TeamRepository()
