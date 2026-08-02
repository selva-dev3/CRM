from fastapi import APIRouter
from typing import List
from app.schemas.crm_schemas import DealResponse, DealCreate

router = APIRouter()

@router.get("/", response_model=List[DealResponse], summary="List all sales deals")
async def list_deals():
    return [
        {"id": "deal-1", "title": "Acme License Expansion", "amount": 45000.0, "stage": "Proposal", "probability": 80.0, "expected_close_date": "2026-08-30", "assigned_to": "usr-1", "organization_id": "org-1", "created_at": "2026-08-01T10:00:00Z"}
    ]

@router.post("/", response_model=DealResponse, status_code=201, summary="Create deal")
async def create_deal(payload: DealCreate):
    return {"id": "deal-2", **payload.model_dump(), "organization_id": "org-1", "created_at": "2026-08-02T12:00:00Z"}

@router.patch("/{deal_id}/stage", summary="Update deal pipeline stage (Kanban)")
async def update_deal_stage(deal_id: str, new_stage: str):
    """Updates deal stage for Kanban drag and drop."""
    return {"deal_id": deal_id, "new_stage": new_stage, "status": "updated"}
