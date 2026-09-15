from datetime import UTC, date, datetime

from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.concurrency import ensure_fresh_record
from app.core.errors import APIException, ForbiddenError, NotFoundError
from app.models import User
from app.models.task import Task
from app.repositories.project_repository import ProjectRepository
from app.repositories.task_repository import TaskRepository
from app.schemas.crm_schemas import TaskCreate, TaskUpdate
from app.services.auth_service import api_key_scope_allows, auth_service
from app.services.notification_service import notification_service
from app.services.org_service import organization_service


def parse_datetime(val: str | None) -> datetime | None:
    if not val or not str(val).strip():
        return None
    val_str = str(val).strip()
    try:
        parsed = datetime.fromisoformat(val_str.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    except ValueError:
        try:
            d = date.fromisoformat(val_str)
            return datetime(d.year, d.month, d.day, tzinfo=UTC)
        except ValueError:
            return None


def task_to_dict(task: Task) -> dict:
    return {
        "id": task.id,
        "title": task.title,
        "description": task.description,
        "priority": task.priority,
        "due_date": str(task.due_date) if task.due_date else None,
        "status": task.status,
        "assigned_to": task.assigned_to,
        "created_by": task.created_by,
        "project_id": getattr(task, "project_id", None),
        "lead_id": task.lead_id,
        "contact_id": task.contact_id,
        "company_id": task.company_id,
        "deal_id": task.deal_id,
        "ticket_id": task.ticket_id,
        "created_at": str(task.created_at) if task.created_at else None,
        "updated_at": str(task.updated_at) if task.updated_at else None,
    }


class TaskService:
    """Business logic for the Task domain."""

    def __init__(
        self,
        repository: TaskRepository | None = None,
        project_repository: ProjectRepository | None = None,
    ) -> None:
        self.repository = repository or TaskRepository()
        self.project_repository = project_repository or ProjectRepository()

    @staticmethod
    async def _access(db: AsyncSession, current_user: User | None):
        if not current_user:
            return None
        from app.services.record_access_service import record_access_service

        return await record_access_service.resolve(db, current_user, "tasks")

    @classmethod
    async def _access_kwargs(cls, db: AsyncSession, current_user: User | None) -> dict:
        access = await cls._access(db, current_user)
        return {"access": access} if access is not None else {}

    async def _validate_project(
        self,
        db: AsyncSession,
        project_id: str | None,
        organization_id: str,
        current_user: User | None,
    ) -> str | None:
        if not project_id or project_id in {"null", "None"}:
            return None
        from app.services.record_access_service import record_access_service

        project_access = (
            await record_access_service.resolve(db, current_user, "projects")
            if current_user
            else None
        )
        project = await self.project_repository.get(
            db,
            project_id=project_id,
            organization_id=organization_id,
            **({"access": project_access} if project_access is not None else {}),
        )
        if not project:
            raise NotFoundError(message=f"Project '{project_id}' not found")
        return project.id

    async def _commit(self, db: AsyncSession, error_message: str) -> None:
        try:
            await db.commit()
        except Exception as e:
            await db.rollback()
            raise APIException(
                status_code=status.HTTP_400_BAD_REQUEST, message=error_message
            ) from e

    async def _recalculate_project(
        self, db: AsyncSession, project_id: str | None, organization_id: str
    ) -> None:
        if not project_id:
            return
        project = await self.project_repository.get(
            db, project_id=project_id, organization_id=organization_id
        )
        if project:
            await self.project_repository.recalculate_progress(db, project)

    async def _validate_project_assignment(
        self, db: AsyncSession, project_id: str | None, assigned_to: str | None
    ) -> None:
        if (
            project_id
            and assigned_to
            and not await self.project_repository.get_member(db, project_id, assigned_to)
        ):
            raise APIException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                message="A project task can only be assigned to a project member.",
            )

    async def _validate_project_due_date(
        self,
        db: AsyncSession,
        project_id: str | None,
        organization_id: str,
        due_date: datetime | None,
    ) -> None:
        if not project_id or not due_date:
            return
        project = await self.project_repository.get(
            db, project_id=project_id, organization_id=organization_id
        )
        if project and (
            (project.start_date and due_date < project.start_date)
            or (project.due_date and due_date > project.due_date)
        ):
            raise APIException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                message="Project task due date must fall within the project date range.",
            )

    @staticmethod
    async def _require_permission(db: AsyncSession, current_user: User, permission: str) -> None:
        permissions = set(await auth_service.get_user_permissions(db, current_user))
        if permission not in permissions or not api_key_scope_allows(current_user, permission):
            raise ForbiddenError(message=f"Missing required permission: {permission}")

    async def _resolve_user_id(
        self,
        db: AsyncSession,
        *,
        assigned_input: str | None,
        organization_id: str,
        default_user_id: str | None,
    ) -> str:
        if assigned_input and str(assigned_input).strip():
            value = str(assigned_input).strip()
            user = await self.repository.get_user_by_id_name_email(
                db, value=value, organization_id=organization_id
            )
            if user:
                return user.id
            raise NotFoundError(message=f"User '{value}' not found")
        if default_user_id is None:
            raise APIException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                message="Task assignee is required.",
            )
        return default_user_id

    async def list_tasks(
        self,
        db: AsyncSession,
        *,
        page: int,
        limit: int,
        organization_id: str,
        status: str | None = None,
        priority: str | None = None,
        search: str | None = None,
        lead_id: str | None = None,
        contact_id: str | None = None,
        company_id: str | None = None,
        deal_id: str | None = None,
        project_id: str | None = None,
        ticket_id: str | None = None,
        project_linked: bool = False,
        current_user: User | None = None,
    ) -> list[dict]:
        access = await self._access(db, current_user)
        tasks = await self.repository.list(
            db,
            page=page,
            limit=limit,
            organization_id=organization_id,
            status=status,
            priority=priority,
            search=search,
            lead_id=lead_id,
            contact_id=contact_id,
            company_id=company_id,
            deal_id=deal_id,
            project_id=project_id,
            ticket_id=ticket_id,
            project_linked=project_linked,
            **({"access": access} if access is not None else {}),
        )
        return [task_to_dict(t) for t in tasks]

    async def count_tasks(
        self,
        db: AsyncSession,
        *,
        organization_id: str,
        status: str | None = None,
        priority: str | None = None,
        search: str | None = None,
        lead_id: str | None = None,
        contact_id: str | None = None,
        company_id: str | None = None,
        deal_id: str | None = None,
        project_id: str | None = None,
        ticket_id: str | None = None,
        project_linked: bool = False,
        current_user: User | None = None,
    ) -> int:
        access = await self._access(db, current_user)
        return await self.repository.count(
            db,
            organization_id=organization_id,
            status=status,
            priority=priority,
            search=search,
            lead_id=lead_id,
            contact_id=contact_id,
            company_id=company_id,
            deal_id=deal_id,
            project_id=project_id,
            ticket_id=ticket_id,
            project_linked=project_linked,
            **({"access": access} if access is not None else {}),
        )

    async def get_task(
        self,
        db: AsyncSession,
        task_id: str,
        organization_id: str,
        current_user: User | None = None,
    ) -> dict:
        task = await self.repository.get_by_id(
            db,
            task_id=task_id,
            organization_id=organization_id,
            **(await self._access_kwargs(db, current_user)),
        )
        if not task:
            raise NotFoundError(message=f"Task '{task_id}' not found")
        return task_to_dict(task)

    async def create_task(
        self, db: AsyncSession, payload: TaskCreate, current_user: User | None = None
    ) -> dict:
        org_id = await organization_service.resolve_valid_org_id(db, current_user)
        if current_user is None:
            raise APIException(
                status_code=status.HTTP_401_UNAUTHORIZED, message="Authentication required"
            )
        due_dt = parse_datetime(payload.due_date)
        if payload.due_date and due_dt is None:
            raise APIException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                message="Invalid due_date. Use an ISO date or datetime.",
                fields={"due_date": "Must be a valid ISO date or datetime."},
            )
        assigned_user = await self._resolve_user_id(
            db,
            assigned_input=payload.assigned_to,
            organization_id=org_id,
            default_user_id=current_user.id,
        )
        if payload.assigned_to and assigned_user != current_user.id:
            await self._require_permission(db, current_user, "tasks:assign")
        project_id = await self._validate_project(db, payload.project_id, org_id, current_user)
        await self._validate_project_assignment(db, project_id, assigned_user)
        await self._validate_project_due_date(db, project_id, org_id, due_dt)
        ticket_id = await self.repository.validate_ticket(db, payload.ticket_id, org_id)
        from app.services.crm_relationship_service import (
            resolve_crm_record_access,
            validate_crm_relationships,
        )

        relationships = await validate_crm_relationships(
            db,
            organization_id=org_id,
            lead_id=payload.lead_id,
            contact_id=payload.contact_id,
            company_id=payload.company_id,
            deal_id=payload.deal_id,
            access_by_module=await resolve_crm_record_access(db, current_user),
        )
        data = {
            "organization_id": org_id,
            "title": payload.title,
            "description": payload.description,
            "priority": payload.priority or "Medium",
            "status": payload.status or "Pending",
            "due_date": due_dt,
            "assigned_to": assigned_user,
            "created_by": current_user.id,
            "project_id": project_id,
            "ticket_id": ticket_id,
            **relationships,
        }
        task = await self.repository.create(db, data=data)
        await db.flush()
        from app.services.workflow_service import workflow_service

        await workflow_service.emit(
            db,
            organization_id=task.organization_id,
            module="tasks",
            trigger="record.created",
            entity_id=task.id,
            actor_id=current_user.id,
            payload={"status": task.status, "priority": task.priority},
        )
        await self._recalculate_project(db, task.project_id, task.organization_id)
        await self._commit(db, "Failed to create task")
        await db.refresh(task)
        await notification_service.notify(
            db,
            event_name="task.created",
            organization_id=task.organization_id,
            actor_user_id=current_user.id if current_user else None,
            entity_type="task",
            entity_id=task.id,
            assigned_to=task.assigned_to,
            data={
                "id": task.id,
                "title": task.title,
                "priority": task.priority,
                "status": task.status,
                "due_date": str(task.due_date) if task.due_date else None,
                "assigned_to": task.assigned_to,
            },
        )
        return task_to_dict(task)

    async def get_overdue_tasks(
        self, db: AsyncSession, organization_id: str, current_user: User | None = None
    ) -> list[dict]:
        tasks = await self.repository.list_pending(
            db,
            organization_id=organization_id,
            **(await self._access_kwargs(db, current_user)),
        )
        today = datetime.now().astimezone().date()
        return [task_to_dict(t) for t in tasks if t.due_date and t.due_date.date() < today]

    async def get_today_tasks(
        self, db: AsyncSession, organization_id: str, current_user: User | None = None
    ) -> list[dict]:
        tasks = await self.repository.list_pending(
            db,
            organization_id=organization_id,
            **(await self._access_kwargs(db, current_user)),
        )
        today = datetime.now().astimezone().date()
        return [task_to_dict(t) for t in tasks if t.due_date and t.due_date.date() == today]

    async def get_board_view(
        self, db: AsyncSession, organization_id: str, current_user: User | None = None
    ) -> dict:
        tasks = await self.repository.list_all(
            db,
            organization_id=organization_id,
            **(await self._access_kwargs(db, current_user)),
        )
        board: dict[str, list[dict]] = {}
        for task in tasks:
            board.setdefault(task.status, []).append(
                {
                    "id": task.id,
                    "title": task.title,
                    "priority": task.priority,
                    "due_date": str(task.due_date) if task.due_date else None,
                    "assigned_to": task.assigned_to,
                }
            )
        return board

    async def update_task(
        self,
        db: AsyncSession,
        task_id: str,
        payload: TaskUpdate,
        organization_id: str,
        *,
        actor_id: str | None = None,
        current_user: User | None = None,
    ) -> dict:
        task = await self.repository.get_by_id(
            db,
            task_id=task_id,
            organization_id=organization_id,
            **(await self._access_kwargs(db, current_user)),
        )
        if not task:
            raise NotFoundError(message=f"Task '{task_id}' not found")
        await ensure_fresh_record(db, task, payload.expected_updated_at, "task")

        prev_priority = task.priority
        prev_status = task.status
        previous_project_id = task.project_id
        updates = payload.model_dump(exclude_unset=True)
        updates.pop("expected_updated_at", None)
        if "project_id" in updates:
            target_project_id = await self._validate_project(
                db, updates["project_id"], task.organization_id, current_user
            )
            if target_project_id != previous_project_id:
                await self.repository.lock_dependency_projects(
                    db,
                    project_ids={
                        project_id
                        for project_id in (previous_project_id, target_project_id)
                        if project_id
                    },
                    organization_id=task.organization_id,
                )
                await db.refresh(task)
                if task.project_id != previous_project_id:
                    raise APIException(
                        status_code=status.HTTP_409_CONFLICT,
                        message="Task project changed concurrently. Reload and try again.",
                    )
                if await self.repository.has_dependencies(db, task.id):
                    raise APIException(
                        status_code=status.HTTP_409_CONFLICT,
                        message=(
                            "Remove task dependencies before moving the task to another project."
                        ),
                    )
            updates["project_id"] = target_project_id
        if "title" in updates and updates["title"] is not None:
            task.title = updates["title"]
        if "description" in updates:
            task.description = updates["description"]
        if "due_date" in updates:
            task.due_date = parse_datetime(updates["due_date"])
        if "assigned_to" in updates:
            assigned_user = await self._resolve_user_id(
                db,
                assigned_input=updates["assigned_to"],
                organization_id=task.organization_id,
                default_user_id=task.assigned_to,
            )
            if assigned_user != task.assigned_to:
                if current_user is None:
                    raise ForbiddenError(message="Authentication required to reassign a task")
                if assigned_user != current_user.id:
                    await self._require_permission(db, current_user, "tasks:assign")
                task.assigned_to = assigned_user
        if "status" in updates:
            task.status = updates["status"]
        if "priority" in updates:
            task.priority = updates["priority"]
        if "project_id" in updates:
            task.project_id = updates["project_id"]
        await self._validate_project_assignment(db, task.project_id, task.assigned_to)
        await self._validate_project_due_date(
            db, task.project_id, task.organization_id, task.due_date
        )
        if "ticket_id" in updates:
            task.ticket_id = await self.repository.validate_ticket(
                db, updates["ticket_id"], task.organization_id
            )
        relationship_fields = {"lead_id", "contact_id", "company_id", "deal_id"}
        if relationship_fields & updates.keys():
            from app.services.crm_relationship_service import (
                resolve_crm_record_access,
                validate_crm_relationships,
            )

            merged = {
                field: updates.get(field, getattr(task, field)) for field in relationship_fields
            }
            await validate_crm_relationships(
                db,
                organization_id=task.organization_id,
                access_by_module=(
                    await resolve_crm_record_access(db, current_user) if current_user else None
                ),
                **merged,
            )
            for field in relationship_fields & updates.keys():
                setattr(task, field, updates[field])

        from app.services.workflow_service import workflow_service

        await workflow_service.emit(
            db,
            organization_id=task.organization_id,
            module="tasks",
            trigger="record.status_changed" if prev_status != task.status else "record.updated",
            entity_id=task.id,
            actor_id=actor_id,
            payload={
                "status": task.status,
                "priority": task.priority,
                "old_status": prev_status,
                "changed_fields": list(updates),
            },
        )

        if task.status == "Completed":
            incomplete = await self.repository.incomplete_dependency_ids(db, task.id)
            if incomplete:
                raise APIException(
                    status_code=409,
                    message="Complete all task dependencies before completing this task.",
                )
        await db.flush()
        await self._recalculate_project(db, previous_project_id, task.organization_id)
        if task.project_id != previous_project_id:
            await self._recalculate_project(db, task.project_id, task.organization_id)

        await self._commit(db, "Failed to update task")
        await db.refresh(task)
        if task.priority != prev_priority:
            await notification_service.notify(
                db,
                event_name="task.priority_changed",
                organization_id=task.organization_id,
                entity_type="task",
                entity_id=task.id,
                assigned_to=task.assigned_to,
                data={
                    "id": task.id,
                    "title": task.title,
                    "old_priority": prev_priority,
                    "priority": task.priority,
                },
            )
        return task_to_dict(task)

    async def delete_task(
        self,
        db: AsyncSession,
        task_id: str,
        organization_id: str,
        current_user: User | None = None,
    ) -> dict:
        task = await self.repository.get_by_id(
            db,
            task_id=task_id,
            organization_id=organization_id,
            **(await self._access_kwargs(db, current_user)),
        )
        if not task:
            raise NotFoundError(message=f"Task '{task_id}' not found")
        project_id = task.project_id
        await self.repository.delete(db, task)
        await db.flush()
        await self._recalculate_project(db, project_id, organization_id)
        await self._commit(db, "Failed to delete task")
        return {"message": f"Task {task_id} deleted successfully", "status": "success"}

    async def bulk_delete(
        self,
        db: AsyncSession,
        ids: list[str],
        organization_id: str,
        current_user: User | None = None,
    ) -> dict:
        tasks = await self.repository.list_by_ids(
            db,
            ids=ids,
            organization_id=organization_id,
            **(await self._access_kwargs(db, current_user)),
        )
        project_ids = {task.project_id for task in tasks if task.project_id}
        for task in tasks:
            await self.repository.delete(db, task)
        await db.flush()
        for project_id in project_ids:
            await self._recalculate_project(db, project_id, organization_id)
        await self._commit(db, "Failed to bulk delete tasks")
        return {"affected_count": len(tasks), "message": "Tasks deleted successfully"}

    async def bulk_complete(
        self,
        db: AsyncSession,
        ids: list[str],
        organization_id: str,
        current_user: User | None = None,
    ) -> dict:
        tasks = await self.repository.list_by_ids(
            db,
            ids=ids,
            organization_id=organization_id,
            **(await self._access_kwargs(db, current_user)),
        )
        for task in tasks:
            if await self.repository.incomplete_dependency_ids(db, task.id):
                raise APIException(
                    status_code=409,
                    message=f"Task '{task.id}' has incomplete dependencies.",
                )
            task.status = "Completed"
        await db.flush()
        for project_id in {task.project_id for task in tasks if task.project_id}:
            await self._recalculate_project(db, project_id, organization_id)
        await self._commit(db, "Failed to mark tasks complete")
        return {"affected_count": len(tasks), "message": "Tasks marked complete"}

    async def complete_task(
        self,
        db: AsyncSession,
        task_id: str,
        organization_id: str,
        current_user: User | None = None,
    ) -> dict:
        task = await self.repository.get_by_id(
            db,
            task_id=task_id,
            organization_id=organization_id,
            **(await self._access_kwargs(db, current_user)),
        )
        if not task:
            raise NotFoundError(message=f"Task '{task_id}' not found")
        if await self.repository.incomplete_dependency_ids(db, task.id):
            raise APIException(
                status_code=409,
                message="Complete all task dependencies before completing this task.",
            )
        task.status = "Completed"
        await db.flush()
        await self._recalculate_project(db, task.project_id, organization_id)
        await self._commit(db, "Failed to complete task")
        await notification_service.notify(
            db,
            event_name="task.completed",
            organization_id=task.organization_id,
            entity_type="task",
            entity_id=task.id,
            assigned_to=task.assigned_to,
            data={"id": task.id, "title": task.title, "status": task.status},
        )
        return {"message": f"Task {task_id} marked as Completed", "status": "success"}

    async def reopen_task(
        self,
        db: AsyncSession,
        task_id: str,
        organization_id: str,
        current_user: User | None = None,
    ) -> dict:
        task = await self.repository.get_by_id(
            db,
            task_id=task_id,
            organization_id=organization_id,
            **(await self._access_kwargs(db, current_user)),
        )
        if not task:
            raise NotFoundError(message=f"Task '{task_id}' not found")
        task.status = "Pending"
        await db.flush()
        await self._recalculate_project(db, task.project_id, organization_id)
        await self._commit(db, "Failed to reopen task")
        return {"message": f"Task {task_id} reopened", "status": "success"}

    async def assign_task(
        self,
        db: AsyncSession,
        task_id: str,
        user_id: str,
        organization_id: str,
        current_user: User | None = None,
    ) -> dict:
        task = await self.repository.get_by_id(
            db,
            task_id=task_id,
            organization_id=organization_id,
            **(await self._access_kwargs(db, current_user)),
        )
        if not task:
            raise NotFoundError(message=f"Task '{task_id}' not found")
        task.assigned_to = await self._resolve_user_id(
            db,
            assigned_input=user_id,
            organization_id=organization_id,
            default_user_id=user_id,
        )
        await self._commit(db, "Failed to assign task")
        await notification_service.notify(
            db,
            event_name="task.assigned",
            organization_id=task.organization_id,
            entity_type="task",
            entity_id=task.id,
            assigned_to=task.assigned_to,
            data={"id": task.id, "title": task.title, "assigned_to": task.assigned_to},
        )
        return {"message": f"Task {task_id} assigned to user {user_id}", "status": "success"}

    async def require_task(
        self,
        db: AsyncSession,
        task_id: str,
        organization_id: str,
        current_user: User | None = None,
    ) -> None:
        task = await self.repository.get_by_id(
            db,
            task_id=task_id,
            organization_id=organization_id,
            **(await self._access_kwargs(db, current_user)),
        )
        if not task:
            raise NotFoundError(message=f"Task '{task_id}' not found")

    async def list_dependencies(
        self, db: AsyncSession, task_id: str, organization_id: str, current_user: User
    ) -> list[dict]:
        await self.require_task(db, task_id, organization_id, current_user)
        return [
            {"task_id": task_id, "depends_on_task_id": dependency_id}
            for dependency_id in await self.repository.dependency_ids(db, task_id)
        ]

    async def add_dependency(
        self,
        db: AsyncSession,
        task_id: str,
        depends_on_task_id: str,
        organization_id: str,
        current_user: User,
    ) -> dict:
        access_kwargs = await self._access_kwargs(db, current_user)
        task = await self.repository.get_by_id(
            db, task_id=task_id, organization_id=organization_id, **access_kwargs
        )
        dependency_task = await self.repository.get_by_id(
            db,
            task_id=depends_on_task_id,
            organization_id=organization_id,
            **access_kwargs,
        )
        if not task or not dependency_task:
            raise NotFoundError(message="Task dependency record not found")
        if not task.project_id or task.project_id != dependency_task.project_id:
            raise APIException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                message="Task dependencies must belong to the same project.",
            )
        locked_project_id = task.project_id
        await self.repository.lock_dependency_projects(
            db,
            project_ids={locked_project_id},
            organization_id=organization_id,
        )
        await db.refresh(task)
        await db.refresh(dependency_task)
        if (
            task.organization_id != organization_id
            or dependency_task.organization_id != organization_id
            or task.project_id != locked_project_id
            or dependency_task.project_id != locked_project_id
        ):
            raise APIException(
                status_code=status.HTTP_409_CONFLICT,
                message="Task projects changed concurrently. Reload and try again.",
            )
        existing = await self.repository.get_dependency(
            db, task_id=task_id, depends_on_task_id=depends_on_task_id
        )
        if existing:
            return {"task_id": task_id, "depends_on_task_id": depends_on_task_id}
        pending = [depends_on_task_id]
        visited: set[str] = set()
        while pending:
            candidate = pending.pop()
            if candidate == task_id:
                raise APIException(status_code=409, message="Task dependency would create a cycle.")
            if candidate in visited:
                continue
            visited.add(candidate)
            if len(visited) > 10000:
                raise APIException(status_code=409, message="Task dependency graph is too large.")
            pending.extend(await self.repository.dependency_ids(db, candidate))
        await self.repository.create_dependency(
            db,
            task_id=task_id,
            depends_on_task_id=depends_on_task_id,
            created_by=current_user.id,
        )
        await self._commit(db, "Failed to add task dependency")
        return {"task_id": task_id, "depends_on_task_id": depends_on_task_id}

    async def remove_dependency(
        self,
        db: AsyncSession,
        task_id: str,
        depends_on_task_id: str,
        organization_id: str,
        current_user: User,
    ) -> None:
        await self.require_task(db, task_id, organization_id, current_user)
        dependency = await self.repository.get_dependency(
            db, task_id=task_id, depends_on_task_id=depends_on_task_id
        )
        if dependency:
            await db.delete(dependency)
            await self._commit(db, "Failed to remove task dependency")

    async def export_csv(self) -> dict:
        raise APIException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED, message="Task export is not available"
        )

    async def import_csv(self) -> dict:
        raise APIException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED, message="Task import is not available"
        )

    async def list_subtasks(self) -> list:
        return []

    async def add_subtask(self, task_id: str, title: str) -> dict:
        raise APIException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED, message="Subtasks are not available"
        )

    async def set_reminder(self, task_id: str, reminder_time: str) -> dict:
        raise APIException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED, message="Task reminders are not available"
        )


task_service = TaskService()
