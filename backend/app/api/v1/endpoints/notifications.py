from fastapi import APIRouter, HTTPException, status, Query
from typing import List, Optional
from app.schemas.crm_schemas import NotificationItem, MessageResponse, BulkDeleteRequest, BulkActionResponse

router = APIRouter()

@router.get("", response_model=List[NotificationItem], summary="List notifications for logged in user")
async def list_notifications(page: int = 1, limit: int = 20, unread_only: bool = False):
    return [
        {"id": "ntf-1", "title": "New Lead Assigned", "message": "Lead Alice Johnson assigned to you", "is_read": False, "created_at": "2026-08-02T10:00:00Z"},
        {"id": "ntf-2", "title": "Task Overdue", "message": "Task 'Follow up TechCorp' is overdue", "is_read": True, "created_at": "2026-08-01T15:00:00Z"}
    ]

@router.get("/unread-count", summary="Get unread notification count badge")
async def get_unread_count():
    return {"unread_count": 5}

@router.post("/read-all", response_model=MessageResponse, summary="Mark all notifications as read")
async def mark_all_notifications_read():
    return {"message": "All notifications marked as read", "status": "success"}

@router.get("/preferences", summary="Get user notification delivery preferences")
async def get_notification_preferences():
    return {"email_notifications": True, "webpush_notifications": True, "slack_notifications": False, "digest_frequency": "Daily"}

@router.put("/preferences", response_model=MessageResponse, summary="Update notification delivery preferences")
async def update_notification_preferences(email_notifications: bool = True, webpush_notifications: bool = True, slack_notifications: bool = False):
    return {"message": "Notification preferences updated", "status": "success"}

@router.post("/webpush/register", response_model=MessageResponse, summary="Register WebPush browser token for push notifications")
async def register_webpush_token(token: str, device_type: str = "Chrome"):
    return {"message": "WebPush token registered", "status": "success"}

@router.post("/send-system-alert", response_model=MessageResponse, summary="Admin endpoint to broadcast system alert notification")
async def send_system_alert(title: str, message: str):
    return {"message": f"Broadcasted alert '{title}' to all active users", "status": "success"}

@router.post("/bulk-delete", response_model=BulkActionResponse, summary="Bulk delete notifications")
async def bulk_delete_notifications(payload: BulkDeleteRequest):
    return {"affected_count": len(payload.ids), "message": "Notifications deleted successfully"}

@router.post("/{notification_id}/read", response_model=MessageResponse, summary="Mark single notification as read")
async def mark_notification_read(notification_id: str):
    return {"message": f"Notification {notification_id} marked as read", "status": "success"}

@router.delete("/{notification_id}", response_model=MessageResponse, summary="Delete single notification")
async def delete_notification(notification_id: str):
    return {"message": f"Notification {notification_id} deleted", "status": "success"}
