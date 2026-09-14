from datetime import UTC, datetime

from fastapi import status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIException, ForbiddenError, NotFoundError
from app.core.permissions import effective_organization_id
from app.models import ProjectMilestone, User
from app.repositories.milestone_repository import MilestoneRepository, milestone_repository
from app.repositories.project_repository import ProjectRepository
from app.schemas.milestone import MilestoneCreate, MilestoneUpdate
from app.services.record_access_service import record_access_service
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
    def __init__(
        self,
        repository: MilestoneRepository | None = None,
        project_repository: ProjectRepository | None = None,
    ) -> None:
        self.repository = repository or milestone_repository
        self.project_repository = project_repository or ProjectRepository()

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
        access = await record_access_service.resolve(db, current_user, "projects")
        rows = await self.repository.list(
            db, organization_id=self.organization_id(current_user), access=access, **filters
        )
        return [milestone_to_dict(row) for row in rows]

    async def count(self, db: AsyncSession, current_user: User, **filters) -> int:
        access = await record_access_service.resolve(db, current_user, "projects")
        return await self.repository.count(
            db, organization_id=self.organization_id(current_user), access=access, **filters
        )

    async def create(self, db: AsyncSession, current_user: User, payload: MilestoneCreate) -> dict:
        organization_id = self.organization_id(current_user)
        access = await record_access_service.resolve(db, current_user, "projects")
        project = await self.repository.get_project(
            db, project_id=payload.project_id, organization_id=organization_id, access=access
        )
        if not project:
            raise NotFoundError(message="Related project not found")
        due_date = parse_datetime(payload.due_date)
        if due_date and (
            (project.start_date and due_date < project.start_date)
            or (project.due_date and due_date > project.due_date)
        ):
            raise APIException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                message="Milestone due date must fall within the project date range.",
            )
        milestone = ProjectMilestone(
            organization_id=organization_id,
            project_id=payload.project_id,
            name=payload.name.strip(),
            description=payload.description.strip() if payload.description else None,
            status=payload.status,
            due_date=due_date,
            completed_at=datetime.now(UTC) if payload.status == "Completed" else None,
        )
        db.add(milestone)
        await db.flush()
        await self.project_repository.recalculate_progress(db, project)
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
        access = await record_access_service.resolve(db, current_user, "projects")
        milestone = await self.repository.get(
            db,
            milestone_id=milestone_id,
            organization_id=self.organization_id(current_user),
            access=access,
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
            project = await self.repository.get_project(
                db,
                project_id=milestone.project_id,
                organization_id=self.organization_id(current_user),
                access=access,
            )
            due_date = updates["due_date"]
            if project and due_date and (
                (project.start_date and due_date < project.start_date)
                or (project.due_date and due_date > project.due_date)
            ):
                raise APIException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    message="Milestone due date must fall within the project date range.",
                )
        if updates.get("status") == "Completed" and milestone.status != "Completed":
            updates["completed_at"] = datetime.now(UTC)
        elif "status" in updates and updates["status"] != "Completed":
            updates["completed_at"] = None
        for field, value in updates.items():
            setattr(milestone, field, value)
        await db.flush()
        project = await self.repository.get_project(
            db,
            project_id=milestone.project_id,
            organization_id=self.organization_id(current_user),
            access=access,
        )
        if project:
            await self.project_repository.recalculate_progress(db, project)
        await self._commit(db)
        await db.refresh(milestone)
        return milestone_to_dict(milestone)

    async def delete(self, db: AsyncSession, current_user: User, milestone_id: str) -> dict:
        access = await record_access_service.resolve(db, current_user, "projects")
        milestone = await self.repository.get(
            db,
            milestone_id=milestone_id,
            organization_id=self.organization_id(current_user),
            access=access,
        )
        if not milestone:
            raise NotFoundError(message="Milestone not found")
        project = await self.repository.get_project(
            db,
            project_id=milestone.project_id,
            organization_id=self.organization_id(current_user),
            access=access,
        )
        await db.delete(milestone)
        await db.flush()
        if project:
            await self.project_repository.recalculate_progress(db, project)
        await self._commit(db)
        return {"message": "Milestone deleted", "status": "success"}


milestone_service = MilestoneService()
