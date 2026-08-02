from fastapi import APIRouter, HTTPException, status, Query
from typing import List, Optional, Dict, Any
from app.schemas.crm_schemas import (
    DealResponse, DealCreate, DealUpdate, MessageResponse, BulkDeleteRequest, BulkActionResponse,
    ProductResponse, NoteResponse, QuoteResponse
)

router = APIRouter()

@router.get("", response_model=List[DealResponse], summary="List all deals with pagination & filters")
async def list_deals(page: int = 1, limit: int = 20, stage: Optional[str] = None, search: Optional[str] = None):
    return [
        {"id": "dl-1", "title": "Acme Enterprise License", "amount": 85000.0, "stage": "Proposal Sent", "probability": 75.0, "expected_close_date": "2026-08-30", "assigned_to": "usr-1", "organization_id": "org-1", "created_at": "2026-08-02"},
        {"id": "dl-2", "title": "TechCorp Expansion", "amount": 42000.0, "stage": "Negotiation", "probability": 90.0, "expected_close_date": "2026-08-15", "assigned_to": "usr-2", "organization_id": "org-1", "created_at": "2026-08-02"}
    ]

@router.post("", response_model=DealResponse, status_code=status.HTTP_201_CREATED, summary="Create new deal")
async def create_deal(payload: DealCreate):
    return {"id": "dl-3", "title": payload.title, "amount": payload.amount, "stage": payload.stage, "probability": payload.probability, "expected_close_date": payload.expected_close_date, "assigned_to": payload.assigned_to, "organization_id": "org-1", "created_at": "2026-08-02"}

@router.get("/stages", summary="Get deal pipeline stages configuration")
async def get_deal_stages():
    return [
        {"id": "stg-1", "name": "Prospecting", "probability": 10.0},
        {"id": "stg-2", "name": "Qualified", "probability": 30.0},
        {"id": "stg-3", "name": "Proposal Sent", "probability": 60.0},
        {"id": "stg-4", "name": "Negotiation", "probability": 80.0},
        {"id": "stg-5", "name": "Closed Won", "probability": 100.0},
        {"id": "stg-6", "name": "Closed Lost", "probability": 0.0}
    ]

@router.post("/stages", response_model=MessageResponse, summary="Create new pipeline stage")
async def create_deal_stage(name: str, probability: float):
    return {"message": f"Pipeline stage {name} created", "status": "success"}

@router.get("/kanban", summary="Get aggregated Kanban board layout by stage")
async def get_kanban_board():
    return {
        "Prospecting": [{"id": "dl-10", "title": "Beta Deal", "amount": 15000.0}],
        "Proposal Sent": [{"id": "dl-1", "title": "Acme License", "amount": 85000.0}],
        "Closed Won": [{"id": "dl-50", "title": "Old Contract", "amount": 120000.0}]
    }

@router.get("/win-loss-analytics", summary="Get win/loss ratio & reason breakdown")
async def get_win_loss_analytics():
    return {"win_rate": 68.5, "won_count": 45, "lost_count": 21, "top_loss_reasons": ["Price too high", "Missing feature X"]}

@router.get("/export/csv", summary="Export deals list as CSV")
async def export_deals_csv():
    return {"download_url": "https://api.crm.com/exports/deals.csv"}

@router.post("/import/csv", response_model=MessageResponse, summary="Import deals from CSV")
async def import_deals_csv():
    return {"message": "Imported 25 deals", "status": "success"}

@router.post("/bulk-delete", response_model=BulkActionResponse, summary="Bulk delete deals")
async def bulk_delete_deals(payload: BulkDeleteRequest):
    return {"affected_count": len(payload.ids), "message": "Deals deleted successfully"}

@router.post("/bulk-update-stage", response_model=BulkActionResponse, summary="Bulk update deal stage")
async def bulk_update_deal_stage(payload: BulkDeleteRequest, stage: str):
    return {"affected_count": len(payload.ids), "message": f"Updated stage to {stage}"}

@router.get("/{deal_id}", response_model=DealResponse, summary="Get deal details by ID")
async def get_deal(deal_id: str):
    return {"id": deal_id, "title": "Acme Enterprise License", "amount": 85000.0, "stage": "Proposal Sent", "probability": 75.0, "expected_close_date": "2026-08-30", "assigned_to": "usr-1", "organization_id": "org-1", "created_at": "2026-08-02"}

