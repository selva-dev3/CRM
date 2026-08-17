from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Notification


class NotificationRepository:
    """Query layer for the Notification domain — no business logic."""

    async def list_notifications(
        self,
        db: AsyncSession,
        *,
        user_id: str,
        page: int,
        limit: int,
        unread_only: bool = False,
    ) -> Sequence[Notification]:
        stmt = select(Notification).where(Notification.user_id == user_id)
        if unread_only:
            stmt = stmt.where(Notification.is_read == False)  # noqa: E712
        stmt = stmt.order_by(Notification.created_at.desc()).offset((page - 1) * limit).limit(limit)
        res = await db.execute(stmt)
        return res.scalars().all()

    async def list_unread(self, db: AsyncSession, *, user_id: str) -> Sequence[Notification]:
        stmt = select(Notification).where(
            Notification.user_id == user_id,
            Notification.is_read == False,  # noqa: E712
        )
        res = await db.execute(stmt)
        return res.scalars().all()

    async def count_unread(self, db: AsyncSession, *, user_id: str) -> int:
        stmt = (
            select(func.count())
            .select_from(Notification)
            .where(
                Notification.user_id == user_id,
                Notification.is_read == False,  # noqa: E712
            )
        )
        res = await db.execute(stmt)
        return res.scalar_one()

    async def list_by_ids(
        self, db: AsyncSession, *, user_id: str, ids: list[str]
    ) -> Sequence[Notification]:
        stmt = select(Notification).where(
            Notification.user_id == user_id, Notification.id.in_(ids)
        )
        res = await db.execute(stmt)
        return res.scalars().all()

    async def get_notification(
        self, db: AsyncSession, *, user_id: str, notification_id: str
    ) -> Notification | None:
        stmt = select(Notification).where(
            Notification.user_id == user_id, Notification.id == notification_id
        )
        res = await db.execute(stmt)
        return res.scalars().first()

    async def exists_unread(
        self,
        db: AsyncSession,
        *,
        user_id: str,
        event_name: str | None,
        entity_type: str | None,
        entity_id: str | None,
    ) -> bool:
        stmt = select(Notification.id).where(
            Notification.user_id == user_id,
            Notification.is_read == False,  # noqa: E712
            Notification.event_name == event_name,
            Notification.entity_type == entity_type,
            Notification.entity_id == entity_id,
        )
        res = await db.execute(stmt.limit(1))
        return res.scalars().first() is not None

    async def create_notification(self, db: AsyncSession, *, data: dict) -> Notification:
        notification = Notification(**data)
        db.add(notification)
        return notification

    async def delete_notification(self, db: AsyncSession, notification: Notification) -> None:
        await db.delete(notification)

    async def commit(self, db: AsyncSession) -> None:
        await db.commit()
