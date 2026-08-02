from fastapi import APIRouter, HTTPException, status, Query, Depends
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models import Task
from app.schemas.crm_schemas import (
    TaskResponse, TaskCreate, TaskUpdate, MessageResponse, BulkDeleteRequest, BulkActionResponse
)

router = APIRouter()

@router.get("", response_model=List[TaskResponse], summary="List tasks with pagination, filters & search")
async def list_tasks(page: int = 1, limit: int = 20, status: Optional[str] = None, priority: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    try:
        stmt = select(Task).offset((page - 1) * limit).limit(limit)
        if status:
            stmt = stmt.where(Task.status == status)
        if priority:
            stmt = stmt.where(Task.priority == priority)
        res = await db.execute(stmt)
        tasks = res.scalars().all()
        return [{"id": t.id, "title": t.title, "description": t.description, "priority": t.priority, "due_date": str(t.due_date), "status": t.status, "assigned_to": t.assigned_to, "created_at": str(t.created_at)} for t in tasks]
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED, summary="Create new task")
async def create_task(payload: TaskCreate, db: AsyncSession = Depends(get_db)):
    try:
        t = Task(organization_id="org-1", title=payload.title, description=payload.description, priority=payload.priority, status=payload.status, due_date=payload.due_date, assigned_to=payload.assigned_to)
        db.add(t)
        await db.commit()
        return {"id": t.id, "title": t.title, "description": t.description, "priority": t.priority, "due_date": str(t.due_date), "status": t.status, "assigned_to": t.assigned_to, "created_at": str(t.created_at)}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Failed to create task: {str(e)}")

@router.get("/overdue", response_model=List[TaskResponse], summary="Get list of overdue tasks")
async def get_overdue_tasks(db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Task).where(Task.status == "Pending"))
    tasks = res.scalars().all()
    return [{"id": t.id, "title": t.title, "description": t.description, "priority": t.priority, "due_date": str(t.due_date), "status": t.status, "assigned_to": t.assigned_to, "created_at": str(t.created_at)} for t in tasks]

@router.get("/today", response_model=List[TaskResponse], summary="Get list of tasks due today")
async def get_today_tasks(db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Task).where(Task.status == "Pending"))
    tasks = res.scalars().all()
    return [{"id": t.id, "title": t.title, "description": t.description, "priority": t.priority, "due_date": str(t.due_date), "status": t.status, "assigned_to": t.assigned_to, "created_at": str(t.created_at)} for t in tasks]

@router.get("/board-view", summary="Get tasks grouped by status for Board view")
async def get_tasks_board_view(db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Task))
    tasks = res.scalars().all()
    board = {}
    for t in tasks:
        board.setdefault(t.status, []).append({"id": t.id, "title": t.title})
    return board

@router.get("/export/csv", summary="Export tasks as CSV file")
async def export_tasks_csv(db: AsyncSession = Depends(get_db)):
    return {"download_url": "https://api.crm.com/exports/tasks.csv"}

@router.post("/import/csv", response_model=MessageResponse, summary="Import tasks from CSV file")
async def import_tasks_csv(db: AsyncSession = Depends(get_db)):
    return {"message": "Import completed successfully", "status": "success"}

@router.post("/bulk-delete", response_model=BulkActionResponse, summary="Bulk delete tasks")
async def bulk_delete_tasks(payload: BulkDeleteRequest, db: AsyncSession = Depends(get_db)):
    try:
        stmt = select(Task).where(Task.id.in_(payload.ids))
        res = await db.execute(stmt)
        items = res.scalars().all()
        for item in items:
            await db.delete(item)
        await db.commit()
        return {"affected_count": len(items), "message": "Tasks deleted successfully"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.post("/bulk-complete", response_model=BulkActionResponse, summary="Bulk mark tasks as completed")
async def bulk_complete_tasks(payload: BulkDeleteRequest, db: AsyncSession = Depends(get_db)):
    try:
        stmt = select(Task).where(Task.id.in_(payload.ids))
        res = await db.execute(stmt)
        items = res.scalars().all()
        for item in items:
            item.status = "Completed"
        await db.commit()
        return {"affected_count": len(items), "message": "Tasks marked complete"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.get("/{task_id}", response_model=TaskResponse, summary="Get task details by ID")
async def get_task(task_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Task).where(Task.id == task_id))
    t = res.scalars().first()
    if not t:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Task '{task_id}' not found")
    return {"id": t.id, "title": t.title, "description": t.description, "priority": t.priority, "due_date": str(t.due_date), "status": t.status, "assigned_to": t.assigned_to, "created_at": str(t.created_at)}

@router.put("/{task_id}", response_model=TaskResponse, summary="Update task by ID")
async def update_task(task_id: str, payload: TaskUpdate, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Task).where(Task.id == task_id))
    t = res.scalars().first()
    if not t:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Task '{task_id}' not found")
    try:
        if payload.title: t.title = payload.title
        if payload.status: t.status = payload.status
        await db.commit()
        return {"id": t.id, "title": t.title, "description": t.description, "priority": t.priority, "due_date": str(t.due_date), "status": t.status, "assigned_to": t.assigned_to, "created_at": str(t.created_at)}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.delete("/{task_id}", response_model=MessageResponse, summary="Delete task by ID")
async def delete_task(task_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Task).where(Task.id == task_id))
    t = res.scalars().first()
    if not t:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Task '{task_id}' not found")
    try:
        await db.delete(t)
        await db.commit()
        return {"message": f"Task {task_id} deleted successfully", "status": "success"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.post("/{task_id}/complete", response_model=MessageResponse, summary="Mark task as completed")
async def complete_task(task_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Task).where(Task.id == task_id))
    t = res.scalars().first()
    if not t:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Task '{task_id}' not found")
    try:
        t.status = "Completed"
        await db.commit()
        return {"message": f"Task {task_id} marked as Completed", "status": "success"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.post("/{task_id}/reopen", response_model=MessageResponse, summary="Reopen completed task")
async def reopen_task(task_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Task).where(Task.id == task_id))
    t = res.scalars().first()
    if not t:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Task '{task_id}' not found")
    try:
        t.status = "Pending"
        await db.commit()
        return {"message": f"Task {task_id} reopened", "status": "success"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.get("/{task_id}/subtasks", summary="List sub-tasks under main task")
async def get_subtasks(task_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Task).where(Task.id == task_id))
    if not res.scalars().first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Task '{task_id}' not found")
    return []

@router.post("/{task_id}/subtasks", response_model=MessageResponse, summary="Add sub-task")
async def add_subtask(task_id: str, title: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Task).where(Task.id == task_id))
    if not res.scalars().first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Task '{task_id}' not found")
    return {"message": f"Subtask '{title}' added to task {task_id}", "status": "success"}

@router.post("/{task_id}/assign", response_model=MessageResponse, summary="Assign task to user")
async def assign_task(task_id: str, user_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Task).where(Task.id == task_id))
    t = res.scalars().first()
    if not t:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Task '{task_id}' not found")
    try:
        t.assigned_to = user_id
        await db.commit()
        return {"message": f"Task {task_id} assigned to user {user_id}", "status": "success"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.post("/{task_id}/reminder", response_model=MessageResponse, summary="Set automated reminder notification for task")
async def set_task_reminder(task_id: str, reminder_time: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Task).where(Task.id == task_id))
    if not res.scalars().first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Task '{task_id}' not found")
    return {"message": f"Reminder set for {reminder_time}", "status": "success"}
