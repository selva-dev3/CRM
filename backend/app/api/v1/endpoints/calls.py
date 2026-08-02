from fastapi import APIRouter
from typing import List
from app.schemas.crm_schemas import CallLogResponse, CallLogBase

router = APIRouter()

@router.get("/", response_model=List[CallLogResponse], summary="List call logs")
async def list_calls():
    return [
        {"id": "call-1", "contact_id": "cnt-1", "call_type": "Outbound", "duration_seconds": 320, "notes": "Customer confirmed budget approval", "timestamp": "2026-08-02T11:00:00Z"}
    ]

@router.post("/", response_model=CallLogResponse, status_code=201, summary="Log phone call")
async def log_call(payload: CallLogBase):
    return {"id": "call-2", **payload.model_dump(), "timestamp": "2026-08-02T12:00:00Z"}
