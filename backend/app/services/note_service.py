from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIException, NotFoundError
from app.models import User
from app.models.note import Note
from app.repositories.note_repository import NoteRepository
from app.services.org_service import organization_service
from app.services.record_access_service import record_access_service

NOTE_ENTITY_TYPES = frozenset({"lead", "contact", "company", "deal"})


def normalize_note_entity_type(entity_type: str | None) -> str:
    normalized = (entity_type or "").strip().casefold()
    return normalized if normalized in NOTE_ENTITY_TYPES else "general"


def _note_entity_label(display_context: dict[str, str | None], entity_type: str) -> str | None:
    if entity_type == "lead":
        value = display_context.get("lead_name") or display_context.get("lead_title")
    else:
        value = display_context.get(f"{entity_type}_name") or display_context.get(
            f"{entity_type}_title"
        )
    return value.strip() or None if value else None


def note_to_dict(note: Note, display_context: dict[str, str | None] | None = None) -> dict:
    context = display_context or {}
    entity_type = normalize_note_entity_type(note.entity_type)
    creator_name = context.get("creator_name") or context.get("creator_email")
    return {
        "id": note.id,
        "entity_type": entity_type,
        "entity_id": note.entity_id,
        "entity_label": _note_entity_label(context, entity_type),
        "content": note.content,
        "is_pinned": getattr(note, "is_pinned", False),
        "created_by": note.created_by,
        "created_by_name": creator_name.strip() or None if creator_name else None,
        "created_at": str(note.created_at),
    }


