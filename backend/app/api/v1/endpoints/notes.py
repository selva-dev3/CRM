from fastapi import APIRouter, HTTPException, status, Query, Depends
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models import Note, User
from app.api.deps import get_valid_org_id
from app.schemas.crm_schemas import NoteResponse, NoteBase, MessageResponse, BulkDeleteRequest, BulkActionResponse

router = APIRouter()

async def resolve_user_id(db: AsyncSession) -> str:
    first_user_res = await db.execute(select(User).limit(1))
    first_user = first_user_res.scalars().first()
    if first_user:
        return first_user.id
    return "user-default-1"

@router.get("", summary="List all notes across entities")
async def list_notes(
    page: int = 1,
    limit: int = 20,
    entity_type: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    try:
        stmt = select(Note)
        if entity_type and entity_type.strip():
            stmt = stmt.where(Note.entity_type == entity_type.strip())
        if search and search.strip():
            stmt = stmt.where(Note.content.ilike(f"%{search.strip()}%"))
        stmt = stmt.order_by(Note.created_at.desc()).offset((page - 1) * limit).limit(limit)
        res = await db.execute(stmt)
        notes = res.scalars().all()
        return [
            {
                "id": n.id,
                "entity_type": n.entity_type or "General",
                "entity_id": n.entity_id or "General",
                "content": n.content,
                "is_pinned": getattr(n, "is_pinned", False),
                "created_by": n.created_by or "Sales Admin",
                "created_at": str(n.created_at)
            } for n in notes
        ]
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.post("", summary="Create new note")
async def create_note(payload: NoteBase, db: AsyncSession = Depends(get_db)):
    try:
        org_id = await get_valid_org_id(db)
        uid = await resolve_user_id(db)
        n = Note(
            organization_id=org_id,
            entity_type=payload.entity_type or "General",
            entity_id=payload.entity_id or "General",
            content=payload.content,
            created_by=uid
        )
        db.add(n)
        await db.commit()
        await db.refresh(n)
        return {
            "id": n.id,
            "entity_type": n.entity_type,
            "entity_id": n.entity_id,
            "content": n.content,
            "is_pinned": getattr(n, "is_pinned", False),
            "created_by": n.created_by,
            "created_at": str(n.created_at)
        }
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Failed to create note: {str(e)}")

@router.get("/pinned", summary="Get list of pinned notes")
async def get_pinned_notes(db: AsyncSession = Depends(get_db)):
    try:
        res = await db.execute(select(Note).where(Note.is_pinned == True))
        notes = res.scalars().all()
        return [
            {
                "id": n.id,
                "entity_type": n.entity_type,
                "entity_id": n.entity_id,
                "content": n.content,
                "is_pinned": True,
                "created_by": n.created_by,
                "created_at": str(n.created_at)
            } for n in notes
        ]
    except Exception:
        return []

@router.get("/entity/{entity_type}/{entity_id}", summary="Get notes filtered by entity type and ID")
async def get_notes_by_entity(entity_type: str, entity_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Note).where(Note.entity_type == entity_type, Note.entity_id == entity_id))
    notes = res.scalars().all()
    return [
        {
            "id": n.id,
            "entity_type": n.entity_type,
            "entity_id": n.entity_id,
            "content": n.content,
            "is_pinned": getattr(n, "is_pinned", False),
            "created_by": n.created_by,
            "created_at": str(n.created_at)
        } for n in notes
    ]

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

@router.get("/{note_id}", summary="Get note details by ID")
async def get_note(note_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Note).where(Note.id == note_id))
    n = res.scalars().first()
    if not n:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Note '{note_id}' not found")
    return {
        "id": n.id,
        "entity_type": n.entity_type,
        "entity_id": n.entity_id,
        "content": n.content,
        "is_pinned": getattr(n, "is_pinned", False),
        "created_by": n.created_by,
        "created_at": str(n.created_at)
    }

@router.put("/{note_id}", summary="Update note content")
async def update_note(note_id: str, content: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Note).where(Note.id == note_id))
    n = res.scalars().first()
    if not n:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Note '{note_id}' not found")
    try:
        n.content = content
        await db.commit()
        await db.refresh(n)
        return {
            "id": n.id,
            "entity_type": n.entity_type,
            "entity_id": n.entity_id,
            "content": n.content,
            "is_pinned": getattr(n, "is_pinned", False),
            "created_by": n.created_by,
            "created_at": str(n.created_at)
        }
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
