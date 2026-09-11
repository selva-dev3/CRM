from __future__ import annotations

import builtins
from datetime import datetime

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Contact, Meeting, MeetingAttendee


class MeetingRepository:
    """DB query layer for the Meeting domain. No business logic here."""

    async def list(
        self,
        db: AsyncSession,
        *,
        page: int,
        limit: int,
        organization_id: str,
        search: str | None = None,
        lead_id: str | None = None,
        contact_id: str | None = None,
        company_id: str | None = None,
        deal_id: str | None = None,
    ) -> builtins.list[Meeting]:
        stmt = select(Meeting).where(Meeting.organization_id == organization_id)
        if search and search.strip():
            stmt = stmt.where(Meeting.title.ilike(f"%{search.strip()}%"))
        for column, value in (
            (Meeting.lead_id, lead_id),
            (Meeting.contact_id, contact_id),
            (Meeting.company_id, company_id),
            (Meeting.deal_id, deal_id),
        ):
            if value:
                stmt = stmt.where(column == value)
        stmt = stmt.order_by(Meeting.start_time.asc()).offset((page - 1) * limit).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def list_upcoming(
        self, db: AsyncSession, *, organization_id: str, limit: int = 10
    ) -> builtins.list[Meeting]:
        result = await db.execute(
            select(Meeting)
            .where(
                Meeting.organization_id == organization_id,
                Meeting.status == "Scheduled",
            )
            .order_by(Meeting.start_time.asc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def list_for_contact(
        self,
        db: AsyncSession,
        *,
        organization_id: str,
        contact_id: str,
        contact_email: str,
        limit: int,
        search: str | None = None,
        statuses: builtins.list[str] | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
        newest_first: bool = False,
    ) -> builtins.list[Meeting]:
        """Return explicitly linked meetings and safe legacy attendee matches."""
        normalized_email = func.lower(func.trim(contact_email))
        matching_contact_count = (
            select(func.count(Contact.id))
            .where(
                Contact.organization_id == organization_id,
                func.lower(func.trim(Contact.email)) == normalized_email,
            )
            .scalar_subquery()
        )
        stmt = (
            select(Meeting)
            .outerjoin(MeetingAttendee, MeetingAttendee.meeting_id == Meeting.id)
            .where(
                Meeting.organization_id == organization_id,
                or_(
                    Meeting.contact_id == contact_id,
                    and_(
                        Meeting.contact_id.is_(None),
                        func.lower(func.trim(MeetingAttendee.email))
                        == normalized_email,
                        matching_contact_count == 1,
                    ),
                ),
            )
            .distinct()
        )
        if search and search.strip():
            stmt = stmt.where(Meeting.title.ilike(f"%{search.strip()}%"))
        if statuses:
            stmt = stmt.where(Meeting.status.in_(statuses))
        if start is not None:
            stmt = stmt.where(Meeting.start_time >= start)
        if end is not None:
            stmt = stmt.where(Meeting.start_time < end)
        order = Meeting.start_time.desc() if newest_first else Meeting.start_time.asc()
        result = await db.execute(stmt.order_by(order).limit(limit))
        return list(result.scalars().all())

    async def get_by_id(
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
        self, db: AsyncSession, *, ids: builtins.list[str], organization_id: str
    ) -> builtins.list[Meeting]:
        result = await db.execute(
            select(Meeting).where(Meeting.id.in_(ids), Meeting.organization_id == organization_id)
        )
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
