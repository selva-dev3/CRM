from datetime import UTC, date, datetime
from typing import Any

from fastapi import status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIException, ForbiddenError, NotFoundError
from app.core.permissions import effective_organization_id
from app.models import Project, ProjectMember, ProjectStakeholder, User
from app.repositories.project_repository import ProjectRepository
from app.schemas.project import ProjectCreate, ProjectUpdate
from app.services.auth_service import auth_service


def parse_project_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    except ValueError:
        try:
            parsed_date = date.fromisoformat(value)
            return datetime(parsed_date.year, parsed_date.month, parsed_date.day, tzinfo=UTC)
        except ValueError as error:
            raise APIException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
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
        self, db: AsyncSession, current_user: User, **filters: Any
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
        data.pop("completion_percentage", None)
        await self._validate_owner(db, current_user, data.get("owner_id"))
        from app.services.crm_relationship_service import (
            resolve_crm_record_access,
            validate_crm_relationships,
        )

        await validate_crm_relationships(
            db,
            organization_id=self.organization_id(current_user),
            company_id=data.get("company_id"),
            contact_id=data.get("contact_id"),
            deal_id=data.get("originating_deal_id"),
            access_by_module=await resolve_crm_record_access(db, current_user),
        )
        data.update(
            organization_id=self.organization_id(current_user),
            created_by=current_user.id,
            start_date=parse_project_datetime(data.pop("start_date")),
            due_date=parse_project_datetime(data.pop("due_date")),
        )
        self._validate_dates(data["start_date"], data["due_date"])
        if data.get("status") == "Completed":
            raise APIException(
                status_code=409,
                message="A new project cannot be completed before its work is created.",
            )
        project = await self.repository.create(db, data)
        await db.flush()
        member_user_id = project.owner_id or current_user.id
        db.add(
            ProjectMember(
                project_id=project.id,
                user_id=member_user_id,
                role="Owner" if project.owner_id else "Manager",
                added_by=current_user.id,
            )
        )
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
        updates.pop("completion_percentage", None)
        if updates.get("owner_id"):
            await self._validate_owner(db, current_user, updates["owner_id"])
        from app.services.crm_relationship_service import (
            resolve_crm_record_access,
            validate_crm_relationships,
        )

        await validate_crm_relationships(
            db,
            organization_id=self.organization_id(current_user),
            company_id=updates.get("company_id", project.company_id),
            contact_id=updates.get("contact_id", project.contact_id),
            deal_id=updates.get("originating_deal_id", project.originating_deal_id),
            access_by_module=await resolve_crm_record_access(db, current_user),
        )
        previous_status = project.status
        for field in ("start_date", "due_date"):
            if field in updates:
                updates[field] = parse_project_datetime(updates[field])
        self._validate_dates(
            updates.get("start_date", project.start_date),
            updates.get("due_date", project.due_date),
        )
        await self.repository.recalculate_progress(db, project)
        if updates.get("status") == "Completed" and project.completion_percentage != 100:
            raise APIException(
                status_code=409,
                message="Complete every project task and milestone before completing the project.",
            )
        if updates.get("owner_id") and updates["owner_id"] != project.owner_id:
            if project.owner_id:
                previous_owner = await self.repository.get_member(db, project.id, project.owner_id)
                if previous_owner and previous_owner.role == "Owner":
                    previous_owner.role = "Member"
            member = await self.repository.get_member(db, project.id, updates["owner_id"])
            if member:
                member.role = "Owner"
            else:
                db.add(
                    ProjectMember(
                        project_id=project.id,
                        user_id=updates["owner_id"],
                        role="Owner",
                        added_by=current_user.id,
                    )
                )
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

    async def list_members(self, db: AsyncSession, current_user: User, project_id: str):
        await self.get_project(db, current_user, project_id)
        return [
            self._member_to_dict(row) for row in await self.repository.list_members(db, project_id)
        ]

    async def add_member(
        self,
        db: AsyncSession,
        current_user: User,
        project_id: str,
        user_id: str,
        role: str,
    ):
        await self.get_project(db, current_user, project_id)
        await self._require_assign_permission(db, current_user)
        user = await self.repository.get_user_in_organization(
            db, user_id=user_id, organization_id=self.organization_id(current_user)
        )
        if not user:
            raise NotFoundError(
                message="Project member must be an active user in this organization"
            )
        existing = await self.repository.get_member(db, project_id, user_id)
        if existing:
            existing.role = role.strip()
            member = existing
        else:
            member = ProjectMember(
                project_id=project_id,
                user_id=user_id,
                role=role.strip(),
                added_by=current_user.id,
            )
            db.add(member)
        await self._commit(db)
        await db.refresh(member)
        return self._member_to_dict(member)

    async def remove_member(
        self, db: AsyncSession, current_user: User, project_id: str, user_id: str
    ) -> None:
        project = await self.repository.get(
            db,
            project_id=project_id,
            organization_id=self.organization_id(current_user),
            access=await self._project_access(db, current_user),
        )
        if not project:
            raise NotFoundError(message=f"Project '{project_id}' not found")
        await self._require_assign_permission(db, current_user)
        if project.owner_id == user_id:
            raise APIException(status_code=409, message="The project owner cannot be removed")
        member = await self.repository.get_member(db, project_id, user_id)
        if member:
            await db.delete(member)
            await self._commit(db)

    @staticmethod
    def _member_to_dict(member: ProjectMember) -> dict:
        return {
            "id": member.id,
            "project_id": member.project_id,
            "user_id": member.user_id,
            "role": member.role,
            "added_by": member.added_by,
            "created_at": str(member.created_at) if member.created_at else None,
        }

    @staticmethod
    def _validate_dates(start_date: datetime | None, due_date: datetime | None) -> None:
        if start_date and due_date and due_date < start_date:
            raise APIException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                message="Project due date must not be before its start date.",
            )

    @staticmethod
    async def _project_access(db: AsyncSession, current_user: User):
        from app.services.record_access_service import record_access_service

        return await record_access_service.resolve(db, current_user, "projects")

    @staticmethod
    async def _require_assign_permission(db: AsyncSession, current_user: User) -> None:
        permissions = await auth_service.get_user_permissions(db, current_user)
        if "projects:assign" not in permissions:
            raise ForbiddenError(message="Missing required permission: projects:assign")

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
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                message="Project owner must be an active user in the current organization.",
            )


project_service = ProjectService()
