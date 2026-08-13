from __future__ import annotations

from typing import Optional

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
        entity_type: Optional[str] = None,
        search: Optional[str] = None,
    ) -> list[Note]:
        stmt = select(Note)
        if entity_type and entity_type.strip():
            stmt = stmt.where(Note.entity_type == entity_type.strip())
        if search and search.strip():
            stmt = stmt.where(Note.content.ilike(f"%{search.strip()}%"))
        stmt = stmt.order_by(Note.created_at.desc()).offset((page - 1) * limit).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def list_by_entity(
        self, db: AsyncSession, *, entity_type: str, entity_id: str
    ) -> list[Note]:
        result = await db.execute(
            select(Note)
            .where(Note.entity_type == entity_type, Note.entity_id == entity_id)
            .order_by(Note.created_at.desc())
        )
        return list(result.scalars().all())

    async def list_pinned(self, db: AsyncSession) -> list[Note]:
        result = await db.execute(select(Note).where(Note.is_pinned == True))
        return list(result.scalars().all())

    async def get_by_id(self, db: AsyncSession, note_id: str) -> Optional[Note]:
        result = await db.execute(select(Note).where(Note.id == note_id))
        return result.scalars().first()

    async def list_by_ids(self, db: AsyncSession, ids: list[str]) -> list[Note]:
        result = await db.execute(select(Note).where(Note.id.in_(ids)))
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