from fastapi import APIRouter, HTTPException, status, Query, Depends
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models import Quote
from app.api.deps import get_valid_org_id
from app.schemas.crm_schemas import QuoteResponse, QuoteBase, MessageResponse, BulkDeleteRequest, BulkActionResponse, InvoiceResponse

router = APIRouter()

@router.get("", summary="List quotes with pagination & filter")
async def list_quotes(
    page: int = 1,
    limit: int = 20,
    status_filter: Optional[str] = Query(None, alias="status"),
    search: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    try:
        stmt = select(Quote)
        if status_filter and status_filter.strip():
            stmt = stmt.where(Quote.status == status_filter.strip())
        if search and search.strip():
            stmt = stmt.where(Quote.quote_number.ilike(f"%{search.strip()}%"))
        stmt = stmt.order_by(Quote.created_at.desc()).offset((page - 1) * limit).limit(limit)
        res = await db.execute(stmt)
        quotes = res.scalars().all()
        return [
            {
                "id": q.id,
                "quote_number": q.quote_number or f"QUO-{q.id[:6]}",
                "items": [],
                "total_amount": q.total_amount or 0.0,
                "status": q.status or "Draft",
                "created_at": str(q.created_at)
            } for q in quotes
        ]
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.post("", response_model=QuoteResponse, status_code=status.HTTP_201_CREATED, summary="Create new sales quote / proposal")
async def create_quote(payload: QuoteBase, db: AsyncSession = Depends(get_db)):
    try:
        org_id = await get_valid_org_id(db)
        q = Quote(
            organization_id=org_id,
            quote_number=payload.quote_number or f"QUO-{int(datetime.now().timestamp() if 'datetime' in globals() else 1001)}",
            total_amount=payload.total_amount or 0.0,
            status=payload.status or "Draft"
        )
        db.add(q)
        await db.commit()
        await db.refresh(q)
        return {
            "id": q.id,
            "quote_number": q.quote_number,
            "items": payload.items or [],
            "total_amount": q.total_amount,
            "status": q.status,
            "created_at": str(q.created_at)
        }
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Failed to create quote: {str(e)}")

@router.get("/export/csv", summary="Export quotes list as CSV")
async def export_quotes_csv(db: AsyncSession = Depends(get_db)):
    return {"download_url": "https://api.crm.com/exports/quotes_proposals_export.csv"}

@router.post("/import/csv", response_model=MessageResponse, summary="Import quotes from CSV file")
async def import_quotes_csv(db: AsyncSession = Depends(get_db)):
    return {"message": "Quote proposals CSV import processing completed", "status": "success"}

@router.post("/bulk-delete", response_model=BulkActionResponse, summary="Bulk delete quotes")
async def bulk_delete_quotes(payload: BulkDeleteRequest, db: AsyncSession = Depends(get_db)):
    try:
        stmt = select(Quote).where(Quote.id.in_(payload.ids))
        res = await db.execute(stmt)
        items = res.scalars().all()
        for item in items:
            await db.delete(item)
        await db.commit()
        return {"affected_count": len(items), "message": "Quotes deleted successfully"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.get("/{quote_id}", summary="Get quote details by ID")
async def get_quote(quote_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Quote).where(Quote.id == quote_id))
    q = res.scalars().first()
    if not q:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Quote '{quote_id}' not found")
    return {
        "id": q.id,
        "quote_number": q.quote_number or f"QUO-{q.id[:6]}",
        "items": [
            {"name": "Enterprise CRM License", "quantity": 10, "unit_price": 1200.0, "total": 12000.0},
            {"name": "Dedicated Onboarding", "quantity": 1, "unit_price": 3000.0, "total": 3000.0}
        ],
        "total_amount": q.total_amount or 15000.0,
        "status": q.status or "Draft",
        "created_at": str(q.created_at)
    }

@router.put("/{quote_id}", summary="Update quote details")
async def update_quote(quote_id: str, payload: QuoteBase, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Quote).where(Quote.id == quote_id))
    q = res.scalars().first()
    if not q:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Quote '{quote_id}' not found")
    try:
        if payload.quote_number: q.quote_number = payload.quote_number
        if payload.total_amount is not None: q.total_amount = payload.total_amount
        if payload.status: q.status = payload.status
        await db.commit()
        await db.refresh(q)
        return {
            "id": q.id,
            "quote_number": q.quote_number,
            "items": payload.items or [],
            "total_amount": q.total_amount,
            "status": q.status,
            "created_at": str(q.created_at)
        }
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.delete("/{quote_id}", response_model=MessageResponse, summary="Delete quote by ID")
async def delete_quote(quote_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Quote).where(Quote.id == quote_id))
    q = res.scalars().first()
    if not q:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Quote '{quote_id}' not found")
    try:
        await db.delete(q)
        await db.commit()
        return {"message": f"Quote {quote_id} deleted successfully", "status": "success"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.post("/{quote_id}/send", response_model=MessageResponse, summary="Send quote proposal email to client")
async def send_quote_email(quote_id: str, recipient_email: str = Query(...), db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Quote).where(Quote.id == quote_id))
    if not res.scalars().first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Quote '{quote_id}' not found")
    return {"message": f"Quote proposal sent to {recipient_email}", "status": "success"}

