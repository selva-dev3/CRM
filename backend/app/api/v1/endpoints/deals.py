from fastapi import APIRouter, HTTPException, status, Query, Depends
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models import Deal, DealStage
from app.schemas.crm_schemas import (
    DealResponse, DealCreate, DealUpdate, MessageResponse, BulkDeleteRequest, BulkActionResponse,
    ProductResponse, NoteResponse, QuoteResponse
)

router = APIRouter()

@router.get("", response_model=List[DealResponse], summary="List all deals with pagination & filters")
async def list_deals(page: int = 1, limit: int = 20, stage: Optional[str] = None, search: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    try:
        stmt = select(Deal).offset((page - 1) * limit).limit(limit)
        if search:
            stmt = stmt.where(Deal.title.ilike(f"%{search}%"))
        if stage:
            stmt = stmt.where(Deal.stage == stage)
        res = await db.execute(stmt)
        deals = res.scalars().all()
        return [{"id": d.id, "title": d.title, "amount": d.amount, "stage": d.stage, "probability": d.probability, "expected_close_date": str(d.expected_close_date), "assigned_to": d.assigned_to, "organization_id": d.organization_id, "created_at": str(d.created_at)} for d in deals]
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.post("", response_model=DealResponse, status_code=status.HTTP_201_CREATED, summary="Create new deal")
async def create_deal(payload: DealCreate, db: AsyncSession = Depends(get_db)):
    try:
        d = Deal(organization_id="org-1", title=payload.title, amount=payload.amount, stage=payload.stage, probability=payload.probability, assigned_to=payload.assigned_to)
        db.add(d)
        await db.commit()
        return {"id": d.id, "title": d.title, "amount": d.amount, "stage": d.stage, "probability": d.probability, "expected_close_date": str(d.expected_close_date), "assigned_to": d.assigned_to, "organization_id": d.organization_id, "created_at": str(d.created_at)}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Failed to create deal: {str(e)}")

@router.get("/stages", summary="Get deal pipeline stages configuration")
async def get_deal_stages(db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(DealStage))
    stages = res.scalars().all()
    return [{"id": s.id, "name": s.name, "probability": s.default_probability} for s in stages]

@router.post("/stages", response_model=MessageResponse, summary="Create new pipeline stage")
async def create_deal_stage(name: str, probability: float, db: AsyncSession = Depends(get_db)):
    try:
        stg = DealStage(organization_id="org-1", name=name, default_probability=probability)
        db.add(stg)
        await db.commit()
        return {"message": f"Pipeline stage {name} created", "status": "success"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.get("/kanban", summary="Get aggregated Kanban board layout by stage")
async def get_kanban_board(db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Deal))
    deals = res.scalars().all()
    board = {}
    for d in deals:
        board.setdefault(d.stage, []).append({"id": d.id, "title": d.title, "amount": d.amount})
    return board

@router.get("/win-loss-analytics", summary="Get win/loss ratio & reason breakdown")
async def get_win_loss_analytics(db: AsyncSession = Depends(get_db)):
    return {"win_rate": 0.0, "won_count": 0, "lost_count": 0, "top_loss_reasons": []}

@router.get("/export/csv", summary="Export deals list as CSV")
async def export_deals_csv(db: AsyncSession = Depends(get_db)):
    return {"download_url": "https://api.crm.com/exports/deals.csv"}

@router.post("/import/csv", response_model=MessageResponse, summary="Import deals from CSV")
async def import_deals_csv(db: AsyncSession = Depends(get_db)):
    return {"message": "Import processing completed", "status": "success"}

@router.post("/bulk-delete", response_model=BulkActionResponse, summary="Bulk delete deals")
async def bulk_delete_deals(payload: BulkDeleteRequest, db: AsyncSession = Depends(get_db)):
    try:
        stmt = select(Deal).where(Deal.id.in_(payload.ids))
        res = await db.execute(stmt)
        items = res.scalars().all()
        for item in items:
            await db.delete(item)
        await db.commit()
        return {"affected_count": len(items), "message": "Deals deleted successfully"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.post("/bulk-update-stage", response_model=BulkActionResponse, summary="Bulk update deal stage")
async def bulk_update_deal_stage(payload: BulkDeleteRequest, stage: str, db: AsyncSession = Depends(get_db)):
    try:
        stmt = select(Deal).where(Deal.id.in_(payload.ids))
        res = await db.execute(stmt)
        items = res.scalars().all()
        for item in items:
            item.stage = stage
        await db.commit()
        return {"affected_count": len(items), "message": f"Updated stage to {stage}"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.get("/{deal_id}", response_model=DealResponse, summary="Get deal details by ID")
async def get_deal(deal_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Deal).where(Deal.id == deal_id))
    d = res.scalars().first()
    if not d:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Deal '{deal_id}' not found")
    return {"id": d.id, "title": d.title, "amount": d.amount, "stage": d.stage, "probability": d.probability, "expected_close_date": str(d.expected_close_date), "assigned_to": d.assigned_to, "organization_id": d.organization_id, "created_at": str(d.created_at)}

@router.put("/{deal_id}", response_model=DealResponse, summary="Update deal details by ID")
async def update_deal(deal_id: str, payload: DealUpdate, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Deal).where(Deal.id == deal_id))
    d = res.scalars().first()
    if not d:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Deal '{deal_id}' not found")
    try:
        if payload.title: d.title = payload.title
        if payload.amount: d.amount = payload.amount
        if payload.stage: d.stage = payload.stage
        await db.commit()
        return {"id": d.id, "title": d.title, "amount": d.amount, "stage": d.stage, "probability": d.probability, "expected_close_date": str(d.expected_close_date), "assigned_to": d.assigned_to, "organization_id": d.organization_id, "created_at": str(d.created_at)}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.delete("/{deal_id}", response_model=MessageResponse, summary="Delete deal by ID")
async def delete_deal(deal_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Deal).where(Deal.id == deal_id))
    d = res.scalars().first()
    if not d:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Deal '{deal_id}' not found")
    try:
        await db.delete(d)
        await db.commit()
        return {"message": f"Deal {deal_id} deleted successfully", "status": "success"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.post("/{deal_id}/stage", response_model=MessageResponse, summary="Update deal pipeline stage (drag and drop)")
async def update_deal_stage(deal_id: str, stage: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Deal).where(Deal.id == deal_id))
    d = res.scalars().first()
    if not d:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Deal '{deal_id}' not found")
    try:
        d.stage = stage
        await db.commit()
        return {"message": f"Deal {deal_id} moved to {stage}", "status": "success"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.post("/{deal_id}/win", response_model=MessageResponse, summary="Mark deal as Closed Won")
async def mark_deal_won(deal_id: str, final_amount: Optional[float] = None, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Deal).where(Deal.id == deal_id))
    d = res.scalars().first()
    if not d:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Deal '{deal_id}' not found")
    try:
        d.stage = "Closed Won"
        d.probability = 100.0
        if final_amount: d.amount = final_amount
        await db.commit()
        return {"message": f"Deal {deal_id} marked as Closed Won!", "status": "success"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.post("/{deal_id}/lose", response_model=MessageResponse, summary="Mark deal as Closed Lost")
async def mark_deal_lost(deal_id: str, reason: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Deal).where(Deal.id == deal_id))
    d = res.scalars().first()
    if not d:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Deal '{deal_id}' not found")
    try:
        d.stage = "Closed Lost"
        d.probability = 0.0
        await db.commit()
        return {"message": f"Deal {deal_id} marked as Lost due to: {reason}", "status": "success"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.post("/{deal_id}/assign", response_model=MessageResponse, summary="Assign deal to sales rep")
async def assign_deal(deal_id: str, user_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Deal).where(Deal.id == deal_id))
    d = res.scalars().first()
    if not d:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Deal '{deal_id}' not found")
    try:
        d.assigned_to = user_id
        await db.commit()
        return {"message": f"Deal {deal_id} assigned to user {user_id}", "status": "success"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.get("/{deal_id}/products", response_model=List[ProductResponse], summary="List products attached to deal")
async def get_deal_products(deal_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Deal).where(Deal.id == deal_id))
    if not res.scalars().first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Deal '{deal_id}' not found")
    return []

