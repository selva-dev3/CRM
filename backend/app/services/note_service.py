from typing import Optional

from fastapi import status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIException, NotFoundError
from app.models import User
from app.models.note import Note
from app.repositories.note_repository import NoteRepository
from app.services.org_service import organization_service


def note_to_dict(note: Note) -> dict:
    return {
        "id": note.id,
        "entity_type": note.entity_type or "General",
        "entity_id": note.entity_id or "General",
        "content": note.content,
        "is_pinned": getattr(note, "is_pinned", False),
        "created_by": note.created_by or "Sales Admin",
        "created_at": str(note.created_at),
    }


class NoteService:
    """Business logic for notes, shared across the notes router and the
    entity-scoped note endpoints (contacts, companies, etc.).
    """

    def __init__(self, repository: Optional[NoteRepository] = None) -> None:
        self.repository = repository or NoteRepository()

    async def _commit(self, db: AsyncSession, error_message: str) -> None:
        try:
            await db.commit()
        except Exception as e:
            await db.rollback()
            raise APIException(
                status_code=status.HTTP_400_BAD_REQUEST, message=error_message
            ) from e

    async def _resolve_user_id(self, db: AsyncSession) -> str:
        result = await db.execute(select(User).limit(1))
        user = result.scalars().first()
        if user:
            return user.id
        return "user-default-1"

    async def list_notes(
        self,
        db: AsyncSession,
        *,
        page: int,
        limit: int,
        entity_type: Optional[str] = None,
        search: Optional[str] = None,
    ) -> list[dict]:
        notes = await self.repository.list(
            db, page=page, limit=limit, entity_type=entity_type, search=search
        )
        return [note_to_dict(n) for n in notes]

    async def create_note(
        self, db: AsyncSession, *, entity_type: str, entity_id: str, content: str
    ) -> dict:
        org_id = await organization_service.resolve_valid_org_id(db)
        created_by = await self._resolve_user_id(db)
        note = await self.repository.create(
            db,
            organization_id=org_id,
            entity_type=entity_type or "General",
            entity_id=entity_id or "General",
            content=content,
            created_by=created_by,
        )
        await self._commit(db, "Failed to create note")
        await db.refresh(note)
        return note_to_dict(note)

    async def list_pinned(self, db: AsyncSession) -> list[dict]:
        notes = await self.repository.list_pinned(db)
        return [note_to_dict(n) for n in notes]

    async def get_notes_by_entity(
        self, db: AsyncSession, *, entity_type: str, entity_id: str
    ) -> list[dict]:
        notes = await self.repository.list_by_entity(db, entity_type=entity_type, entity_id=entity_id)
        return [note_to_dict(n) for n in notes]

    async def bulk_delete(self, db: AsyncSession, ids: list[str]) -> dict:
        notes = await self.repository.list_by_ids(db, ids)
        for note in notes:
            await self.repository.delete(db, note)
        await self._commit(db, "Failed to bulk delete notes")
        return {"affected_count": len(notes), "message": "Notes deleted successfully"}

    async def get_note(self, db: AsyncSession, note_id: str) -> dict:
        note = await self.repository.get_by_id(db, note_id)
        if not note:
            raise NotFoundError(message=f"Note '{note_id}' not found")
        return note_to_dict(note)

    async def update_note(self, db: AsyncSession, note_id: str, content: str) -> dict:
        note = await self.repository.get_by_id(db, note_id)
        if not note:
            raise NotFoundError(message=f"Note '{note_id}' not found")
        note.content = content
        await self._commit(db, "Failed to update note")
        await db.refresh(note)
        return note_to_dict(note)

    async def delete_note(self, db: AsyncSession, note_id: str) -> dict:
        note = await self.repository.get_by_id(db, note_id)
        if not note:
            raise NotFoundError(message=f"Note '{note_id}' not found")
        await self.repository.delete(db, note)
        await self._commit(db, "Failed to delete note")
        return {"message": f"Note {note_id} deleted successfully", "status": "success"}

    async def set_pinned(self, db: AsyncSession, note_id: str, pinned: bool) -> dict:
        note = await self.repository.get_by_id(db, note_id)
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
        created_by_default: Optional[str] = None,
    ) -> list[dict]:
        notes = await self.repository.list_by_entity(db, entity_type=entity_type, entity_id=entity_id)
        return [
            {
                "id": n.id,
                "entity_type": n.entity_type,
                "entity_id": n.entity_id,
                "content": n.content,
                "created_by": n.created_by or created_by_default,
                "created_at": str(n.created_at) if n.created_at else None,
            }
            for n in notes
        ]

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
        note = await self.repository.create(
            db,
            organization_id=org_id,
            entity_type=entity_type,
            entity_id=entity_id,
            content=content,
            created_by=current_user.id,
        )
        await self._commit(db, "Failed to add note")
        await db.refresh(note)
        return {
            "id": note.id,
            "entity_type": note.entity_type,
            "entity_id": note.entity_id,
            "content": note.content,
            "created_by": note.created_by,
            "created_at": str(note.created_at) if note.created_at else None,
        }


note_service = NoteService()