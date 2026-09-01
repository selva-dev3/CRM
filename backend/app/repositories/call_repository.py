from __future__ import annotations

import builtins

from sqlalchemy import select
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
        search: str | None = None,
        call_type: str | None = None,
    ) -> builtins.list[CallLog]:
        stmt = select(CallLog)
        if search and search.strip():
            stmt = stmt.where(CallLog.notes.ilike(f"%{search.strip()}%"))
        if call_type and call_type.strip():
            stmt = stmt.where(CallLog.call_type == call_type.strip())
        stmt = stmt.order_by(CallLog.timestamp.desc()).offset((page - 1) * limit).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_by_id(self, db: AsyncSession, call_id: str) -> CallLog | None:
        result = await db.execute(select(CallLog).where(CallLog.id == call_id))
        return result.scalars().first()

    async def list_by_ids(
        self, db: AsyncSession, ids: builtins.list[str]
    ) -> builtins.list[CallLog]:
        result = await db.execute(select(CallLog).where(CallLog.id.in_(ids)))
        return list(result.scalars().all())

    async def create(self, db: AsyncSession, *, data: dict) -> CallLog:
        call = CallLog(**data)
        db.add(call)
        return call

    async def delete(self, db: AsyncSession, call: CallLog) -> None:
        await db.delete(call)
