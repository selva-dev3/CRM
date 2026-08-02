from fastapi import APIRouter
from typing import List
from app.schemas.crm_schemas import QuoteResponse, QuoteBase

router = APIRouter()

@router.get("/", response_model=List[QuoteResponse], summary="List quotes & proposals")
async def list_quotes():
    return [
        {"id": "qte-1", "quote_number": "Q-2026-001", "items": [{"product_id": "prod-1", "quantity": 10, "unit_price": 1200.0}], "total_amount": 12000.0, "status": "Sent", "created_at": "2026-08-01T10:00:00Z"}
    ]

@router.post("/", response_model=QuoteResponse, status_code=201, summary="Create commercial quote")
async def create_quote(payload: QuoteBase):
    return {"id": "qte-2", **payload.model_dump(), "created_at": "2026-08-02T12:00:00Z"}
