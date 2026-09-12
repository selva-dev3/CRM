from datetime import date, datetime

from fastapi import status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIException, ForbiddenError, NotFoundError
from app.core.permissions import effective_organization_id
from app.models import Project, ProjectStakeholder, User
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
        "company_id": project.company_id,
        "contact_id": project.contact_id,
        "originating_deal_id": project.originating_deal_id,
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
            raise APIException(status_code=400, message="Failed to save project.") from error

    async def list_projects(
        self, db: AsyncSession, current_user: User, **filters: object
    ) -> list[dict]:
        from app.services.record_access_service import record_access_service

        access = await record_access_service.resolve(db, current_user, "projects")
        projects = await self.repository.list(
            db, organization_id=self.organization_id(current_user), access=access, **filters
        )
        return [project_to_dict(project) for project in projects]

    async def count_projects(
        self,
        db: AsyncSession,
        current_user: User,
        *,
        status: str | None = None,
        priority: str | None = None,
        search: str | None = None,
    ) -> int:
        from app.services.record_access_service import record_access_service

        access = await record_access_service.resolve(db, current_user, "projects")
        return await self.repository.count(
            db,
            organization_id=self.organization_id(current_user),
            status=status,
            priority=priority,
            search=search,
            access=access,
        )

    async def get_project(self, db: AsyncSession, current_user: User, project_id: str) -> dict:
        from app.services.record_access_service import record_access_service

        access = await record_access_service.resolve(db, current_user, "projects")
        project = await self.repository.get(
            db,
            project_id=project_id,
            organization_id=self.organization_id(current_user),
            access=access,
        )
        if not project:
            raise NotFoundError(message=f"Project '{project_id}' not found")
        return project_to_dict(project)

    async def create_project(
        self, db: AsyncSession, current_user: User, payload: ProjectCreate
    ) -> dict:
        data = payload.model_dump()
        await self._validate_owner(db, current_user, data.get("owner_id"))
        invalid = await self.repository.validate_related(
            db,
            organization_id=self.organization_id(current_user),
            company_id=data.get("company_id"),
            contact_id=data.get("contact_id"),
            originating_deal_id=data.get("originating_deal_id"),
        )
        if invalid:
            raise NotFoundError(message=f"Related {invalid} not found")
        data.update(
            organization_id=self.organization_id(current_user),
            created_by=current_user.id,
            start_date=parse_project_datetime(data.pop("start_date")),
            due_date=parse_project_datetime(data.pop("due_date")),
        )
        project = await self.repository.create(db, data)
        await db.flush()
        from app.services.workflow_service import workflow_service

        await workflow_service.emit(
            db,
            organization_id=project.organization_id,
            module="projects",
            trigger="record.created",
            entity_id=project.id,
            actor_id=current_user.id,
            payload={"status": project.status, "priority": project.priority},
        )
        await self._commit(db)
        await db.refresh(project)
        return project_to_dict(project)

    async def update_project(
        self, db: AsyncSession, current_user: User, project_id: str, payload: ProjectUpdate
    ) -> dict:
        from app.services.record_access_service import record_access_service

        access = await record_access_service.resolve(db, current_user, "projects")
        project = await self.repository.get(
            db,
            project_id=project_id,
            organization_id=self.organization_id(current_user),
            access=access,
        )
        if not project:
            raise NotFoundError(message=f"Project '{project_id}' not found")
        updates = payload.model_dump(exclude_unset=True)
        if updates.get("owner_id"):
            await self._validate_owner(db, current_user, updates["owner_id"])
        invalid = await self.repository.validate_related(
            db,
            organization_id=self.organization_id(current_user),
            company_id=updates.get("company_id"),
            contact_id=updates.get("contact_id"),
            originating_deal_id=updates.get("originating_deal_id"),
        )
        if invalid:
            raise NotFoundError(message=f"Related {invalid} not found")
        previous_status = project.status
        for field in ("start_date", "due_date"):
            if field in updates:
                updates[field] = parse_project_datetime(updates[field])
        await self.repository.update(db, project, updates)
        from app.services.workflow_service import workflow_service

        await workflow_service.emit(
            db,
            organization_id=project.organization_id,
            module="projects",
            trigger=(
                "record.status_changed" if previous_status != project.status else "record.updated"
            ),
            entity_id=project.id,
            actor_id=current_user.id,
            payload={
                "status": project.status,
                "priority": project.priority,
                "old_status": previous_status,
                "changed_fields": list(updates),
            },
        )
        await self._commit(db)
        await db.refresh(project)
        return project_to_dict(project)

    async def delete_project(self, db: AsyncSession, current_user: User, project_id: str) -> dict:
        from app.services.record_access_service import record_access_service

        access = await record_access_service.resolve(db, current_user, "projects")
        project = await self.repository.get(
            db,
            project_id=project_id,
            organization_id=self.organization_id(current_user),
            access=access,
        )
        if not project:
            raise NotFoundError(message=f"Project '{project_id}' not found")
        await self.repository.delete(db, project)
        await self._commit(db)
        return {"message": "Project deleted successfully"}

    async def list_stakeholders(self, db: AsyncSession, current_user: User, project_id: str):
        await self.get_project(db, current_user, project_id)
        return await self.repository.list_stakeholders(db, project_id)

    async def add_stakeholder(
        self, db: AsyncSession, current_user: User, project_id: str, contact_id: str, role: str
    ):
        await self.get_project(db, current_user, project_id)
        invalid = await self.repository.validate_related(
            db, organization_id=self.organization_id(current_user), contact_id=contact_id
        )
        if invalid:
            raise NotFoundError(message="Related contact not found")
        item = ProjectStakeholder(project_id=project_id, contact_id=contact_id, role=role)
        db.add(item)
        try:
            await self._commit(db)
            await db.refresh(item)
        except APIException as exc:
            raise APIException(
                status_code=409, message="Contact is already a project stakeholder"
            ) from exc
        return item

    async def remove_stakeholder(
        self, db: AsyncSession, current_user: User, project_id: str, stakeholder_id: str
    ):
        await self.get_project(db, current_user, project_id)
        item = await self.repository.get_stakeholder(db, project_id, stakeholder_id)
        if item:
            await db.delete(item)
            await self._commit(db)

    async def _validate_owner(
        self, db: AsyncSession, current_user: User, owner_id: str | None
    ) -> None:
        if not owner_id:
            return
        permissions = await auth_service.get_user_permissions(db, current_user)
        if "projects:assign" not in permissions:
            raise ForbiddenError(message="Missing required permission: projects:assign")
        owner = await self.repository.get_user_in_organization(
            db, user_id=owner_id, organization_id=self.organization_id(current_user)
        )
        if not owner:
            raise APIException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                message="Project owner must be an active user in the current organization.",
            )


project_service = ProjectService()
