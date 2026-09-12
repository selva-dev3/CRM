from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError
from app.core.permissions import effective_organization_id
from app.models import Team, User
from app.repositories.team_repository import team_repository
from app.schemas.team import TeamCreate, TeamMemberUpdate, TeamUpdate


class TeamService:
    @staticmethod
    def _org(user: User) -> str:
        organization_id = effective_organization_id(user)
        if not organization_id:
            raise NotFoundError(message="Organization not found")
        return organization_id

    @staticmethod
    def _serialize(team: Team, count: int = 0) -> dict:
        return {
            "id": team.id,
            "name": team.name,
            "description": team.description,
            "manager_id": team.manager_id,
            "is_active": team.is_active,
            "member_count": count,
            "created_at": team.created_at,
        }

    async def list(self, db: AsyncSession, user: User, search: str | None, page: int, limit: int):
        rows, total, counts = await team_repository.list(
            db, self._org(user), search=search, offset=(page - 1) * limit, limit=limit
        )
        return [self._serialize(row, counts.get(row.id, 0)) for row in rows], total

    async def detail(self, db: AsyncSession, user: User, team_id: str):
        team = await team_repository.get(db, team_id, self._org(user))
        if not team:
            raise NotFoundError(message="Team not found")
        members = await team_repository.members(db, team.id)
        return self._serialize(team, len(members)) | {
            "members": [
                {
                    "user_id": member.id,
                    "name": member.name,
                    "email": member.email,
                    "is_primary": primary,
                }
                for member, primary in members
            ]
        }

    async def create(self, db: AsyncSession, user: User, payload: TeamCreate):
        org = self._org(user)
        if payload.manager_id and not await team_repository.user(db, payload.manager_id, org):
            raise NotFoundError(message="Manager not found")
        team = Team(organization_id=org, **payload.model_dump())
        db.add(team)
        try:
            await db.commit()
            await db.refresh(team)
        except IntegrityError as exc:
            await db.rollback()
            raise ConflictError(message="A team with this name already exists") from exc
        return self._serialize(team)

    async def update(self, db: AsyncSession, user: User, team_id: str, payload: TeamUpdate):
        team = await team_repository.get(db, team_id, self._org(user))
        if not team:
            raise NotFoundError(message="Team not found")
        data = payload.model_dump(exclude_unset=True)
        if data.get("manager_id") and not await team_repository.user(
            db, data["manager_id"], self._org(user)
        ):
            raise NotFoundError(message="Manager not found")
        for key, value in data.items():
            setattr(team, key, value)
        try:
            await db.commit()
            await db.refresh(team)
        except IntegrityError as exc:
            await db.rollback()
            raise ConflictError(message="A team with this name already exists") from exc
        return self._serialize(team, len(await team_repository.members(db, team.id)))

    async def delete(self, db: AsyncSession, user: User, team_id: str):
        team = await team_repository.get(db, team_id, self._org(user))
        if not team:
            return
        await db.delete(team)
        await db.commit()

    async def add_member(
        self, db: AsyncSession, user: User, team_id: str, payload: TeamMemberUpdate
    ):
        org = self._org(user)
        if not await team_repository.get(db, team_id, org):
            raise NotFoundError(message="Team not found")
        if not await team_repository.user(db, payload.user_id, org):
            raise NotFoundError(message="User not found")
        await team_repository.add_member(db, team_id, payload.user_id, payload.is_primary)
        await db.commit()
        return await self.detail(db, user, team_id)

    async def remove_member(self, db: AsyncSession, user: User, team_id: str, user_id: str):
        if not await team_repository.get(db, team_id, self._org(user)):
            raise NotFoundError(message="Team not found")
        await team_repository.remove_member(db, team_id, user_id)
        await db.commit()


team_service = TeamService()
