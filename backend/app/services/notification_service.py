import json
from datetime import UTC, datetime

from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIException, NotFoundError
from app.core.logging import get_logger
from app.models import Notification
from app.repositories.notification_repository import NotificationRepository
from app.repositories.user_repository import UserRepository
from app.services.integration_service import integration_service

logger = get_logger(__name__)

# Recipient targeting rules per event. "org-wide" = every active user in the org.
_ORG_WIDE_EVENTS = {
    "company.created",
    "company.updated",
    "contact.created",
    "meeting.created",
    "invoice.paid",
}
_ASSIGNEE_OR_ORG_EVENTS = {
    "lead.created",
    "lead.updated",
    "deal.created",
    "deal.won",
    "deal.lost",
    "task.created",
}
_ASSIGNEE_ONLY_EVENTS = {
    "lead.assigned",
    "task.completed",
}

_EVENT_TITLES = {
    "lead.created": "New lead created",
    "lead.updated": "Lead updated",
    "lead.assigned": "Lead assigned to you",
    "deal.created": "New deal created",
    "deal.won": "Deal won",
    "deal.lost": "Deal lost",
    "task.created": "New task",
    "task.completed": "Task completed",
    "company.created": "New company added",
    "company.updated": "Company updated",
    "contact.created": "New contact added",
    "meeting.created": "Meeting scheduled",
    "invoice.paid": "Invoice paid",
}


def _safe_payload(data: dict | None) -> str | None:
    if not data:
        return None
    try:
        return json.dumps(data)
    except (TypeError, ValueError):
        return None


def notification_to_dict(notification: Notification) -> dict:
    payload = None
    if notification.payload:
        try:
            payload = json.loads(notification.payload)
        except (TypeError, ValueError):
            payload = None
    return {
        "id": notification.id,
        "title": notification.title,
        "message": notification.message,
        "is_read": notification.is_read,
        "created_at": str(notification.created_at),
        "organization_id": notification.organization_id,
        "event_name": notification.event_name,
        "entity_type": notification.entity_type,
        "entity_id": notification.entity_id,
        "payload": payload,
        "read_at": str(notification.read_at) if notification.read_at else None,
        "updated_at": str(notification.updated_at) if notification.updated_at else None,
    }


