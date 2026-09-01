from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user, require_permission
from app.db.session import get_db
from app.models import User
from app.schemas.crm_schemas import (
    BulkActionResponse,
    BulkDeleteRequest,
    MessageResponse,
    TaskCreate,
    TaskResponse,
    TaskUpdate,
)
from app.services.task_service import task_service

router = APIRouter()


@router.get(
    "",
    response_model=list[TaskResponse],
    summary="List tasks with pagination, filters & search",
    dependencies=[Depends(require_permission("tasks:read"))],
)
async def list_tasks(
    page: int = 1,
    limit: int = 20,
    status: str | None = None,
    priority: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    return await task_service.list_tasks(
        db, page=page, limit=limit, status=status, priority=priority
    )


@router.post(
    "",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create new task",
    dependencies=[Depends(require_permission("tasks:create"))],
)
async def create_task(
    payload: TaskCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await task_service.create_task(db, payload, current_user)


@router.get(
    "/overdue",
    response_model=list[TaskResponse],
    summary="Get list of overdue tasks",
    dependencies=[Depends(require_permission("tasks:read"))],
)
async def get_overdue_tasks(db: AsyncSession = Depends(get_db)):
    return await task_service.get_overdue_tasks(db)


@router.get(
    "/today",
    response_model=list[TaskResponse],
    summary="Get list of tasks due today",
    dependencies=[Depends(require_permission("tasks:read"))],
)
async def get_today_tasks(db: AsyncSession = Depends(get_db)):
    return await task_service.get_today_tasks(db)


@router.get(
    "/board-view",
    summary="Get tasks grouped by status for Board view",
    dependencies=[Depends(require_permission("tasks:read"))],
)
async def get_tasks_board_view(db: AsyncSession = Depends(get_db)):
    return await task_service.get_board_view(db)


@router.get(
    "/export/csv",
    summary="Export tasks as CSV file",
    dependencies=[Depends(require_permission("tasks:read"))],
)
async def export_tasks_csv():
    return await task_service.export_csv()


@router.post(
    "/import/csv",
    response_model=MessageResponse,
    summary="Import tasks from CSV file",
    dependencies=[Depends(require_permission("tasks:create"))],
)
async def import_tasks_csv():
    return await task_service.import_csv()


@router.post(
    "/bulk-delete",
    response_model=BulkActionResponse,
    summary="Bulk delete tasks",
    dependencies=[Depends(require_permission("tasks:delete"))],
)
async def bulk_delete_tasks(payload: BulkDeleteRequest, db: AsyncSession = Depends(get_db)):
    return await task_service.bulk_delete(db, payload.ids)


@router.post(
    "/bulk-complete",
    response_model=BulkActionResponse,
    summary="Bulk mark tasks as completed",
    dependencies=[Depends(require_permission("tasks:complete"))],
)
async def bulk_complete_tasks(payload: BulkDeleteRequest, db: AsyncSession = Depends(get_db)):
    return await task_service.bulk_complete(db, payload.ids)


@router.get(
    "/{task_id}",
    response_model=TaskResponse,
    summary="Get task details by ID",
    dependencies=[Depends(require_permission("tasks:read"))],
)
async def get_task(task_id: str, db: AsyncSession = Depends(get_db)):
    return await task_service.get_task(db, task_id)


@router.put(
    "/{task_id}",
    response_model=TaskResponse,
    summary="Update task by ID",
    dependencies=[Depends(require_permission("tasks:update"))],
)
async def update_task(task_id: str, payload: TaskUpdate, db: AsyncSession = Depends(get_db)):
    return await task_service.update_task(db, task_id, payload)


@router.delete(
    "/{task_id}",
    response_model=MessageResponse,
    summary="Delete task by ID",
    dependencies=[Depends(require_permission("tasks:delete"))],
)
async def delete_task(task_id: str, db: AsyncSession = Depends(get_db)):
    return await task_service.delete_task(db, task_id)


@router.post(
    "/{task_id}/complete",
    response_model=MessageResponse,
    summary="Mark task as completed",
    dependencies=[Depends(require_permission("tasks:complete"))],
)
async def complete_task(task_id: str, db: AsyncSession = Depends(get_db)):
    return await task_service.complete_task(db, task_id)


@router.post(
    "/{task_id}/reopen",
    response_model=MessageResponse,
    summary="Reopen completed task",
    dependencies=[Depends(require_permission("tasks:update"))],
)
async def reopen_task(task_id: str, db: AsyncSession = Depends(get_db)):
    return await task_service.reopen_task(db, task_id)


@router.get(
    "/{task_id}/subtasks",
    summary="List sub-tasks under main task",
    dependencies=[Depends(require_permission("tasks:read"))],
)
async def get_subtasks(task_id: str, db: AsyncSession = Depends(get_db)):
    await task_service.require_task(db, task_id)
    return await task_service.list_subtasks()


@router.post(
    "/{task_id}/subtasks",
    response_model=MessageResponse,
    summary="Add sub-task",
    dependencies=[Depends(require_permission("tasks:create"))],
)
async def add_subtask(task_id: str, title: str, db: AsyncSession = Depends(get_db)):
    await task_service.require_task(db, task_id)
    return await task_service.add_subtask(task_id, title)


@router.post(
    "/{task_id}/assign",
    response_model=MessageResponse,
    summary="Assign task to user",
    dependencies=[Depends(require_permission("tasks:assign"))],
)
async def assign_task(task_id: str, user_id: str, db: AsyncSession = Depends(get_db)):
    return await task_service.assign_task(db, task_id, user_id)


@router.post(
    "/{task_id}/reminder",
    response_model=MessageResponse,
    summary="Set automated reminder notification for task",
    dependencies=[Depends(require_permission("tasks:update"))],
)
async def set_task_reminder(task_id: str, reminder_time: str, db: AsyncSession = Depends(get_db)):
    await task_service.require_task(db, task_id)
    return await task_service.set_reminder(task_id, reminder_time)
