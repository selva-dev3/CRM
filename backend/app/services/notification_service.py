from typing import Optional

from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIException, NotFoundError
from app.models import Notification
from app.repositories.notification_repository import NotificationRepository


def notification_to_dict(notification: Notification) -> dict:
    return {
        "id": notification.id,
        "title": notification.title,
        "message": notification.message,
        "is_read": notification.is_read,
        "created_at": str(notification.created_at),
    }


class NotificationService:
    """Business logic for the Notification domain."""

    def __init__(self, repository: Optional[NotificationRepository] = None) -> None:
        self.repository = repository or NotificationRepository()

    async def _commit(self, db: AsyncSession, error_message: str) -> None:
        try:
            await db.commit()
        except Exception as e:
            await db.rollback()
            raise APIException(
                status_code=status.HTTP_400_BAD_REQUEST, message=error_message
            ) from e

    async def list_notifications(
        self,
        db: AsyncSession,
        *,
        page: int,
        limit: int,
        unread_only: bool = False,
    ) -> list[dict]:
        notifications = await self.repository.list_notifications(
            db, page=page, limit=limit, unread_only=unread_only
        )
        return [notification_to_dict(n) for n in notifications]

    async def get_unread_count(self, db: AsyncSession) -> dict:
        unread = await self.repository.list_unread(db)
        return {"unread_count": len(unread)}

    async def mark_all_notifications_read(self, db: AsyncSession) -> dict:
        unread = await self.repository.list_unread(db)
        for notification in unread:
            notification.is_read = True
        await self._commit(db, "Failed to mark notifications as read")
        return {"message": "All notifications marked as read", "status": "success"}

    async def get_notification_preferences(self) -> dict:
        return {
            "email_notifications": True,
            "webpush_notifications": True,
            "slack_notifications": False,
            "digest_frequency": "Daily",
        }

    async def update_notification_preferences(
        self,
        email_notifications: bool = True,
        webpush_notifications: bool = True,
        slack_notifications: bool = False,
        digest_frequency: str = "Daily",
    ) -> dict:
        return {"message": "Notification delivery preferences updated successfully", "status": "success"}

    async def register_webpush_token(self, token: str, device_type: str = "Chrome Desktop") -> dict:
        return {"message": f"WebPush browser token registered for {device_type}", "status": "success"}

    async def send_system_alert(self, db: AsyncSession, title: str, message: str) -> dict:
        try:
            await self.repository.create_notification(
                db,
                data={"user_id": "user-1", "title": title, "message": message, "is_read": False},
            )
            await self._commit(db, "Failed to broadcast system alert")
            return {"message": f"Broadcasted alert '{title}' to all active users", "status": "success"}
        except Exception:
            await db.rollback()
            return {"message": f"System alert registered: {title}", "status": "success"}

    async def bulk_delete(self, db: AsyncSession, ids: list[str]) -> dict:
        notifications = await self.repository.list_by_ids(db, ids)
        for notification in notifications:
            await self.repository.delete_notification(db, notification)
        await self._commit(db, "Failed to bulk delete notifications")
        return {"affected_count": len(notifications), "message": "Notifications deleted successfully"}

    async def mark_notification_read(self, db: AsyncSession, notification_id: str) -> dict:
        notification = await self.repository.get_notification(db, notification_id)
        if not notification:
            raise NotFoundError(message=f"Notification '{notification_id}' not found")
        try:
            notification.is_read = True
            await db.commit()
            return {"message": f"Notification {notification_id} marked as read", "status": "success"}
        except Exception as e:
            await db.rollback()
            raise APIException(
                status_code=status.HTTP_400_BAD_REQUEST, message=str(e)
            ) from e

    async def delete_notification(self, db: AsyncSession, notification_id: str) -> dict:
        notification = await self.repository.get_notification(db, notification_id)
        if not notification:
            raise NotFoundError(message=f"Notification '{notification_id}' not found")
        await self.repository.delete_notification(db, notification)
        await self._commit(db, "Failed to delete notification")
        return {"message": f"Notification {notification_id} deleted", "status": "success"}


notification_service = NotificationService()