from fastapi import APIRouter, HTTPException, status, Query
from typing import List, Optional
from app.schemas.crm_schemas import NoteResponse, NoteBase, MessageResponse, BulkDeleteRequest, BulkActionResponse

router = APIRouter()

@router.get("", response_model=List[NoteResponse], summary="List all notes across entities")
async def list_notes(page: int = 1, limit: int = 20, entity_type: Optional[str] = None):
    return [
        {"id": "nt-1", "entity_type": "lead", "entity_id": "ld-101", "content": "Client mentioned decision by Friday.", "created_by": "usr-1", "created_at": "2026-08-02"},
        {"id": "nt-2", "entity_type": "deal", "entity_id": "dl-1", "content": "Legal team reviewing MSA agreement.", "created_by": "usr-2", "created_at": "2026-08-02"}
    ]

@router.post("", response_model=NoteResponse, status_code=status.HTTP_201_CREATED, summary="Create new note")
async def create_note(payload: NoteBase):
    return {"id": "nt-3", "entity_type": payload.entity_type, "entity_id": payload.entity_id, "content": payload.content, "created_by": "usr-1", "created_at": "2026-08-02"}

@router.get("/pinned", response_model=List[NoteResponse], summary="Get list of pinned notes")
async def get_pinned_notes():
    return [{"id": "nt-1", "entity_type": "lead", "entity_id": "ld-101", "content": "Client decision by Friday.", "created_by": "usr-1", "created_at": "2026-08-02"}]

@router.get("/entity/{entity_type}/{entity_id}", response_model=List[NoteResponse], summary="Get notes filtered by entity type and ID")
async def get_notes_by_entity(entity_type: str, entity_id: str):
    return [{"id": "nt-1", "entity_type": entity_type, "entity_id": entity_id, "content": "Entity specific note", "created_by": "usr-1", "created_at": "2026-08-02"}]

@router.post("/bulk-delete", response_model=BulkActionResponse, summary="Bulk delete notes")
async def bulk_delete_notes(payload: BulkDeleteRequest):
    return {"affected_count": len(payload.ids), "message": "Notes deleted successfully"}

@router.get("/{note_id}", response_model=NoteResponse, summary="Get note details by ID")
async def get_note(note_id: str):
    return {"id": note_id, "entity_type": "lead", "entity_id": "ld-101", "content": "Client decision by Friday.", "created_by": "usr-1", "created_at": "2026-08-02"}

@router.put("/{note_id}", response_model=NoteResponse, summary="Update note content")
async def update_note(note_id: str, content: str):
    return {"id": note_id, "entity_type": "lead", "entity_id": "ld-101", "content": content, "created_by": "usr-1", "created_at": "2026-08-02"}

@router.delete("/{note_id}", response_model=MessageResponse, summary="Delete note by ID")
async def delete_note(note_id: str):
    return {"message": f"Note {note_id} deleted", "status": "success"}

@router.post("/{note_id}/pin", response_model=MessageResponse, summary="Pin note to top of entity timeline")
async def pin_note(note_id: str):
    return {"message": f"Note {note_id} pinned", "status": "success"}

@router.post("/{note_id}/unpin", response_model=MessageResponse, summary="Unpin note")
async def unpin_note(note_id: str):
    return {"message": f"Note {note_id} unpinned", "status": "success"}
