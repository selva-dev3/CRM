from fastapi import APIRouter
from typing import List
from app.schemas.crm_schemas import ContactResponse, ContactCreate

router = APIRouter()

@router.get("/", response_model=List[ContactResponse], summary="List all contacts")
async def list_contacts():
    return [
        {"id": "cnt-1", "name": "Alice Smith", "email": "alice@techcorp.com", "phone": "+1-555-9012", "position": "VP Engineering", "company_id": "cmp-1", "created_at": "2026-08-01T10:00:00Z"}
    ]

@router.post("/", response_model=ContactResponse, status_code=201, summary="Create contact")
async def create_contact(payload: ContactCreate):
    return {"id": "cnt-2", **payload.model_dump(), "created_at": "2026-08-02T12:00:00Z"}
