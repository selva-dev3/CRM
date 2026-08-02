from fastapi import APIRouter
from typing import List
from app.schemas.crm_schemas import TaskResponse, TaskCreate

router = APIRouter()

@router.get("/", response_model=List[TaskResponse], summary="List assigned tasks")
async def list_tasks():
    return [
        {"id": "tsk-1", "title": "Follow up with TechCorp demo", "description": "Send meeting invite", "priority": "High", "due_date": "2026-08-05", "status": "Pending", "assigned_to": "usr-1", "created_at": "2026-08-01T10:00:00Z"}
    ]

@router.post("/", response_model=TaskResponse, status_code=201, summary="Create task")
async def create_task(payload: TaskCreate):
    return {"id": "tsk-2", **payload.model_dump(), "created_at": "2026-08-02T12:00:00Z"}
