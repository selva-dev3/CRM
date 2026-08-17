from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user, require_permission
from app.db.session import get_db
from app.models.auth import User
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
    response_model=list[NotificationItem],
    summary="List notifications for logged in user",
    dependencies=[Depends(require_permission("notifications:read"))],
)
async def list_notifications(
    page: int = 1,
    limit: int = 20,
    unread_only: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await notification_service.list_notifications(
        db, user_id=current_user.id, page=page, limit=limit, unread_only=unread_only
    )


@router.get("/unread-count", summary="Get unread notification count badge", dependencies=[Depends(require_permission("notifications:read"))])
async def get_unread_count(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await notification_service.get_unread_count(db, user_id=current_user.id)


@router.post(
    "/read-all", response_model=MessageResponse, summary="Mark all notifications as read",
    dependencies=[Depends(require_permission("notifications:read"))],
)
async def mark_all_notifications_read(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await notification_service.mark_all_notifications_read(
        db, user_id=current_user.id
    )


@router.get("/preferences", summary="Get user notification delivery preferences", dependencies=[Depends(require_permission("notifications:read"))])
async def get_notification_preferences(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await notification_service.get_notification_preferences()


@router.put(
    "/preferences",
    response_model=MessageResponse,
    summary="Update notification delivery preferences",
    dependencies=[Depends(require_permission("notifications:manage"))],
)
async def update_notification_preferences(
    email_notifications: bool = Query(True),
    webpush_notifications: bool = Query(True),
    slack_notifications: bool = Query(False),
    digest_frequency: str = Query("Daily"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
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
    dependencies=[Depends(require_permission("notifications:manage"))],
)
async def register_webpush_token(
    token: str = Query(...),
    device_type: str = Query("Chrome Desktop"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await notification_service.register_webpush_token(token, device_type)


@router.post(
    "/send-system-alert",
    response_model=MessageResponse,
    summary="Admin endpoint to broadcast system alert notification",
    dependencies=[Depends(require_permission("notifications:send"))],
)
async def send_system_alert(
    title: str = Query(...),
    message: str = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await notification_service.send_system_alert(
        db, user_id=current_user.id, org_id=current_user.organization_id,
        title=title, message=message,
    )


@router.post(
    "/bulk-delete",
    response_model=BulkActionResponse,
    summary="Bulk delete notifications",
    dependencies=[Depends(require_permission("notifications:manage"))],
)
async def bulk_delete_notifications(
    payload: BulkDeleteRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await notification_service.bulk_delete(
        db, user_id=current_user.id, ids=payload.ids
    )


@router.post(
    "/{notification_id}/read",
    response_model=MessageResponse,
    summary="Mark single notification as read",
    dependencies=[Depends(require_permission("notifications:read"))],
)
async def mark_notification_read(
    notification_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await notification_service.mark_notification_read(
        db, user_id=current_user.id, notification_id=notification_id
    )


@router.delete(
    "/{notification_id}",
    response_model=MessageResponse,
    summary="Delete single notification",
    dependencies=[Depends(require_permission("notifications:manage"))],
)
async def delete_notification(
    notification_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await notification_service.delete_notification(
        db, user_id=current_user.id, notification_id=notification_id
    )