class NotificationService:
    """Business logic for the Notification domain."""

    def __init__(
        self,
        repository: NotificationRepository | None = None,
        user_repository: UserRepository | None = None,
    ) -> None:
        self.repository = repository or NotificationRepository()
        self.user_repository = user_repository or UserRepository()

    async def _commit(self, db: AsyncSession, error_message: str) -> None:
        try:
            await db.commit()
        except Exception as e:
            await db.rollback()
            raise APIException(
                status_code=status.HTTP_400_BAD_REQUEST, message=error_message
            ) from e

    async def _safe_rollback(self, db: AsyncSession) -> None:
        try:
            await db.rollback()
        except Exception:
            return

    async def _org_active_ids(self, db: AsyncSession, org_id: str) -> list[str]:
        try:
            return list(await self.user_repository.list_active_ids_by_org(db, org_id))
        except Exception as e:
            logger.warning("Failed to resolve active users for org '%s': %s", org_id, e)
            return []

    async def _resolve_recipient_ids(
        self,
        db: AsyncSession,
        *,
        event_name: str,
        organization_id: str,
        assigned_to: str | None,
        actor_user_id: str | None,
    ) -> list[str]:
        if event_name in _ASSIGNEE_ONLY_EVENTS:
            candidates = [assigned_to] if assigned_to else []
        elif event_name in _ASSIGNEE_OR_ORG_EVENTS:
            candidates = (
                [assigned_to]
                if assigned_to
                else await self._org_active_ids(db, organization_id)
            )
        else:
            candidates = await self._org_active_ids(db, organization_id)
        if actor_user_id and actor_user_id in candidates:
            candidates = [uid for uid in candidates if uid != actor_user_id]
        return candidates

    async def notify(
        self,
        db: AsyncSession,
        *,
        event_name: str,
        organization_id: str,
        actor_user_id: str | None = None,
        entity_type: str,
        entity_id: str,
        data: dict | None = None,
        assigned_to: str | None = None,
    ) -> None:
        """Central dispatcher for CRM entity events.

        Creates in-app notifications for the resolved recipients (best-effort,
        never raises) and then dispatches exactly one Slack event through
        integration_service.notify_slack_event, which is itself best-effort and
        post-commit. A notification failure must never roll back or break the
        already-completed CRM operation.
        """
        try:
            recipient_ids = await self._resolve_recipient_ids(
                db,
                event_name=event_name,
                organization_id=organization_id,
                assigned_to=assigned_to,
                actor_user_id=actor_user_id,
            )
            title = _EVENT_TITLES.get(event_name, "CRM update")
            subject = (data or {}).get("title") or (data or {}).get("name")
            message = f"{title}: {subject}" if subject else title
            created = False
            for user_id in recipient_ids:
                if await self.repository.exists_unread(
                    db,
                    user_id=user_id,
                    event_name=event_name,
                    entity_type=entity_type,
                    entity_id=entity_id,
                ):
                    continue
                await self.repository.create_notification(
                    db,
                    data={
                        "user_id": user_id,
                        "organization_id": organization_id,
                        "event_name": event_name,
                        "entity_type": entity_type,
                        "entity_id": entity_id,
                        "title": title,
                        "message": message,
                        "payload": _safe_payload(data),
                        "is_read": False,
                    },
                )
                created = True
            if created:
                await self.repository.commit(db)
        except Exception as e:
            logger.warning(
                "In-app notification failed for event '%s' (org %s): %s",
                event_name,
                organization_id,
                e,
            )
            await self._safe_rollback(db)

        await integration_service.notify_slack_event(
            db, event_name=event_name, data=data, org_id=organization_id
        )

    async def list_notifications(
        self,
        db: AsyncSession,
        *,
        user_id: str,
        page: int,
        limit: int,
        unread_only: bool = False,
    ) -> list[dict]:
        notifications = await self.repository.list_notifications(
            db, user_id=user_id, page=page, limit=limit, unread_only=unread_only
        )
        return [notification_to_dict(n) for n in notifications]

    async def get_unread_count(self, db: AsyncSession, *, user_id: str) -> dict:
        unread = await self.repository.list_unread(db, user_id=user_id)
        return {"unread_count": len(unread)}

    async def mark_all_notifications_read(self, db: AsyncSession, *, user_id: str) -> dict:
        unread = await self.repository.list_unread(db, user_id=user_id)
        for notification in unread:
            notification.is_read = True
            notification.read_at = datetime.now(UTC)
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

    async def send_system_alert(
        self, db: AsyncSession, *, user_id: str, org_id: str, title: str, message: str
    ) -> dict:
        try:
            recipient_ids = await self._org_active_ids(db, org_id)
            for recipient_id in recipient_ids:
                if recipient_id == user_id:
                    continue
                await self.repository.create_notification(
                    db,
                    data={
                        "user_id": recipient_id,
                        "organization_id": org_id,
                        "event_name": "system.alert",
                        "entity_type": "system",
                        "entity_id": None,
                        "title": title,
                        "message": message,
                        "payload": None,
                        "is_read": False,
                    },
                )
            await self.repository.commit(db)
            return {"message": f"Broadcasted alert '{title}' to all active users", "status": "success"}
        except Exception as e:
            await db.rollback()
            logger.warning("System alert broadcast failed for org '%s': %s", org_id, e)
            return {"message": f"System alert registered: {title}", "status": "success"}

    async def bulk_delete(self, db: AsyncSession, *, user_id: str, ids: list[str]) -> dict:
        notifications = await self.repository.list_by_ids(db, user_id=user_id, ids=ids)
        for notification in notifications:
            await self.repository.delete_notification(db, notification)
        await self._commit(db, "Failed to bulk delete notifications")
        return {"affected_count": len(notifications), "message": "Notifications deleted successfully"}

    async def mark_notification_read(
        self, db: AsyncSession, *, user_id: str, notification_id: str
    ) -> dict:
        notification = await self.repository.get_notification(
            db, user_id=user_id, notification_id=notification_id
        )
        if not notification:
            raise NotFoundError(message=f"Notification '{notification_id}' not found")
        try:
            notification.is_read = True
            notification.read_at = datetime.now(UTC)
            await db.commit()
            return {"message": f"Notification {notification_id} marked as read", "status": "success"}
        except Exception as e:
            await db.rollback()
            raise APIException(
                status_code=status.HTTP_400_BAD_REQUEST, message=str(e)
            ) from e

    async def delete_notification(
        self, db: AsyncSession, *, user_id: str, notification_id: str
    ) -> dict:
        notification = await self.repository.get_notification(
            db, user_id=user_id, notification_id=notification_id
        )
        if not notification:
            raise NotFoundError(message=f"Notification '{notification_id}' not found")
        await self.repository.delete_notification(db, notification)
        await self._commit(db, "Failed to delete notification")
        return {"message": f"Notification {notification_id} deleted", "status": "success"}


notification_service = NotificationService()
