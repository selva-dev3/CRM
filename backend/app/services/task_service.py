from datetime import date, datetime

from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIException, NotFoundError
from app.models import User
from app.models.task import Task
from app.repositories.project_repository import ProjectRepository
from app.repositories.task_repository import TaskRepository
from app.schemas.crm_schemas import TaskCreate, TaskUpdate
from app.services.notification_service import notification_service
from app.services.org_service import organization_service


def parse_datetime(val: str | None) -> datetime | None:
    if not val or not str(val).strip():
        return None
    val_str = str(val).strip()
    try:
        return datetime.fromisoformat(val_str.replace("Z", "+00:00"))
    except Exception:
        try:
            d = date.fromisoformat(val_str)
            return datetime(d.year, d.month, d.day)
        except Exception:
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
        "project_id": getattr(task, "project_id", None),
        "created_at": str(task.created_at) if task.created_at else None,
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

    async def _validate_project(
        self, db: AsyncSession, project_id: str | None, organization_id: str
    ) -> str | None:
        if not project_id or project_id in {"null", "None"}:
            return None
        project = await self.project_repository.get(
            db, project_id=project_id, organization_id=organization_id
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

    async def _resolve_user_id(
        self,
        db: AsyncSession,
        *,
        assigned_input: str | None,
        organization_id: str,
        default_user_id: str,
    ) -> str:
        if assigned_input and str(assigned_input).strip():
            value = str(assigned_input).strip()
            user = await self.repository.get_user_by_id_name_email(
                db, value=value, organization_id=organization_id
            )
            if user:
                return user.id
            raise NotFoundError(message=f"User '{value}' not found")
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
    ) -> list[dict]:
        tasks = await self.repository.list(
            db,
            page=page,
            limit=limit,
            organization_id=organization_id,
            status=status,
            priority=priority,
        )
        return [task_to_dict(t) for t in tasks]

    async def get_task(self, db: AsyncSession, task_id: str, organization_id: str) -> dict:
        task = await self.repository.get_by_id(db, task_id=task_id, organization_id=organization_id)
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
        assigned_user = await self._resolve_user_id(
            db,
            assigned_input=payload.assigned_to,
            organization_id=org_id,
            default_user_id=current_user.id,
        )
        project_id = await self._validate_project(db, payload.project_id, org_id)
        data = {
            "organization_id": org_id,
            "title": payload.title,
            "description": payload.description,
            "priority": payload.priority or "Medium",
            "status": payload.status or "Pending",
            "due_date": due_dt,
            "assigned_to": assigned_user,
            "project_id": project_id,
        }
        task = await self.repository.create(db, data=data)
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

    async def get_overdue_tasks(self, db: AsyncSession, organization_id: str) -> list[dict]:
        tasks = await self.repository.list_pending(db, organization_id=organization_id)
        today = datetime.now().astimezone().date()
        return [task_to_dict(t) for t in tasks if t.due_date and t.due_date.date() < today]

    async def get_today_tasks(self, db: AsyncSession, organization_id: str) -> list[dict]:
        tasks = await self.repository.list_pending(db, organization_id=organization_id)
        today = datetime.now().astimezone().date()
        return [task_to_dict(t) for t in tasks if t.due_date and t.due_date.date() == today]

    async def get_board_view(self, db: AsyncSession, organization_id: str) -> dict:
        tasks = await self.repository.list_all(db, organization_id=organization_id)
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
        self, db: AsyncSession, task_id: str, payload: TaskUpdate, organization_id: str
    ) -> dict:
        task = await self.repository.get_by_id(db, task_id=task_id, organization_id=organization_id)
        if not task:
            raise NotFoundError(message=f"Task '{task_id}' not found")

        prev_priority = task.priority
        updates = payload.model_dump(exclude_unset=True)
        if "status" in updates:
            task.status = updates["status"]
        if "priority" in updates:
            task.priority = updates["priority"]
        if "project_id" in updates:
            task.project_id = await self._validate_project(
                db, updates["project_id"], task.organization_id
            )

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

    async def delete_task(self, db: AsyncSession, task_id: str, organization_id: str) -> dict:
        task = await self.repository.get_by_id(db, task_id=task_id, organization_id=organization_id)
        if not task:
            raise NotFoundError(message=f"Task '{task_id}' not found")
        await self.repository.delete(db, task)
        await self._commit(db, "Failed to delete task")
        return {"message": f"Task {task_id} deleted successfully", "status": "success"}

    async def bulk_delete(self, db: AsyncSession, ids: list[str], organization_id: str) -> dict:
        tasks = await self.repository.list_by_ids(db, ids=ids, organization_id=organization_id)
        for task in tasks:
            await self.repository.delete(db, task)
        await self._commit(db, "Failed to bulk delete tasks")
        return {"affected_count": len(tasks), "message": "Tasks deleted successfully"}

    async def bulk_complete(self, db: AsyncSession, ids: list[str], organization_id: str) -> dict:
        tasks = await self.repository.list_by_ids(db, ids=ids, organization_id=organization_id)
        for task in tasks:
            task.status = "Completed"
        await self._commit(db, "Failed to mark tasks complete")
        return {"affected_count": len(tasks), "message": "Tasks marked complete"}

    async def complete_task(self, db: AsyncSession, task_id: str, organization_id: str) -> dict:
        task = await self.repository.get_by_id(db, task_id=task_id, organization_id=organization_id)
        if not task:
            raise NotFoundError(message=f"Task '{task_id}' not found")
        task.status = "Completed"
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

    async def reopen_task(self, db: AsyncSession, task_id: str, organization_id: str) -> dict:
        task = await self.repository.get_by_id(db, task_id=task_id, organization_id=organization_id)
        if not task:
            raise NotFoundError(message=f"Task '{task_id}' not found")
        task.status = "Pending"
        await self._commit(db, "Failed to reopen task")
        return {"message": f"Task {task_id} reopened", "status": "success"}

    async def assign_task(
        self, db: AsyncSession, task_id: str, user_id: str, organization_id: str
    ) -> dict:
        task = await self.repository.get_by_id(db, task_id=task_id, organization_id=organization_id)
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

    async def require_task(self, db: AsyncSession, task_id: str, organization_id: str) -> None:
        task = await self.repository.get_by_id(db, task_id=task_id, organization_id=organization_id)
        if not task:
            raise NotFoundError(message=f"Task '{task_id}' not found")

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
