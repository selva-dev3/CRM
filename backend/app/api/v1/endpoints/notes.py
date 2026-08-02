from fastapi import APIRouter
from typing import List
from app.schemas.crm_schemas import NoteResponse, NoteBase

router = APIRouter()

@router.get("/", response_model=List[NoteResponse], summary="List internal notes")
async def list_notes():
    return [
        {"id": "nte-1", "entity_type": "Lead", "entity_id": "lead-1", "content": "Requires enterprise SSO setup", "created_by": "usr-1", "created_at": "2026-08-01T12:00:00Z"}
    ]

@router.post("/", response_model=NoteResponse, status_code=201, summary="Create note")
async def create_note(payload: NoteBase):
    return {"id": "nte-2", **payload.model_dump(), "created_by": "usr-1", "created_at": "2026-08-02T12:00:00Z"}
