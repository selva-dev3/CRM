from __future__ import annotations

import builtins
from datetime import datetime

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CallLog


class CallRepository:
    """DB query layer for the CallLog entity. No business logic here."""

    async def list(
        self,
        db: AsyncSession,
        *,
        page: int,
        limit: int,
        organization_id: str,
        search: str | None = None,
        call_type: str | None = None,
        lead_id: str | None = None,
        contact_id: str | None = None,
        company_id: str | None = None,
        deal_id: str | None = None,
    ) -> builtins.list[CallLog]:
        stmt = select(CallLog).where(CallLog.organization_id == organization_id)
        if search and search.strip():
            term = f"%{search.strip()}%"
            stmt = stmt.where(or_(CallLog.subject.ilike(term), CallLog.notes.ilike(term)))
        if call_type and call_type.strip():
            stmt = stmt.where(CallLog.call_type == call_type.strip())
        for column, value in (
            (CallLog.lead_id, lead_id),
            (CallLog.contact_id, contact_id),
            (CallLog.company_id, company_id),
            (CallLog.deal_id, deal_id),
        ):
            if value:
                stmt = stmt.where(column == value)
        stmt = (
            stmt.order_by(CallLog.timestamp.desc(), CallLog.id.desc())
            .offset((page - 1) * limit)
            .limit(limit)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def count(
        self,
        db: AsyncSession,
        *,
        organization_id: str,
        search: str | None = None,
        call_type: str | None = None,
        lead_id: str | None = None,
        contact_id: str | None = None,
        company_id: str | None = None,
        deal_id: str | None = None,
    ) -> int:
        stmt = (
            select(func.count())
            .select_from(CallLog)
            .where(CallLog.organization_id == organization_id)
        )
        if search and search.strip():
            term = f"%{search.strip()}%"
            stmt = stmt.where(or_(CallLog.subject.ilike(term), CallLog.notes.ilike(term)))
        if call_type and call_type.strip():
            stmt = stmt.where(CallLog.call_type == call_type.strip())
        for column, value in (
            (CallLog.lead_id, lead_id),
            (CallLog.contact_id, contact_id),
            (CallLog.company_id, company_id),
            (CallLog.deal_id, deal_id),
        ):
            if value:
                stmt = stmt.where(column == value)
        return int((await db.execute(stmt)).scalar_one())

    async def get_by_id(
        self, db: AsyncSession, call_id: str, organization_id: str
    ) -> CallLog | None:
        result = await db.execute(
            select(CallLog).where(
                CallLog.id == call_id,
                CallLog.organization_id == organization_id,
            )
        )
        return result.scalars().first()

    async def get_by_idempotency_key(
        self,
        db: AsyncSession,
        *,
        organization_id: str,
        created_by: str,
        idempotency_key: str,
    ) -> CallLog | None:
        result = await db.execute(
            select(CallLog).where(
                CallLog.organization_id == organization_id,
                CallLog.created_by == created_by,
                CallLog.idempotency_key == idempotency_key,
            )
        )
        return result.scalars().first()

    async def list_by_ids(
        self, db: AsyncSession, ids: builtins.list[str], organization_id: str
    ) -> builtins.list[CallLog]:
        result = await db.execute(
            select(CallLog).where(
                CallLog.id.in_(ids),
                CallLog.organization_id == organization_id,
            )
        )
        return list(result.scalars().all())

    async def list_by_contact(
        self,
        db: AsyncSession,
        *,
        contact_id: str,
        organization_id: str,
        page: int | None = None,
        limit: int | None = None,
        search: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> builtins.list[CallLog]:
        stmt = select(CallLog).where(
            CallLog.contact_id == contact_id,
            CallLog.organization_id == organization_id,
        )
        if search and search.strip():
            stmt = stmt.where(CallLog.subject.ilike(f"%{search.strip()}%"))
        if start is not None:
            stmt = stmt.where(CallLog.timestamp >= start)
        if end is not None:
            stmt = stmt.where(CallLog.timestamp < end)
        stmt = stmt.order_by(CallLog.timestamp.desc(), CallLog.id.desc())
        if page is not None and limit is not None:
            stmt = stmt.offset((page - 1) * limit).limit(limit)
        elif limit is not None:
            stmt = stmt.limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def count_by_contact(
        self, db: AsyncSession, *, contact_id: str, organization_id: str
    ) -> int:
        stmt = (
            select(func.count())
            .select_from(CallLog)
            .where(
                CallLog.contact_id == contact_id,
                CallLog.organization_id == organization_id,
            )
        )
        return int((await db.execute(stmt)).scalar_one())

    async def create(self, db: AsyncSession, *, data: dict) -> CallLog:
        call = CallLog(**data)
        db.add(call)
        return call

    async def update(self, db: AsyncSession, call: CallLog, *, data: dict) -> CallLog:
        for field, value in data.items():
            setattr(call, field, value)
        return call

    async def delete(self, db: AsyncSession, call: CallLog) -> None:
        await db.delete(call)
