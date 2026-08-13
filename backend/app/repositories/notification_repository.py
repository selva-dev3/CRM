from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Notification


class NotificationRepository:
    """Query layer for the Notification domain — no business logic."""

    async def list_notifications(
        self,
        db: AsyncSession,
        *,
        page: int,
        limit: int,
        unread_only: bool = False,
    ) -> Sequence[Notification]:
        stmt = select(Notification)
        if unread_only:
            stmt = stmt.where(Notification.is_read == False)  # noqa: E712
        stmt = stmt.order_by(Notification.created_at.desc()).offset((page - 1) * limit).limit(limit)
        res = await db.execute(stmt)
        return res.scalars().all()

    async def list_unread(self, db: AsyncSession) -> Sequence[Notification]:
        stmt = select(Notification).where(Notification.is_read == False)  # noqa: E712
        res = await db.execute(stmt)
        return res.scalars().all()

    async def list_by_ids(self, db: AsyncSession, ids: list[str]) -> Sequence[Notification]:
        stmt = select(Notification).where(Notification.id.in_(ids))
        res = await db.execute(stmt)
        return res.scalars().all()

    async def get_notification(
        self, db: AsyncSession, notification_id: str
    ) -> Optional[Notification]:
        stmt = select(Notification).where(Notification.id == notification_id)
        res = await db.execute(stmt)
        return res.scalars().first()

    async def create_notification(self, db: AsyncSession, *, data: dict) -> Notification:
        notification = Notification(**data)
        db.add(notification)
        return notification

    async def delete_notification(self, db: AsyncSession, notification: Notification) -> None:
        await db.delete(notification)