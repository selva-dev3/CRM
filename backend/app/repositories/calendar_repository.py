from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.record_access import RecordAccessContext, record_access_filter
from app.models import CalendarEventModel


class CalendarRepository:
    """Query layer for the CalendarEventModel domain — no business logic."""

    async def list_events(
        self,
        db: AsyncSession,
        *,
        organization_id: str,
        search: str | None = None,
        page: int = 1,
        limit: int = 50,
        start: datetime | None = None,
        end: datetime | None = None,
        access: RecordAccessContext | None = None,
    ) -> Sequence[CalendarEventModel]:
        stmt = select(CalendarEventModel).where(
            CalendarEventModel.organization_id == organization_id
        )
        stmt = self._apply_filters(stmt, search=search, start=start, end=end, access=access)
        stmt = (
            stmt.order_by(CalendarEventModel.start_time.asc(), CalendarEventModel.id.asc())
            .offset((page - 1) * limit)
            .limit(limit)
        )
        res = await db.execute(stmt)
        return res.scalars().all()

    async def count_events(
        self,
        db: AsyncSession,
        *,
        organization_id: str,
        search: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
        access: RecordAccessContext | None = None,
    ) -> int:
        stmt = (
            select(func.count())
            .select_from(CalendarEventModel)
            .where(CalendarEventModel.organization_id == organization_id)
        )
        stmt = self._apply_filters(stmt, search=search, start=start, end=end, access=access)
        return int((await db.execute(stmt)).scalar_one())

    @staticmethod
    def _apply_filters(stmt, *, search, start, end, access):
        if search and search.strip():
            stmt = stmt.where(CalendarEventModel.title.ilike(f"%{search.strip()}%"))
        if start is not None:
            stmt = stmt.where(CalendarEventModel.end_time >= start)
        if end is not None:
            stmt = stmt.where(CalendarEventModel.start_time <= end)
        access_filter = record_access_filter(
            access,
            assigned_column=CalendarEventModel.user_id,
            created_column=CalendarEventModel.user_id,
        )
        return stmt.where(access_filter) if access_filter is not None else stmt

    async def get_event(
        self,
        db: AsyncSession,
        event_id: str,
        organization_id: str,
        *,
        access: RecordAccessContext | None = None,
    ) -> CalendarEventModel | None:
        stmt = select(CalendarEventModel).where(
            CalendarEventModel.id == event_id,
            CalendarEventModel.organization_id == organization_id,
        )
        access_filter = record_access_filter(
            access,
            assigned_column=CalendarEventModel.user_id,
            created_column=CalendarEventModel.user_id,
        )
        if access_filter is not None:
            stmt = stmt.where(access_filter)
        res = await db.execute(stmt)
        return res.scalars().first()

    async def create_event(self, db: AsyncSession, *, data: dict) -> CalendarEventModel:
        event = CalendarEventModel(**data)
        db.add(event)
        return event

    async def delete_event(self, db: AsyncSession, event: CalendarEventModel) -> None:
        await db.delete(event)
