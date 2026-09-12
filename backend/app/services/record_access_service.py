from sqlalchemy.ext.asyncio import AsyncSession

from app.core.record_access import RecordAccessContext
from app.models import User
from app.repositories.record_access_repository import record_access_repository


class RecordAccessService:
    async def resolve(self, db: AsyncSession, user: User, module: str) -> RecordAccessContext:
        role_id = await record_access_repository.role_id_for_user(db, user.id)
        scope = "all"
        if role_id:
            scope = await record_access_repository.scope_for_role(db, role_id, module) or "all"
        team_ids = await record_access_repository.team_ids_for_user(db, user.id)
        team_users = await record_access_repository.user_ids_for_teams(db, team_ids)
        return RecordAccessContext(
            scope=scope,
            user_id=user.id,
            team_ids=team_ids,
            team_user_ids=team_users,
        )

    @staticmethod
    def allows(
        context: RecordAccessContext,
        *,
        assigned_to: str | None,
        created_by: str | None = None,
        team_id: str | None = None,
    ) -> bool:
        if context.scope == "all":
            return True
        if context.scope == "none":
            return False
        if context.scope == "own":
            return created_by == context.user_id
        if context.scope == "assigned":
            return assigned_to == context.user_id
        if context.scope == "team":
            return team_id in context.team_ids or assigned_to in context.team_user_ids
        return False


record_access_service = RecordAccessService()
