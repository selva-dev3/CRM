from fastapi import APIRouter
from typing import List
from app.schemas.crm_schemas import NotificationItem

router = APIRouter()

@router.get("/", response_model=List[NotificationItem], summary="List user notifications")
async def list_notifications():
    return [
        {"id": "ntf-1", "title": "New High-Value Lead", "message": "TechCorp (Score: 92) requested a demo", "is_read": False, "created_at": "2026-08-02T10:00:00Z"}
    ]

@router.patch("/{notification_id}/read", summary="Mark notification as read")
async def mark_read(notification_id: str):
    return {"id": notification_id, "is_read": True}
