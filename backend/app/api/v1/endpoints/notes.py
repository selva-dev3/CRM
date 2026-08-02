from fastapi import APIRouter, HTTPException, status, Query, Depends
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models import Note
from app.schemas.crm_schemas import NoteResponse, NoteBase, MessageResponse, BulkDeleteRequest, BulkActionResponse

router = APIRouter()

@router.get("", response_model=List[NoteResponse], summary="List all notes across entities")
async def list_notes(page: int = 1, limit: int = 20, entity_type: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    try:
        stmt = select(Note).offset((page - 1) * limit).limit(limit)
        if entity_type:
            stmt = stmt.where(Note.entity_type == entity_type)
        res = await db.execute(stmt)
        notes = res.scalars().all()
        return [{"id": n.id, "entity_type": n.entity_type, "entity_id": n.entity_id, "content": n.content, "created_by": n.created_by, "created_at": str(n.created_at)} for n in notes]
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.post("", response_model=NoteResponse, status_code=status.HTTP_201_CREATED, summary="Create new note")
async def create_note(payload: NoteBase, db: AsyncSession = Depends(get_db)):
    try:
        n = Note(organization_id="org-1", entity_type=payload.entity_type, entity_id=payload.entity_id, content=payload.content, created_by="usr-1")
        db.add(n)
        await db.commit()
        return {"id": n.id, "entity_type": n.entity_type, "entity_id": n.entity_id, "content": n.content, "created_by": n.created_by, "created_at": str(n.created_at)}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Failed to create note: {str(e)}")

@router.get("/pinned", response_model=List[NoteResponse], summary="Get list of pinned notes")
async def get_pinned_notes(db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Note).where(Note.is_pinned == True))
    notes = res.scalars().all()
    return [{"id": n.id, "entity_type": n.entity_type, "entity_id": n.entity_id, "content": n.content, "created_by": n.created_by, "created_at": str(n.created_at)} for n in notes]

@router.get("/entity/{entity_type}/{entity_id}", response_model=List[NoteResponse], summary="Get notes filtered by entity type and ID")
async def get_notes_by_entity(entity_type: str, entity_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Note).where(Note.entity_type == entity_type, Note.entity_id == entity_id))
    notes = res.scalars().all()
    return [{"id": n.id, "entity_type": n.entity_type, "entity_id": n.entity_id, "content": n.content, "created_by": n.created_by, "created_at": str(n.created_at)} for n in notes]

@router.post("/bulk-delete", response_model=BulkActionResponse, summary="Bulk delete notes")
async def bulk_delete_notes(payload: BulkDeleteRequest, db: AsyncSession = Depends(get_db)):
    try:
        stmt = select(Note).where(Note.id.in_(payload.ids))
        res = await db.execute(stmt)
        items = res.scalars().all()
        for item in items:
            await db.delete(item)
        await db.commit()
        return {"affected_count": len(items), "message": "Notes deleted successfully"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.get("/{note_id}", response_model=NoteResponse, summary="Get note details by ID")
async def get_note(note_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Note).where(Note.id == note_id))
    n = res.scalars().first()
    if not n:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Note '{note_id}' not found")
    return {"id": n.id, "entity_type": n.entity_type, "entity_id": n.entity_id, "content": n.content, "created_by": n.created_by, "created_at": str(n.created_at)}

@router.put("/{note_id}", response_model=NoteResponse, summary="Update note content")
async def update_note(note_id: str, content: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Note).where(Note.id == note_id))
    n = res.scalars().first()
    if not n:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Note '{note_id}' not found")
    try:
        n.content = content
        await db.commit()
        return {"id": n.id, "entity_type": n.entity_type, "entity_id": n.entity_id, "content": n.content, "created_by": n.created_by, "created_at": str(n.created_at)}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.delete("/{note_id}", response_model=MessageResponse, summary="Delete note by ID")
async def delete_note(note_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Note).where(Note.id == note_id))
    n = res.scalars().first()
    if not n:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Note '{note_id}' not found")
    try:
        await db.delete(n)
        await db.commit()
        return {"message": f"Note {note_id} deleted successfully", "status": "success"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.post("/{note_id}/pin", response_model=MessageResponse, summary="Pin note to top of entity timeline")
async def pin_note(note_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Note).where(Note.id == note_id))
    n = res.scalars().first()
    if not n:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Note '{note_id}' not found")
    try:
        n.is_pinned = True
        await db.commit()
        return {"message": f"Note {note_id} pinned", "status": "success"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.post("/{note_id}/unpin", response_model=MessageResponse, summary="Unpin note")
async def unpin_note(note_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Note).where(Note.id == note_id))
    n = res.scalars().first()
    if not n:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Note '{note_id}' not found")
    try:
        n.is_pinned = False
        await db.commit()
        return {"message": f"Note {note_id} unpinned", "status": "success"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
