from datetime import date, datetime

from fastapi import status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIException, ForbiddenError, NotFoundError
from app.models import Project, User
from app.repositories.project_repository import ProjectRepository
from app.schemas.project import ProjectCreate, ProjectUpdate
from app.services.auth_service import auth_service


def parse_project_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = date.fromisoformat(value)
            return datetime(parsed.year, parsed.month, parsed.day)
        except ValueError as error:
            raise APIException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                message="Project dates must be valid ISO dates.",
            ) from error


def project_to_dict(project: Project) -> dict:
    return {
        "id": project.id,
        "organization_id": project.organization_id,
        "name": project.name,
        "description": project.description,
        "status": project.status,
        "priority": project.priority,
        "owner_id": project.owner_id,
        "start_date": str(project.start_date) if project.start_date else None,
        "due_date": str(project.due_date) if project.due_date else None,
        "budget": float(project.budget) if project.budget is not None else None,
        "completion_percentage": project.completion_percentage,
        "created_at": str(project.created_at) if project.created_at else None,
        "updated_at": str(project.updated_at) if project.updated_at else None,
    }


class ProjectService:
    def __init__(self, repository: ProjectRepository | None = None) -> None:
        self.repository = repository or ProjectRepository()

    async def _commit(self, db: AsyncSession) -> None:
        try:
            await db.commit()
        except SQLAlchemyError as error:
            await db.rollback()
            raise APIException(status_code=400, message="Failed to save project.") from error

    async def list_projects(
        self, db: AsyncSession, current_user: User, **filters: object
    ) -> list[dict]:
        projects = await self.repository.list(
            db, organization_id=current_user.organization_id, **filters
        )
        return [project_to_dict(project) for project in projects]

    async def get_project(self, db: AsyncSession, current_user: User, project_id: str) -> dict:
        project = await self.repository.get(
            db, project_id=project_id, organization_id=current_user.organization_id
        )
        if not project:
            raise NotFoundError(message=f"Project '{project_id}' not found")
        return project_to_dict(project)

    async def create_project(
        self, db: AsyncSession, current_user: User, payload: ProjectCreate
    ) -> dict:
        data = payload.model_dump()
        await self._validate_owner(db, current_user, data.get("owner_id"))
        data.update(
            organization_id=current_user.organization_id,
            start_date=parse_project_datetime(data.pop("start_date")),
            due_date=parse_project_datetime(data.pop("due_date")),
        )
        project = await self.repository.create(db, data)
        await self._commit(db)
        await db.refresh(project)
        return project_to_dict(project)

    async def update_project(
        self, db: AsyncSession, current_user: User, project_id: str, payload: ProjectUpdate
    ) -> dict:
        project = await self.repository.get(
            db, project_id=project_id, organization_id=current_user.organization_id
        )
        if not project:
            raise NotFoundError(message=f"Project '{project_id}' not found")
        updates = payload.model_dump(exclude_unset=True)
        if updates.get("owner_id"):
            await self._validate_owner(db, current_user, updates["owner_id"])
        for field in ("start_date", "due_date"):
            if field in updates:
                updates[field] = parse_project_datetime(updates[field])
        await self.repository.update(db, project, updates)
        await self._commit(db)
        await db.refresh(project)
        return project_to_dict(project)

    async def delete_project(self, db: AsyncSession, current_user: User, project_id: str) -> dict:
        project = await self.repository.get(
            db, project_id=project_id, organization_id=current_user.organization_id
        )
        if not project:
            raise NotFoundError(message=f"Project '{project_id}' not found")
        await self.repository.delete(db, project)
        await self._commit(db)
        return {"message": "Project deleted successfully"}

    async def _validate_owner(
        self, db: AsyncSession, current_user: User, owner_id: str | None
    ) -> None:
        if not owner_id:
            return
        permissions = await auth_service.get_user_permissions(db, current_user)
        if "projects:assign" not in permissions and "all" not in permissions:
            raise ForbiddenError(message="Missing required permission: projects:assign")
        owner = await self.repository.get_user_in_organization(
            db, user_id=owner_id, organization_id=current_user.organization_id
        )
        if not owner:
            raise APIException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                message="Project owner must be an active user in the current organization.",
            )


project_service = ProjectService()
