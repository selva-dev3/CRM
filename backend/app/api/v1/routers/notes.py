from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import require_permission
from app.db.session import get_db
from app.schemas.crm_schemas import (
    BulkActionResponse,
    BulkDeleteRequest,
    MessageResponse,
    NoteBase,
)
from app.services.note_service import note_service

router = APIRouter()


@router.get(
    "",
    summary="List all notes across entities",
    dependencies=[Depends(require_permission("notes:read"))],
)
async def list_notes(
    page: int = 1,
    limit: int = 20,
    entity_type: str | None = Query(None),
    search: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    return await note_service.list_notes(
        db, page=page, limit=limit, entity_type=entity_type, search=search
    )


@router.post(
    "", summary="Create new note", dependencies=[Depends(require_permission("notes:create"))]
)
async def create_note(payload: NoteBase, db: AsyncSession = Depends(get_db)):
    return await note_service.create_note(
        db,
        entity_type=payload.entity_type,
        entity_id=payload.entity_id,
        content=payload.content,
    )


@router.get(
    "/pinned",
    summary="Get list of pinned notes",
    dependencies=[Depends(require_permission("notes:read"))],
)
async def get_pinned_notes(db: AsyncSession = Depends(get_db)):
    return await note_service.list_pinned(db)


@router.get(
    "/entity/{entity_type}/{entity_id}",
    summary="Get notes filtered by entity type and ID",
    dependencies=[Depends(require_permission("notes:read"))],
)
async def get_notes_by_entity(entity_type: str, entity_id: str, db: AsyncSession = Depends(get_db)):
    return await note_service.get_notes_by_entity(db, entity_type=entity_type, entity_id=entity_id)


@router.post(
    "/bulk-delete",
    response_model=BulkActionResponse,
    summary="Bulk delete notes",
    dependencies=[Depends(require_permission("notes:delete"))],
)
async def bulk_delete_notes(payload: BulkDeleteRequest, db: AsyncSession = Depends(get_db)):
    return await note_service.bulk_delete(db, payload.ids)


@router.get(
    "/{note_id}",
    summary="Get note details by ID",
    dependencies=[Depends(require_permission("notes:read"))],
)
async def get_note(note_id: str, db: AsyncSession = Depends(get_db)):
    return await note_service.get_note(db, note_id)


@router.put(
    "/{note_id}",
    summary="Update note content",
    dependencies=[Depends(require_permission("notes:update"))],
)
async def update_note(note_id: str, content: str, db: AsyncSession = Depends(get_db)):
    return await note_service.update_note(db, note_id, content)


@router.delete(
    "/{note_id}",
    response_model=MessageResponse,
    summary="Delete note by ID",
    dependencies=[Depends(require_permission("notes:delete"))],
)
async def delete_note(note_id: str, db: AsyncSession = Depends(get_db)):
    return await note_service.delete_note(db, note_id)


@router.post(
    "/{note_id}/pin",
    response_model=MessageResponse,
    summary="Pin note to top of entity timeline",
    dependencies=[Depends(require_permission("notes:update"))],
)
async def pin_note(note_id: str, db: AsyncSession = Depends(get_db)):
    return await note_service.set_pinned(db, note_id, pinned=True)


@router.post(
    "/{note_id}/unpin",
    response_model=MessageResponse,
    summary="Unpin note",
    dependencies=[Depends(require_permission("notes:update"))],
)
async def unpin_note(note_id: str, db: AsyncSession = Depends(get_db)):
    return await note_service.set_pinned(db, note_id, pinned=False)