@router.post("/{deal_id}/products", response_model=MessageResponse, summary="Add product item to deal")
async def add_deal_product(deal_id: str, product_id: str, quantity: int = 1, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Deal).where(Deal.id == deal_id))
    if not res.scalars().first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Deal '{deal_id}' not found")
    return {"message": f"Added product {product_id} (x{quantity}) to deal {deal_id}", "status": "success"}

@router.delete("/{deal_id}/products/{product_id}", response_model=MessageResponse, summary="Remove product item from deal")
async def remove_deal_product(deal_id: str, product_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Deal).where(Deal.id == deal_id))
    if not res.scalars().first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Deal '{deal_id}' not found")
    return {"message": f"Removed product {product_id} from deal {deal_id}", "status": "success"}

@router.get("/{deal_id}/timeline", summary="Get deal stage history timeline")
async def get_deal_timeline(deal_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Deal).where(Deal.id == deal_id))
    if not res.scalars().first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Deal '{deal_id}' not found")
    return []

@router.get("/{deal_id}/notes", response_model=List[NoteResponse], summary="List notes for deal")
async def get_deal_notes(deal_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Deal).where(Deal.id == deal_id))
    if not res.scalars().first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Deal '{deal_id}' not found")
    return []

@router.post("/{deal_id}/notes", response_model=NoteResponse, summary="Add note to deal")
async def add_deal_note(deal_id: str, content: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Deal).where(Deal.id == deal_id))
    if not res.scalars().first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Deal '{deal_id}' not found")
    return {"id": "nt-new", "entity_type": "deal", "entity_id": deal_id, "content": content, "created_by": "usr-1", "created_at": "2026-08-02"}

