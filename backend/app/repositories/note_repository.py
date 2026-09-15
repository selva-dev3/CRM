from __future__ import annotations

import builtins
from collections.abc import Mapping
from typing import Any

from sqlalchemy import and_, false, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.core.record_access import RecordAccessContext, record_access_filter
from app.models import Company, Contact, Deal, Lead, User
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
            stmt = stmt.where(self._entity_type_filter(entity_type))
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
            stmt = stmt.where(self._entity_type_filter(entity_type))
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
                self._entity_type_filter(entity_type),
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
                self._entity_type_filter(entity_type),
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

    async def get_display_context(
        self,
        db: AsyncSession,
        notes: builtins.list[Note],
        organization_id: str,
    ) -> dict[str, dict[str, str | None]]:
        note_ids = [note.id for note in notes]
        if not note_ids:
            return {}
        stmt = (
            select(
                Note.id,
                Lead.contact_name.label("lead_name"),
                Lead.title.label("lead_title"),
                Contact.name.label("contact_name"),
                Company.name.label("company_name"),
                Deal.title.label("deal_title"),
                User.name.label("creator_name"),
                User.email.label("creator_email"),
            )
            .select_from(Note)
            .outerjoin(
                Lead,
                and_(Lead.id == Note.lead_id, Lead.organization_id == organization_id),
            )
            .outerjoin(
                Contact,
                and_(Contact.id == Note.contact_id, Contact.organization_id == organization_id),
            )
            .outerjoin(
                Company,
                and_(Company.id == Note.company_id, Company.organization_id == organization_id),
            )
            .outerjoin(
                Deal,
                and_(Deal.id == Note.deal_id, Deal.organization_id == organization_id),
            )
            .outerjoin(
                User,
                and_(
                    User.id == Note.created_by,
                    or_(User.organization_id == organization_id, User.is_platform_admin.is_(True)),
                ),
            )
            .where(Note.id.in_(note_ids), Note.organization_id == organization_id)
        )
        rows = (await db.execute(stmt)).mappings().all()
        return {
            row["id"]: {
                "lead_name": row["lead_name"],
                "lead_title": row["lead_title"],
                "contact_name": row["contact_name"],
                "company_name": row["company_name"],
                "deal_title": row["deal_title"],
                "creator_name": row["creator_name"],
                "creator_email": row["creator_email"],
            }
            for row in rows
        }

    @staticmethod
    def _entity_type_filter(entity_type: str):
        normalized = entity_type.strip().casefold()
        return func.lower(func.trim(Note.entity_type)) == normalized

    @staticmethod
    def _apply_access(stmt, access: RecordAccessContext | None):
        access_filter = record_access_filter(
            access, assigned_column=Note.created_by, created_column=Note.created_by
        )
        return stmt.where(access_filter) if access_filter is not None else stmt

    @staticmethod
    def _target_access_filter(
        target_access: Mapping[str, RecordAccessContext | None] | None,
    ):
        if target_access is None:
            return None
        specs = (
            ("leads", Note.lead_id, Lead.assigned_to, Lead.created_by),
            ("contacts", Note.contact_id, Contact.owner_id, Contact.created_by),
            ("companies", Note.company_id, Company.owner_id, Company.created_by),
            ("deals", Note.deal_id, Deal.assigned_to, Deal.created_by),
        )
        clauses: builtins.list[ColumnElement[bool]] = []
        for module, note_fk, assigned, created in specs:
            target_filter = record_access_filter(
                target_access[module], assigned_column=assigned, created_column=created
            )
            if target_filter is None:
                clauses.append(note_fk.is_not(None))
            else:
                model: Any = {
                    "leads": Lead,
                    "contacts": Contact,
                    "companies": Company,
                    "deals": Deal,
                }[module]
                clauses.append(
                    and_(
                        note_fk.is_not(None),
                        note_fk.in_(select(model.id).where(target_filter)),
                    )
                )
        return or_(*clauses) if clauses else false()

    @classmethod
    def _apply_target_access(
        cls,
        stmt,
        target_access: Mapping[str, RecordAccessContext | None] | None,
    ):
        target_filter = cls._target_access_filter(target_access)
        return stmt.where(target_filter) if target_filter is not None else stmt