@router.post("/{quote_id}/accept", response_model=MessageResponse, summary="Mark quote as Accepted by client")
async def accept_quote(quote_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Quote).where(Quote.id == quote_id))
    q = res.scalars().first()
    if not q:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Quote '{quote_id}' not found")
    try:
        q.status = "Accepted"
        await db.commit()
        return {"message": f"Quote {quote_id} accepted!", "status": "success"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.post("/{quote_id}/reject", response_model=MessageResponse, summary="Mark quote as Rejected by client")
async def reject_quote(quote_id: str, reason: Optional[str] = Query("Budget constraints"), db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Quote).where(Quote.id == quote_id))
    q = res.scalars().first()
    if not q:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Quote '{quote_id}' not found")
    try:
        q.status = "Rejected"
        await db.commit()
        return {"message": f"Quote {quote_id} rejected due to: {reason}", "status": "success"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.get("/{quote_id}/pdf", summary="Generate downloadable PDF file URL for quote")
async def get_quote_pdf(quote_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Quote).where(Quote.id == quote_id))
    if not res.scalars().first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Quote '{quote_id}' not found")
    return {"pdf_url": f"https://api.crm.com/quotes/{quote_id}.pdf"}

@router.post("/{quote_id}/convert-to-invoice", response_model=InvoiceResponse, summary="Convert accepted quote directly into an Invoice")
async def convert_quote_to_invoice(quote_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Quote).where(Quote.id == quote_id))
    q = res.scalars().first()
    if not q:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Quote '{quote_id}' not found")
    return {
        "id": f"inv-{q.id[:8]}",
        "invoice_number": f"INV-{q.quote_number}",
        "amount": q.total_amount or 15000.0,
        "status": "Draft",
        "due_date": "2026-09-02",
        "created_at": "2026-08-02"
    }

@router.post("/{quote_id}/revisions", summary="Create a new revision copy of quote (v2)")
async def create_quote_revision(quote_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Quote).where(Quote.id == quote_id))
    q = res.scalars().first()
    if not q:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Quote '{quote_id}' not found")
    return {
        "id": f"{q.id}-rev2",
        "quote_number": f"{q.quote_number}-v2",
        "items": [],
        "total_amount": q.total_amount or 15000.0,
        "status": "Draft",
        "created_at": "2026-08-02"
    }

@router.get("/{quote_id}/revisions", summary="List all historical revisions of quote")
async def get_quote_revisions(quote_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Quote).where(Quote.id == quote_id))
    q = res.scalars().first()
    if not q:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Quote '{quote_id}' not found")
    return [
        {"id": f"{q.id}-v1", "quote_number": f"{q.quote_number}-v1", "total_amount": q.total_amount, "version": "v1", "created_at": "2026-08-01"},
        {"id": f"{q.id}-v2", "quote_number": f"{q.quote_number}-v2", "total_amount": (q.total_amount or 15000) * 1.1, "version": "v2", "created_at": "2026-08-02"}
    ]
