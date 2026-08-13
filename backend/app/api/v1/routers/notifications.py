from typing import List

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.crm_schemas import (
    BulkActionResponse,
    BulkDeleteRequest,
    MessageResponse,
    NotificationItem,
)
from app.services.notification_service import notification_service

router = APIRouter()


@router.get(
    "",
    response_model=List[NotificationItem],
    summary="List notifications for logged in user",
)
async def list_notifications(
    page: int = 1,
    limit: int = 20,
    unread_only: bool = False,
    db: AsyncSession = Depends(get_db),
):
    return await notification_service.list_notifications(
        db, page=page, limit=limit, unread_only=unread_only
    )


@router.get("/unread-count", summary="Get unread notification count badge")
async def get_unread_count(db: AsyncSession = Depends(get_db)):
    return await notification_service.get_unread_count(db)


@router.post(
    "/read-all", response_model=MessageResponse, summary="Mark all notifications as read"
)
async def mark_all_notifications_read(db: AsyncSession = Depends(get_db)):
    return await notification_service.mark_all_notifications_read(db)


@router.get("/preferences", summary="Get user notification delivery preferences")
async def get_notification_preferences(db: AsyncSession = Depends(get_db)):
    return await notification_service.get_notification_preferences()


@router.put(
    "/preferences",
    response_model=MessageResponse,
    summary="Update notification delivery preferences",
)
async def update_notification_preferences(
    email_notifications: bool = Query(True),
    webpush_notifications: bool = Query(True),
    slack_notifications: bool = Query(False),
    digest_frequency: str = Query("Daily"),
    db: AsyncSession = Depends(get_db),
):
    return await notification_service.update_notification_preferences(
        email_notifications=email_notifications,
        webpush_notifications=webpush_notifications,
        slack_notifications=slack_notifications,
        digest_frequency=digest_frequency,
    )


@router.post(
    "/webpush/register",
    response_model=MessageResponse,
    summary="Register WebPush browser token for push notifications",
)
async def register_webpush_token(
    token: str = Query(...),
    device_type: str = Query("Chrome Desktop"),
    db: AsyncSession = Depends(get_db),
):
    return await notification_service.register_webpush_token(token, device_type)


@router.post(
    "/send-system-alert",
    response_model=MessageResponse,
    summary="Admin endpoint to broadcast system alert notification",
)
async def send_system_alert(
    title: str = Query(...), message: str = Query(...), db: AsyncSession = Depends(get_db)
):
    return await notification_service.send_system_alert(db, title, message)


@router.post(
    "/bulk-delete",
    response_model=BulkActionResponse,
    summary="Bulk delete notifications",
)
async def bulk_delete_notifications(
    payload: BulkDeleteRequest, db: AsyncSession = Depends(get_db)
):
    return await notification_service.bulk_delete(db, payload.ids)


@router.post(
    "/{notification_id}/read",
    response_model=MessageResponse,
    summary="Mark single notification as read",
)
async def mark_notification_read(notification_id: str, db: AsyncSession = Depends(get_db)):
    return await notification_service.mark_notification_read(db, notification_id)


@router.delete(
    "/{notification_id}",
    response_model=MessageResponse,
    summary="Delete single notification",
)
async def delete_notification(notification_id: str, db: AsyncSession = Depends(get_db)):
    return await notification_service.delete_notification(db, notification_id)