@router.put("/{deal_id}", response_model=DealResponse, summary="Update deal details by ID")
async def update_deal(deal_id: str, payload: DealUpdate):
    return {"id": deal_id, "title": payload.title or "Acme Enterprise License", "amount": payload.amount or 85000.0, "stage": payload.stage or "Proposal Sent", "probability": payload.probability or 75.0, "expected_close_date": "2026-08-30", "assigned_to": "usr-1", "organization_id": "org-1", "created_at": "2026-08-02"}

@router.delete("/{deal_id}", response_model=MessageResponse, summary="Delete deal by ID")
async def delete_deal(deal_id: str):
    return {"message": f"Deal {deal_id} deleted successfully", "status": "success"}

@router.post("/{deal_id}/stage", response_model=MessageResponse, summary="Update deal pipeline stage (drag and drop)")
async def update_deal_stage(deal_id: str, stage: str):
    return {"message": f"Deal {deal_id} moved to {stage}", "status": "success"}

@router.post("/{deal_id}/win", response_model=MessageResponse, summary="Mark deal as Closed Won")
async def mark_deal_won(deal_id: str, final_amount: Optional[float] = None):
    return {"message": f"Deal {deal_id} marked as Closed Won!", "status": "success"}

@router.post("/{deal_id}/lose", response_model=MessageResponse, summary="Mark deal as Closed Lost")
async def mark_deal_lost(deal_id: str, reason: str):
    return {"message": f"Deal {deal_id} marked as Lost due to: {reason}", "status": "success"}

@router.post("/{deal_id}/assign", response_model=MessageResponse, summary="Assign deal to sales rep")
async def assign_deal(deal_id: str, user_id: str):
    return {"message": f"Deal {deal_id} assigned to user {user_id}", "status": "success"}

@router.get("/{deal_id}/products", response_model=List[ProductResponse], summary="List products attached to deal")
async def get_deal_products(deal_id: str):
    return [{"id": "prod-1", "name": "CRM Enterprise Seat", "sku": "CRM-ENT", "price": 1200.0, "category": "Software"}]

@router.post("/{deal_id}/products", response_model=MessageResponse, summary="Add product item to deal")
async def add_deal_product(deal_id: str, product_id: str, quantity: int = 1):
    return {"message": f"Added product {product_id} (x{quantity}) to deal {deal_id}", "status": "success"}

@router.delete("/{deal_id}/products/{product_id}", response_model=MessageResponse, summary="Remove product item from deal")
async def remove_deal_product(deal_id: str, product_id: str):
    return {"message": f"Removed product {product_id} from deal {deal_id}", "status": "success"}

@router.get("/{deal_id}/timeline", summary="Get deal stage history timeline")
async def get_deal_timeline(deal_id: str):
    return [{"stage": "Prospecting", "entered_at": "2026-07-15"}, {"stage": "Proposal Sent", "entered_at": "2026-08-01"}]

@router.get("/{deal_id}/notes", response_model=List[NoteResponse], summary="List notes for deal")
async def get_deal_notes(deal_id: str):
    return [{"id": "nt-1", "entity_type": "deal", "entity_id": deal_id, "content": "Client requested 10% volume discount", "created_by": "usr-1", "created_at": "2026-08-02"}]

@router.post("/{deal_id}/notes", response_model=NoteResponse, summary="Add note to deal")
async def add_deal_note(deal_id: str, content: str):
    return {"id": "nt-2", "entity_type": "deal", "entity_id": deal_id, "content": content, "created_by": "usr-1", "created_at": "2026-08-02"}

@router.get("/{deal_id}/quotes", response_model=List[QuoteResponse], summary="List quotes created for deal")
async def get_deal_quotes(deal_id: str):
    return [{"id": "qt-1", "quote_number": "Q-8801", "items": [], "total_amount": 85000.0, "status": "Sent", "created_at": "2026-08-02"}]

@router.post("/{deal_id}/predict-win-rate", summary="AI prediction for deal win probability")
async def predict_deal_win_rate(deal_id: str):
    return {"deal_id": deal_id, "predicted_probability": 82.4, "key_drivers": ["Decision maker engaged", "Proposal submitted fast"]}

@router.post("/{deal_id}/clone", response_model=DealResponse, summary="Clone an existing deal")
async def clone_deal(deal_id: str, new_title: str):
    return {"id": "dl-cloned", "title": new_title, "amount": 85000.0, "stage": "Prospecting", "probability": 10.0, "expected_close_date": "2026-09-01", "assigned_to": "usr-1", "organization_id": "org-1", "created_at": "2026-08-02"}

@router.get("/{deal_id}/commission", summary="Calculate sales rep commission split for deal")
async def get_deal_commission(deal_id: str):
    return {"deal_id": deal_id, "rep_id": "usr-1", "commission_rate_pct": 10.0, "estimated_commission": 8500.0}
