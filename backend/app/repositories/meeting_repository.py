from __future__ import annotations

import builtins

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Meeting, MeetingAttendee


class MeetingRepository:
    """DB query layer for the Meeting domain. No business logic here."""

    async def list(
        self,
        db: AsyncSession,
        *,
        page: int,
        limit: int,
        search: str | None = None,
    ) -> builtins.list[Meeting]:
        stmt = select(Meeting)
        if search and search.strip():
            stmt = stmt.where(Meeting.title.ilike(f"%{search.strip()}%"))
        stmt = stmt.order_by(Meeting.start_time.asc()).offset((page - 1) * limit).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def list_upcoming(self, db: AsyncSession, limit: int = 10) -> builtins.list[Meeting]:
        result = await db.execute(select(Meeting).order_by(Meeting.start_time.asc()).limit(limit))
        return list(result.scalars().all())

    async def get_by_id(self, db: AsyncSession, meeting_id: str) -> Meeting | None:
        result = await db.execute(select(Meeting).where(Meeting.id == meeting_id))
        return result.scalars().first()

    async def get_by_id_scoped(
        self, db: AsyncSession, *, meeting_id: str, organization_id: str
    ) -> Meeting | None:
        result = await db.execute(
            select(Meeting).where(
                Meeting.id == meeting_id,
                Meeting.organization_id == organization_id,
            )
        )
        return result.scalars().first()

    async def list_by_ids(
        self, db: AsyncSession, ids: builtins.list[str]
    ) -> builtins.list[Meeting]:
        result = await db.execute(select(Meeting).where(Meeting.id.in_(ids)))
        return list(result.scalars().all())

    async def create(self, db: AsyncSession, *, data: dict) -> Meeting:
        meeting = Meeting(**data)
        db.add(meeting)
        return meeting

    async def delete(self, db: AsyncSession, meeting: Meeting) -> None:
        await db.delete(meeting)

    async def list_attendee_emails(self, db: AsyncSession, meeting_id: str) -> builtins.list[str]:
        result = await db.execute(
            select(MeetingAttendee).where(MeetingAttendee.meeting_id == meeting_id)
        )
        return [a.email for a in result.scalars().all()]

    async def get_attendee(
        self, db: AsyncSession, *, meeting_id: str, email: str
    ) -> MeetingAttendee | None:
        result = await db.execute(
            select(MeetingAttendee).where(
                MeetingAttendee.meeting_id == meeting_id, MeetingAttendee.email == email
            )
        )
        return result.scalars().first()

    async def create_attendee(
        self, db: AsyncSession, *, meeting_id: str, email: str, rsvp_status: str | None = None
    ) -> MeetingAttendee:
        attendee = MeetingAttendee(meeting_id=meeting_id, email=email, rsvp_status=rsvp_status)
        db.add(attendee)
        return attendee
