from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CalendarEventModel, User


class CalendarRepository:
    """Query layer for the CalendarEventModel domain — no business logic."""

    async def list_events(
        self,
        db: AsyncSession,
        *,
        search: str | None = None,
    ) -> Sequence[CalendarEventModel]:
        stmt = select(CalendarEventModel)
        if search and search.strip():
            stmt = stmt.where(CalendarEventModel.title.ilike(f"%{search.strip()}%"))
        stmt = stmt.order_by(CalendarEventModel.start_time.asc()).limit(50)
        res = await db.execute(stmt)
        return res.scalars().all()

    async def get_event(self, db: AsyncSession, event_id: str) -> CalendarEventModel | None:
        stmt = select(CalendarEventModel).where(CalendarEventModel.id == event_id)
        res = await db.execute(stmt)
        return res.scalars().first()

    async def create_event(self, db: AsyncSession, *, data: dict) -> CalendarEventModel:
        event = CalendarEventModel(**data)
        db.add(event)
        return event

    async def delete_event(self, db: AsyncSession, event: CalendarEventModel) -> None:
        await db.delete(event)

    async def resolve_user_id(self, db: AsyncSession) -> str:
        res = await db.execute(select(User).limit(1))
        first_user = res.scalars().first()
        if first_user:
            return first_user.id
        return "user-default-1"
