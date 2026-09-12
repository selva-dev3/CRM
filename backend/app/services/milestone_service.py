from datetime import UTC, datetime

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIException, ForbiddenError, NotFoundError
from app.core.permissions import effective_organization_id
from app.models import ProjectMilestone, User
from app.repositories.milestone_repository import MilestoneRepository, milestone_repository
from app.schemas.milestone import MilestoneCreate, MilestoneUpdate
from app.services.task_service import parse_datetime


def milestone_to_dict(milestone: ProjectMilestone) -> dict:
    return {
        "id": milestone.id,
        "project_id": milestone.project_id,
        "name": milestone.name,
        "description": milestone.description,
        "status": milestone.status,
        "due_date": milestone.due_date.isoformat() if milestone.due_date else None,
        "completed_at": milestone.completed_at.isoformat() if milestone.completed_at else None,
        "created_at": milestone.created_at.isoformat() if milestone.created_at else None,
        "updated_at": milestone.updated_at.isoformat() if milestone.updated_at else None,
    }


class MilestoneService:
    def __init__(self, repository: MilestoneRepository | None = None) -> None:
        self.repository = repository or milestone_repository

    @staticmethod
    def organization_id(current_user: User) -> str:
        organization_id = effective_organization_id(current_user)
        if not organization_id:
            raise ForbiddenError(message="Authenticated organization context is required")
        return organization_id

    async def _commit(self, db: AsyncSession) -> None:
        try:
            await db.commit()
        except SQLAlchemyError as error:
            await db.rollback()
            raise APIException(message="Failed to save milestone", status_code=400) from error

    async def list(self, db: AsyncSession, current_user: User, **filters) -> list[dict]:
        rows = await self.repository.list(
            db, organization_id=self.organization_id(current_user), **filters
        )
        return [milestone_to_dict(row) for row in rows]

    async def count(self, db: AsyncSession, current_user: User, **filters) -> int:
        return await self.repository.count(
            db, organization_id=self.organization_id(current_user), **filters
        )

    async def create(self, db: AsyncSession, current_user: User, payload: MilestoneCreate) -> dict:
        organization_id = self.organization_id(current_user)
        if not await self.repository.get_project(
            db, project_id=payload.project_id, organization_id=organization_id
        ):
            raise NotFoundError(message="Related project not found")
        milestone = ProjectMilestone(
            organization_id=organization_id,
            project_id=payload.project_id,
            name=payload.name.strip(),
            description=payload.description.strip() if payload.description else None,
            status=payload.status,
            due_date=parse_datetime(payload.due_date),
            completed_at=datetime.now(UTC) if payload.status == "Completed" else None,
        )
        db.add(milestone)
        await self._commit(db)
        await db.refresh(milestone)
        return milestone_to_dict(milestone)

    async def update(
        self,
        db: AsyncSession,
        current_user: User,
        milestone_id: str,
        payload: MilestoneUpdate,
    ) -> dict:
        milestone = await self.repository.get(
            db,
            milestone_id=milestone_id,
            organization_id=self.organization_id(current_user),
        )
        if not milestone:
            raise NotFoundError(message="Milestone not found")
        updates = payload.model_dump(exclude_unset=True)
        if "name" in updates:
            updates["name"] = updates["name"].strip()
        if "description" in updates and updates["description"]:
            updates["description"] = updates["description"].strip()
        if "due_date" in updates:
            updates["due_date"] = parse_datetime(updates["due_date"])
        if updates.get("status") == "Completed" and milestone.status != "Completed":
            updates["completed_at"] = datetime.now(UTC)
        elif "status" in updates and updates["status"] != "Completed":
            updates["completed_at"] = None
        for field, value in updates.items():
            setattr(milestone, field, value)
        await self._commit(db)
        await db.refresh(milestone)
        return milestone_to_dict(milestone)

    async def delete(self, db: AsyncSession, current_user: User, milestone_id: str) -> dict:
        milestone = await self.repository.get(
            db,
            milestone_id=milestone_id,
            organization_id=self.organization_id(current_user),
        )
        if not milestone:
            raise NotFoundError(message="Milestone not found")
        await db.delete(milestone)
        await self._commit(db)
        return {"message": "Milestone deleted", "status": "success"}


milestone_service = MilestoneService()