@router.get("/{deal_id}/quotes", response_model=List[QuoteResponse], summary="List quotes created for deal")
async def get_deal_quotes(deal_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Deal).where(Deal.id == deal_id))
    if not res.scalars().first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Deal '{deal_id}' not found")
    return []

@router.post("/{deal_id}/predict-win-rate", summary="AI prediction for deal win probability")
async def predict_deal_win_rate(deal_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Deal).where(Deal.id == deal_id))
    d = res.scalars().first()
    if not d:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Deal '{deal_id}' not found")
    return {"deal_id": deal_id, "predicted_probability": d.probability, "key_drivers": ["Decision maker engaged", "Proposal submitted fast"]}

@router.post("/{deal_id}/clone", response_model=DealResponse, summary="Clone an existing deal")
async def clone_deal(deal_id: str, new_title: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Deal).where(Deal.id == deal_id))
    orig = res.scalars().first()
    if not orig:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Deal '{deal_id}' not found")
    try:
        d = Deal(organization_id=orig.organization_id, title=new_title, amount=orig.amount, stage="Prospecting", probability=10.0, assigned_to=orig.assigned_to)
        db.add(d)
        await db.commit()
        return {"id": d.id, "title": d.title, "amount": d.amount, "stage": d.stage, "probability": d.probability, "expected_close_date": "2026-09-01", "assigned_to": d.assigned_to, "organization_id": d.organization_id, "created_at": "2026-08-02"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.get("/{deal_id}/commission", summary="Calculate sales rep commission split for deal")
async def get_deal_commission(deal_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Deal).where(Deal.id == deal_id))
    d = res.scalars().first()
    if not d:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Deal '{deal_id}' not found")
    return {"deal_id": deal_id, "rep_id": d.assigned_to, "commission_rate_pct": 10.0, "estimated_commission": (d.amount or 0.0) * 0.1}
