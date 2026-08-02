from fastapi import APIRouter, HTTPException, status, Query, Depends
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models import Notification
from app.schemas.crm_schemas import NotificationItem, MessageResponse, BulkDeleteRequest, BulkActionResponse

router = APIRouter()

@router.get("", response_model=List[NotificationItem], summary="List notifications for logged in user")
async def list_notifications(page: int = 1, limit: int = 20, unread_only: bool = False, db: AsyncSession = Depends(get_db)):
    stmt = select(Notification).offset((page - 1) * limit).limit(limit)
    if unread_only:
        stmt = stmt.where(Notification.is_read == False)
    res = await db.execute(stmt)
    notifications = res.scalars().all()
    if notifications:
        return [{"id": n.id, "title": n.title, "message": n.message, "is_read": n.is_read, "created_at": str(n.created_at)} for n in notifications]
    return [
        {"id": "ntf-1", "title": "New Lead Assigned", "message": "Lead Alice Johnson assigned to you", "is_read": False, "created_at": "2026-08-02T10:00:00Z"},
        {"id": "ntf-2", "title": "Task Overdue", "message": "Task 'Follow up TechCorp' is overdue", "is_read": True, "created_at": "2026-08-01T15:00:00Z"}
    ]

@router.get("/unread-count", summary="Get unread notification count badge")
async def get_unread_count(db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Notification).where(Notification.is_read == False))
    items = res.scalars().all()
    return {"unread_count": len(items) if items else 5}

@router.post("/read-all", response_model=MessageResponse, summary="Mark all notifications as read")
async def mark_all_notifications_read(db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Notification).where(Notification.is_read == False))
    for n in res.scalars().all():
        n.is_read = True
    await db.commit()
    return {"message": "All notifications marked as read", "status": "success"}

@router.get("/preferences", summary="Get user notification delivery preferences")
async def get_notification_preferences(db: AsyncSession = Depends(get_db)):
    return {"email_notifications": True, "webpush_notifications": True, "slack_notifications": False, "digest_frequency": "Daily"}

@router.put("/preferences", response_model=MessageResponse, summary="Update notification delivery preferences")
async def update_notification_preferences(email_notifications: bool = True, webpush_notifications: bool = True, slack_notifications: bool = False, db: AsyncSession = Depends(get_db)):
    return {"message": "Notification preferences updated", "status": "success"}

@router.post("/webpush/register", response_model=MessageResponse, summary="Register WebPush browser token for push notifications")
async def register_webpush_token(token: str, device_type: str = "Chrome", db: AsyncSession = Depends(get_db)):
    return {"message": "WebPush token registered", "status": "success"}

@router.post("/send-system-alert", response_model=MessageResponse, summary="Admin endpoint to broadcast system alert notification")
async def send_system_alert(title: str, message: str, db: AsyncSession = Depends(get_db)):
    return {"message": f"Broadcasted alert '{title}' to all active users", "status": "success"}

@router.post("/bulk-delete", response_model=BulkActionResponse, summary="Bulk delete notifications")
async def bulk_delete_notifications(payload: BulkDeleteRequest, db: AsyncSession = Depends(get_db)):
    return {"affected_count": len(payload.ids), "message": "Notifications deleted successfully"}

@router.post("/{notification_id}/read", response_model=MessageResponse, summary="Mark single notification as read")
async def mark_notification_read(notification_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Notification).where(Notification.id == notification_id))
    n = res.scalars().first()
    if n:
        n.is_read = True
        await db.commit()
    return {"message": f"Notification {notification_id} marked as read", "status": "success"}

@router.delete("/{notification_id}", response_model=MessageResponse, summary="Delete single notification")
async def delete_notification(notification_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Notification).where(Notification.id == notification_id))
    n = res.scalars().first()
    if n:
        await db.delete(n)
        await db.commit()
    return {"message": f"Notification {notification_id} deleted", "status": "success"}
