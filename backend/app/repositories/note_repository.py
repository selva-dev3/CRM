from __future__ import annotations

import builtins

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.note import Note


class NoteRepository:
    """DB query layer for the Note entity. No business logic here."""

    async def list(
        self,
        db: AsyncSession,
        *,
        page: int,
        limit: int,
        organization_id: str,
        entity_type: str | None = None,
        search: str | None = None,
    ) -> builtins.list[Note]:
        stmt = select(Note).where(Note.organization_id == organization_id)
        if entity_type and entity_type.strip():
            stmt = stmt.where(Note.entity_type == entity_type.strip())
        if search and search.strip():
            stmt = stmt.where(Note.content.ilike(f"%{search.strip()}%"))
        stmt = stmt.order_by(Note.created_at.desc()).offset((page - 1) * limit).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def list_by_entity(
        self,
        db: AsyncSession,
        *,
        entity_type: str,
        entity_id: str,
        organization_id: str,
    ) -> builtins.list[Note]:
        result = await db.execute(
            select(Note)
            .where(
                Note.entity_type == entity_type,
                Note.entity_id == entity_id,
                Note.organization_id == organization_id,
            )
            .order_by(Note.created_at.desc())
        )
        return list(result.scalars().all())

    async def list_pinned(
        self, db: AsyncSession, organization_id: str
    ) -> builtins.list[Note]:
        result = await db.execute(
            select(Note).where(Note.is_pinned, Note.organization_id == organization_id)
        )
        return list(result.scalars().all())

    async def get_by_id(
        self, db: AsyncSession, note_id: str, organization_id: str
    ) -> Note | None:
        result = await db.execute(
            select(Note).where(Note.id == note_id, Note.organization_id == organization_id)
        )
        return result.scalars().first()

    async def list_by_ids(
        self, db: AsyncSession, ids: builtins.list[str], organization_id: str
    ) -> builtins.list[Note]:
        result = await db.execute(
            select(Note).where(Note.id.in_(ids), Note.organization_id == organization_id)
        )
        return list(result.scalars().all())

    async def create(
        self,
        db: AsyncSession,
        *,
        organization_id: str,
        entity_type: str,
        entity_id: str,
        content: str,
        created_by: str,
    ) -> Note:
        note = Note(
            organization_id=organization_id,
            entity_type=entity_type,
            entity_id=entity_id,
            content=content,
            created_by=created_by,
        )
        db.add(note)
        return note

    async def delete(self, db: AsyncSession, note: Note) -> None:
        await db.delete(note)