class NoteService:
    """Business logic for notes, shared across the notes router and the
    entity-scoped note endpoints (contacts, companies, etc.).
    """

    def __init__(self, repository: NoteRepository | None = None) -> None:
        self.repository = repository or NoteRepository()

    async def _access(self, db: AsyncSession, current_user: User):
        from app.services.crm_relationship_service import resolve_crm_record_access

        return (
            await record_access_service.resolve(db, current_user, "notes"),
            await resolve_crm_record_access(db, current_user),
        )

    async def _commit(self, db: AsyncSession, error_message: str) -> None:
        try:
            await db.commit()
        except Exception as e:
            await db.rollback()
            raise APIException(
                status_code=status.HTTP_400_BAD_REQUEST, message=error_message
            ) from e

    async def _serialize_notes(
        self, db: AsyncSession, notes: list[Note], organization_id: str
    ) -> list[dict]:
        context_by_note = await self.repository.get_display_context(db, notes, organization_id)
        return [note_to_dict(note, context_by_note.get(note.id)) for note in notes]

    async def list_notes(
        self,
        db: AsyncSession,
        *,
        page: int,
        limit: int,
        entity_type: str | None = None,
        search: str | None = None,
        current_user: User,
    ) -> list[dict]:
        org_id = await organization_service.resolve_valid_org_id(db, current_user)
        access, target_access = await self._access(db, current_user)
        notes = await self.repository.list(
            db,
            page=page,
            limit=limit,
            organization_id=org_id,
            entity_type=normalize_note_entity_type(entity_type) if entity_type else None,
            search=search,
            access=access,
            target_access=target_access,
        )
        return await self._serialize_notes(db, notes, org_id)

    async def count_notes(
        self,
        db: AsyncSession,
        *,
        entity_type: str | None = None,
        search: str | None = None,
        current_user: User,
    ) -> int:
        org_id = await organization_service.resolve_valid_org_id(db, current_user)
        access, target_access = await self._access(db, current_user)
        return await self.repository.count(
            db,
            organization_id=org_id,
            entity_type=normalize_note_entity_type(entity_type) if entity_type else None,
            search=search,
            access=access,
            target_access=target_access,
        )

    async def create_note(
        self,
        db: AsyncSession,
        *,
        entity_type: str,
        entity_id: str,
        content: str,
        current_user: User,
    ) -> dict:
        org_id = await organization_service.resolve_valid_org_id(db, current_user)
        from app.services.crm_relationship_service import (
            resolve_crm_record_access,
            validate_polymorphic_crm_entity,
        )

        normalized_entity_type = normalize_note_entity_type(entity_type)
        relationships = await validate_polymorphic_crm_entity(
            db,
            organization_id=org_id,
            entity_type=normalized_entity_type,
            entity_id=entity_id,
            access_by_module=await resolve_crm_record_access(db, current_user),
        )
        note = await self.repository.create(
            db,
            organization_id=org_id,
            entity_type=normalized_entity_type,
            entity_id=entity_id,
            content=content,
            created_by=current_user.id,
            relationships=relationships,
        )
        await self._commit(db, "Failed to create note")
        await db.refresh(note)
        return (await self._serialize_notes(db, [note], org_id))[0]

    async def list_pinned(self, db: AsyncSession, current_user: User) -> list[dict]:
        org_id = await organization_service.resolve_valid_org_id(db, current_user)
        access, target_access = await self._access(db, current_user)
        notes = await self.repository.list_pinned(
            db, org_id, access=access, target_access=target_access
        )
        return await self._serialize_notes(db, notes, org_id)

    async def get_notes_by_entity(
        self,
        db: AsyncSession,
        *,
        entity_type: str,
        entity_id: str,
        current_user: User,
        page: int | None = None,
        limit: int | None = None,
    ) -> list[dict]:
        org_id = await organization_service.resolve_valid_org_id(db, current_user)
        access, target_access = await self._access(db, current_user)
        notes = await self.repository.list_by_entity(
            db,
            entity_type=normalize_note_entity_type(entity_type),
            entity_id=entity_id,
            organization_id=org_id,
            page=page,
            limit=limit,
            access=access,
            target_access=target_access,
        )
        return await self._serialize_notes(db, notes, org_id)

    async def bulk_delete(self, db: AsyncSession, ids: list[str], current_user: User) -> dict:
        org_id = await organization_service.resolve_valid_org_id(db, current_user)
        access, target_access = await self._access(db, current_user)
        notes = await self.repository.list_by_ids(
            db, ids, org_id, access=access, target_access=target_access
        )
        for note in notes:
            await self.repository.delete(db, note)
        await self._commit(db, "Failed to bulk delete notes")
        return {"affected_count": len(notes), "message": "Notes deleted successfully"}

    async def get_note(self, db: AsyncSession, note_id: str, current_user: User) -> dict:
        org_id = await organization_service.resolve_valid_org_id(db, current_user)
        access, target_access = await self._access(db, current_user)
        note = await self.repository.get_by_id(
            db, note_id, org_id, access=access, target_access=target_access
        )
        if not note:
            raise NotFoundError(message=f"Note '{note_id}' not found")
        return (await self._serialize_notes(db, [note], org_id))[0]

    async def update_note(
        self, db: AsyncSession, note_id: str, content: str, current_user: User
    ) -> dict:
        org_id = await organization_service.resolve_valid_org_id(db, current_user)
        access, target_access = await self._access(db, current_user)
        note = await self.repository.get_by_id(
            db, note_id, org_id, access=access, target_access=target_access
        )
        if not note:
            raise NotFoundError(message=f"Note '{note_id}' not found")
        note.content = content
        await self._commit(db, "Failed to update note")
        await db.refresh(note)
        return (await self._serialize_notes(db, [note], org_id))[0]

    async def delete_note(self, db: AsyncSession, note_id: str, current_user: User) -> dict:
        org_id = await organization_service.resolve_valid_org_id(db, current_user)
        access, target_access = await self._access(db, current_user)
        note = await self.repository.get_by_id(
            db, note_id, org_id, access=access, target_access=target_access
        )
        if not note:
            raise NotFoundError(message=f"Note '{note_id}' not found")
        await self.repository.delete(db, note)
        await self._commit(db, "Failed to delete note")
        return {"message": f"Note {note_id} deleted successfully", "status": "success"}

    async def set_pinned(
        self, db: AsyncSession, note_id: str, pinned: bool, current_user: User
    ) -> dict:
        org_id = await organization_service.resolve_valid_org_id(db, current_user)
        access, target_access = await self._access(db, current_user)
        note = await self.repository.get_by_id(
            db, note_id, org_id, access=access, target_access=target_access
        )
        if not note:
            raise NotFoundError(message=f"Note '{note_id}' not found")
        note.is_pinned = pinned
        await self._commit(db, "Failed to pin note")
        return {
            "message": f"Note {note_id} {'pinned' if pinned else 'unpinned'}",
            "status": "success",
        }

    async def list_for_entity(
        self,
        db: AsyncSession,
        *,
        entity_type: str,
        entity_id: str,
        page: int | None = None,
        limit: int | None = None,
        current_user: User,
    ) -> list[dict]:
        org_id = await organization_service.resolve_valid_org_id(db, current_user)
        access, target_access = await self._access(db, current_user)
        notes = await self.repository.list_by_entity(
            db,
            entity_type=normalize_note_entity_type(entity_type),
            entity_id=entity_id,
            organization_id=org_id,
            page=page,
            limit=limit,
            access=access,
            target_access=target_access,
        )
        return await self._serialize_notes(db, notes, org_id)

    async def count_for_entity(
        self,
        db: AsyncSession,
        *,
        entity_type: str,
        entity_id: str,
        current_user: User,
    ) -> int:
        org_id = await organization_service.resolve_valid_org_id(db, current_user)
        access, target_access = await self._access(db, current_user)
        return await self.repository.count_by_entity(
            db,
            entity_type=normalize_note_entity_type(entity_type),
            entity_id=entity_id,
            organization_id=org_id,
            access=access,
            target_access=target_access,
        )

    async def add_for_entity(
        self,
        db: AsyncSession,
        *,
        entity_type: str,
        entity_id: str,
        content: str,
        current_user: User,
    ) -> dict:
        org_id = await organization_service.resolve_valid_org_id(db, current_user)
        from app.services.crm_relationship_service import (
            resolve_crm_record_access,
            validate_polymorphic_crm_entity,
        )

        normalized_entity_type = normalize_note_entity_type(entity_type)
        relationships = await validate_polymorphic_crm_entity(
            db,
            organization_id=org_id,
            entity_type=normalized_entity_type,
            entity_id=entity_id,
            access_by_module=await resolve_crm_record_access(db, current_user),
        )
        note = await self.repository.create(
            db,
            organization_id=org_id,
            entity_type=normalized_entity_type,
            entity_id=entity_id,
            content=content,
            created_by=current_user.id,
            relationships=relationships,
        )
        await self._commit(db, "Failed to add note")
        await db.refresh(note)
        return (await self._serialize_notes(db, [note], org_id))[0]


note_service = NoteService()
