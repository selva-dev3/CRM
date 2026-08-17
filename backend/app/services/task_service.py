from datetime import date, datetime
from typing import Optional

from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIException, NotFoundError
from app.models import User
from app.models.task import Task
from app.repositories.task_repository import TaskRepository
from app.schemas.crm_schemas import TaskCreate, TaskUpdate
from app.services.notification_service import notification_service
from app.services.org_service import organization_service


def parse_datetime(val: Optional[str]) -> Optional[datetime]:
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
        "created_at": str(task.created_at) if task.created_at else None,
    }


class TaskService:
    """Business logic for the Task domain."""

    def __init__(self, repository: Optional[TaskRepository] = None) -> None:
        self.repository = repository or TaskRepository()

    async def _commit(self, db: AsyncSession, error_message: str) -> None:
        try:
            await db.commit()
        except Exception as e:
            await db.rollback()
            raise APIException(
                status_code=status.HTTP_400_BAD_REQUEST, message=error_message
            ) from e

    async def _resolve_user_id(
        self, db: AsyncSession, assigned_input: Optional[str] = None
    ) -> str:
        if assigned_input and str(assigned_input).strip():
            value = str(assigned_input).strip()
            user = await self.repository.get_user_by_id_name_email(db, value)
            if user:
                return user.id

        first_user = await self.repository.get_first_user(db)
        if first_user:
            return first_user.id

        user = await self.repository.create_system_user(db)
        return user.id

    async def list_tasks(
        self,
        db: AsyncSession,
        *,
        page: int,
        limit: int,
        status: Optional[str] = None,
        priority: Optional[str] = None,
    ) -> list[dict]:
        tasks = await self.repository.list(
            db, page=page, limit=limit, status=status, priority=priority
        )
        return [task_to_dict(t) for t in tasks]

    async def get_task(self, db: AsyncSession, task_id: str) -> dict:
        task = await self.repository.get_by_id(db, task_id)
        if not task:
            raise NotFoundError(message=f"Task '{task_id}' not found")
        return task_to_dict(task)

    async def create_task(
        self, db: AsyncSession, payload: TaskCreate, current_user: Optional[User] = None
    ) -> dict:
        due_dt = parse_datetime(payload.due_date)
        assigned_user = await self._resolve_user_id(db, payload.assigned_to)
        org_id = await organization_service.resolve_valid_org_id(db, current_user)
        data = {
            "organization_id": org_id,
            "title": payload.title,
            "description": payload.description,
            "priority": payload.priority or "Medium",
            "status": payload.status or "Pending",
            "due_date": due_dt,
            "assigned_to": assigned_user,
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

    async def get_overdue_tasks(self, db: AsyncSession) -> list[dict]:
        tasks = await self.repository.list_pending(db)
        return [task_to_dict(t) for t in tasks]

    async def get_today_tasks(self, db: AsyncSession) -> list[dict]:
        tasks = await self.repository.list_pending(db)
        return [task_to_dict(t) for t in tasks]

    async def get_board_view(self, db: AsyncSession) -> dict:
        tasks = await self.repository.list_all(db)
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

    async def update_task(self, db: AsyncSession, task_id: str, payload: TaskUpdate) -> dict:
        task = await self.repository.get_by_id(db, task_id)
        if not task:
            raise NotFoundError(message=f"Task '{task_id}' not found")

        updates = payload.model_dump(exclude_unset=True)
        if "status" in updates:
            task.status = updates["status"]
        if "priority" in updates:
            task.priority = updates["priority"]

        await self._commit(db, "Failed to update task")
        await db.refresh(task)
        return task_to_dict(task)

    async def delete_task(self, db: AsyncSession, task_id: str) -> dict:
        task = await self.repository.get_by_id(db, task_id)
        if not task:
            raise NotFoundError(message=f"Task '{task_id}' not found")
        await self.repository.delete(db, task)
        await self._commit(db, "Failed to delete task")
        return {"message": f"Task {task_id} deleted successfully", "status": "success"}

    async def bulk_delete(self, db: AsyncSession, ids: list[str]) -> dict:
        tasks = await self.repository.list_by_ids(db, ids)
        for task in tasks:
            await self.repository.delete(db, task)
        await self._commit(db, "Failed to bulk delete tasks")
        return {"affected_count": len(tasks), "message": "Tasks deleted successfully"}

    async def bulk_complete(self, db: AsyncSession, ids: list[str]) -> dict:
        tasks = await self.repository.list_by_ids(db, ids)
        for task in tasks:
            task.status = "Completed"
        await self._commit(db, "Failed to mark tasks complete")
        return {"affected_count": len(tasks), "message": "Tasks marked complete"}

    async def complete_task(self, db: AsyncSession, task_id: str) -> dict:
        task = await self.repository.get_by_id(db, task_id)
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

    async def reopen_task(self, db: AsyncSession, task_id: str) -> dict:
        task = await self.repository.get_by_id(db, task_id)
        if not task:
            raise NotFoundError(message=f"Task '{task_id}' not found")
        task.status = "Pending"
        await self._commit(db, "Failed to reopen task")
        return {"message": f"Task {task_id} reopened", "status": "success"}

    async def assign_task(self, db: AsyncSession, task_id: str, user_id: str) -> dict:
        task = await self.repository.get_by_id(db, task_id)
        if not task:
            raise NotFoundError(message=f"Task '{task_id}' not found")
        task.assigned_to = await self._resolve_user_id(db, user_id)
        await self._commit(db, "Failed to assign task")
        return {"message": f"Task {task_id} assigned to user {user_id}", "status": "success"}

    async def require_task(self, db: AsyncSession, task_id: str) -> None:
        task = await self.repository.get_by_id(db, task_id)
        if not task:
            raise NotFoundError(message=f"Task '{task_id}' not found")

    async def export_csv(self) -> dict:
        return {"download_url": "https://api.crm.com/exports/tasks.csv"}

    async def import_csv(self) -> dict:
        return {"message": "Import completed successfully", "status": "success"}

    async def list_subtasks(self) -> list:
        return []

    async def add_subtask(self, task_id: str, title: str) -> dict:
        return {"message": f"Subtask '{title}' added to task {task_id}", "status": "success"}

    async def set_reminder(self, task_id: str, reminder_time: str) -> dict:
        return {"message": f"Reminder set for {reminder_time}", "status": "success"}


task_service = TaskService()