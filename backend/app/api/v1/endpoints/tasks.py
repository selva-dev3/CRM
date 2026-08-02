from fastapi import APIRouter, HTTPException, status, Query
from typing import List, Optional
from app.schemas.crm_schemas import (
    TaskResponse, TaskCreate, TaskUpdate, MessageResponse, BulkDeleteRequest, BulkActionResponse
)

router = APIRouter()

@router.get("", response_model=List[TaskResponse], summary="List tasks with pagination, filters & search")
async def list_tasks(page: int = 1, limit: int = 20, status: Optional[str] = None, priority: Optional[str] = None):
    return [
        {"id": "tsk-1", "title": "Follow up with TechCorp", "description": "Send updated contract draft", "priority": "High", "due_date": "2026-08-05", "status": "Pending", "assigned_to": "usr-1", "created_at": "2026-08-02"},
        {"id": "tsk-2", "title": "Prepare Q3 Deck", "description": "Gather sales rep metrics", "priority": "Medium", "due_date": "2026-08-10", "status": "In Progress", "assigned_to": "usr-2", "created_at": "2026-08-02"}
    ]

@router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED, summary="Create new task")
async def create_task(payload: TaskCreate):
    return {"id": "tsk-3", "title": payload.title, "description": payload.description, "priority": payload.priority, "due_date": payload.due_date, "status": payload.status, "assigned_to": payload.assigned_to, "created_at": "2026-08-02"}

@router.get("/overdue", response_model=List[TaskResponse], summary="Get list of overdue tasks")
async def get_overdue_tasks():
    return [{"id": "tsk-10", "title": "Missed Call Back", "description": "Call Bob back", "priority": "Urgent", "due_date": "2026-08-01", "status": "Pending", "assigned_to": "usr-1", "created_at": "2026-07-30"}]

@router.get("/today", response_model=List[TaskResponse], summary="Get list of tasks due today")
async def get_today_tasks():
    return [{"id": "tsk-11", "title": "Demo Call Prep", "description": "Setup test org", "priority": "High", "due_date": "2026-08-02", "status": "Pending", "assigned_to": "usr-1", "created_at": "2026-08-02"}]

@router.get("/board-view", summary="Get tasks grouped by status for Board view")
async def get_tasks_board_view():
    return {
        "Pending": [{"id": "tsk-1", "title": "Follow up TechCorp"}],
        "In Progress": [{"id": "tsk-2", "title": "Prepare Q3 Deck"}],
        "Completed": [{"id": "tsk-99", "title": "Initial Outreach"}]
    }

@router.get("/export/csv", summary="Export tasks as CSV file")
async def export_tasks_csv():
    return {"download_url": "https://api.crm.com/exports/tasks.csv"}

@router.post("/import/csv", response_model=MessageResponse, summary="Import tasks from CSV file")
async def import_tasks_csv():
    return {"message": "Imported 40 tasks", "status": "success"}

@router.post("/bulk-delete", response_model=BulkActionResponse, summary="Bulk delete tasks")
async def bulk_delete_tasks(payload: BulkDeleteRequest):
    return {"affected_count": len(payload.ids), "message": "Tasks deleted successfully"}

@router.post("/bulk-complete", response_model=BulkActionResponse, summary="Bulk mark tasks as completed")
async def bulk_complete_tasks(payload: BulkDeleteRequest):
    return {"affected_count": len(payload.ids), "message": "Tasks marked complete"}

@router.get("/{task_id}", response_model=TaskResponse, summary="Get task details by ID")
async def get_task(task_id: str):
    return {"id": task_id, "title": "Follow up with TechCorp", "description": "Send updated contract draft", "priority": "High", "due_date": "2026-08-05", "status": "Pending", "assigned_to": "usr-1", "created_at": "2026-08-02"}

@router.put("/{task_id}", response_model=TaskResponse, summary="Update task by ID")
async def update_task(task_id: str, payload: TaskUpdate):
    return {"id": task_id, "title": payload.title or "Follow up with TechCorp", "description": "Send updated contract draft", "priority": payload.priority or "High", "due_date": "2026-08-05", "status": payload.status or "Pending", "assigned_to": "usr-1", "created_at": "2026-08-02"}

@router.delete("/{task_id}", response_model=MessageResponse, summary="Delete task by ID")
async def delete_task(task_id: str):
    return {"message": f"Task {task_id} deleted successfully", "status": "success"}

@router.post("/{task_id}/complete", response_model=MessageResponse, summary="Mark task as completed")
async def complete_task(task_id: str):
    return {"message": f"Task {task_id} marked as Completed", "status": "success"}

@router.post("/{task_id}/reopen", response_model=MessageResponse, summary="Reopen completed task")
async def reopen_task(task_id: str):
    return {"message": f"Task {task_id} reopened", "status": "success"}

@router.get("/{task_id}/subtasks", summary="List sub-tasks under main task")
async def get_subtasks(task_id: str):
    return [{"subtask_id": "st-1", "title": "Review clause 4", "completed": True}]

@router.post("/{task_id}/subtasks", response_model=MessageResponse, summary="Add sub-task")
async def add_subtask(task_id: str, title: str):
    return {"message": f"Subtask '{title}' added to task {task_id}", "status": "success"}

@router.post("/{task_id}/assign", response_model=MessageResponse, summary="Assign task to user")
async def assign_task(task_id: str, user_id: str):
    return {"message": f"Task {task_id} assigned to user {user_id}", "status": "success"}

@router.post("/{task_id}/reminder", response_model=MessageResponse, summary="Set automated reminder notification for task")
async def set_task_reminder(task_id: str, reminder_time: str):
    return {"message": f"Reminder set for {reminder_time}", "status": "success"}
