from __future__ import annotations

import builtins

from sqlalchemy import and_, false, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.record_access import RecordAccessContext, record_access_filter
from app.models import Company, Contact, Deal, Lead
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
        access: RecordAccessContext | None = None,
        target_access: dict[str, RecordAccessContext] | None = None,
    ) -> builtins.list[Note]:
        stmt = select(Note).where(Note.organization_id == organization_id)
        stmt = self._apply_access(stmt, access)
        stmt = self._apply_target_access(stmt, target_access)
        if entity_type and entity_type.strip():
            stmt = stmt.where(Note.entity_type == entity_type.strip())
        if search and search.strip():
            stmt = stmt.where(Note.content.ilike(f"%{search.strip()}%"))
        stmt = (
            stmt.order_by(Note.created_at.desc(), Note.id.desc())
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
        entity_type: str | None = None,
        search: str | None = None,
        access: RecordAccessContext | None = None,
        target_access: dict[str, RecordAccessContext] | None = None,
    ) -> int:
        stmt = select(func.count()).select_from(Note).where(Note.organization_id == organization_id)
        stmt = self._apply_access(stmt, access)
        stmt = self._apply_target_access(stmt, target_access)
        if entity_type and entity_type.strip():
            stmt = stmt.where(Note.entity_type == entity_type.strip())
        if search and search.strip():
            stmt = stmt.where(Note.content.ilike(f"%{search.strip()}%"))
        return int((await db.execute(stmt)).scalar_one())

    async def list_by_entity(
        self,
        db: AsyncSession,
        *,
        entity_type: str,
        entity_id: str,
        organization_id: str,
        page: int | None = None,
        limit: int | None = None,
        access: RecordAccessContext | None = None,
        target_access: dict[str, RecordAccessContext] | None = None,
    ) -> builtins.list[Note]:
        stmt = (
            select(Note)
            .where(
                Note.entity_type == entity_type,
                Note.entity_id == entity_id,
                Note.organization_id == organization_id,
            )
            .order_by(Note.created_at.desc(), Note.id.desc())
        )
        stmt = self._apply_access(stmt, access)
        stmt = self._apply_target_access(stmt, target_access)
        if page is not None and limit is not None:
            stmt = stmt.offset((page - 1) * limit).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def count_by_entity(
        self,
        db: AsyncSession,
        *,
        entity_type: str,
        entity_id: str,
        organization_id: str,
        access: RecordAccessContext | None = None,
        target_access: dict[str, RecordAccessContext] | None = None,
    ) -> int:
        stmt = (
            select(func.count())
            .select_from(Note)
            .where(
                Note.entity_type == entity_type,
                Note.entity_id == entity_id,
                Note.organization_id == organization_id,
            )
        )
        stmt = self._apply_access(stmt, access)
        stmt = self._apply_target_access(stmt, target_access)
        return int((await db.execute(stmt)).scalar_one())

    async def list_pinned(
        self,
        db: AsyncSession,
        organization_id: str,
        *,
        access: RecordAccessContext | None = None,
        target_access: dict[str, RecordAccessContext] | None = None,
    ) -> builtins.list[Note]:
        stmt = select(Note).where(Note.is_pinned, Note.organization_id == organization_id)
        stmt = self._apply_access(stmt, access)
        result = await db.execute(self._apply_target_access(stmt, target_access))
        return list(result.scalars().all())

    async def get_by_id(
        self,
        db: AsyncSession,
        note_id: str,
        organization_id: str,
        *,
        access: RecordAccessContext | None = None,
        target_access: dict[str, RecordAccessContext] | None = None,
    ) -> Note | None:
        stmt = select(Note).where(Note.id == note_id, Note.organization_id == organization_id)
        stmt = self._apply_access(stmt, access)
        result = await db.execute(self._apply_target_access(stmt, target_access))
        return result.scalars().first()

    async def list_by_ids(
        self,
        db: AsyncSession,
        ids: builtins.list[str],
        organization_id: str,
        *,
        access: RecordAccessContext | None = None,
        target_access: dict[str, RecordAccessContext] | None = None,
    ) -> builtins.list[Note]:
        stmt = select(Note).where(Note.id.in_(ids), Note.organization_id == organization_id)
        stmt = self._apply_access(stmt, access)
        result = await db.execute(self._apply_target_access(stmt, target_access))
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
        relationships: dict[str, str | None] | None = None,
    ) -> Note:
        note = Note(
            organization_id=organization_id,
            entity_type=entity_type,
            entity_id=entity_id,
            content=content,
            created_by=created_by,
            **(relationships or {}),
        )
        db.add(note)
        return note

    async def delete(self, db: AsyncSession, note: Note) -> None:
        await db.delete(note)

    @staticmethod
    def _apply_access(stmt, access: RecordAccessContext | None):
        access_filter = record_access_filter(
            access, assigned_column=Note.created_by, created_column=Note.created_by
        )
        return stmt.where(access_filter) if access_filter is not None else stmt

    @staticmethod
    def _target_access_filter(target_access: dict[str, RecordAccessContext] | None):
        if target_access is None:
            return None
        specs = (
            ("leads", Note.lead_id, Lead.assigned_to, Lead.created_by),
            ("contacts", Note.contact_id, Contact.owner_id, Contact.created_by),
            ("companies", Note.company_id, Company.owner_id, Company.created_by),
            ("deals", Note.deal_id, Deal.assigned_to, Deal.created_by),
        )
        clauses = []
        for module, note_fk, assigned, created in specs:
            target_filter = record_access_filter(
                target_access[module], assigned_column=assigned, created_column=created
            )
            if target_filter is None:
                clauses.append(note_fk.is_not(None))
            else:
                model = {"leads": Lead, "contacts": Contact, "companies": Company, "deals": Deal}[
                    module
                ]
                clauses.append(
                    and_(
                        note_fk.is_not(None),
                        note_fk.in_(select(model.id).where(target_filter)),
                    )
                )
        return or_(*clauses) if clauses else false()

    @classmethod
    def _apply_target_access(
        cls, stmt, target_access: dict[str, RecordAccessContext] | None
    ):
        target_filter = cls._target_access_filter(target_access)
        return stmt.where(target_filter) if target_filter is not None else stmt
