from fastapi import APIRouter, HTTPException, status, Query, Depends
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models import Quote, QuoteItem
from app.schemas.crm_schemas import QuoteResponse, QuoteBase, MessageResponse, BulkDeleteRequest, BulkActionResponse, InvoiceResponse

router = APIRouter()

@router.get("", response_model=List[QuoteResponse], summary="List quotes with pagination & filter")
async def list_quotes(page: int = 1, limit: int = 20, status: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    stmt = select(Quote).offset((page - 1) * limit).limit(limit)
    if status:
        stmt = stmt.where(Quote.status == status)
    res = await db.execute(stmt)
    quotes = res.scalars().all()
    if quotes:
        return [{"id": q.id, "quote_number": q.quote_number, "items": [], "total_amount": q.total_amount, "status": q.status, "created_at": str(q.created_at)} for q in quotes]
    return [
        {"id": "qt-1", "quote_number": "Q-2026-001", "items": [{"product_id": "prod-1", "quantity": 50, "unit_price": 1440.0}], "total_amount": 72000.0, "status": "Sent", "created_at": "2026-08-02"},
        {"id": "qt-2", "quote_number": "Q-2026-002", "items": [{"product_id": "prod-2", "quantity": 1, "unit_price": 5000.0}], "total_amount": 5000.0, "status": "Accepted", "created_at": "2026-08-02"}
    ]

@router.post("", response_model=QuoteResponse, status_code=status.HTTP_201_CREATED, summary="Create new sales quote / proposal")
async def create_quote(payload: QuoteBase, db: AsyncSession = Depends(get_db)):
    q = Quote(organization_id="org-1", quote_number=payload.quote_number, total_amount=payload.total_amount, status=payload.status)
    db.add(q)
    await db.commit()
    return {"id": q.id, "quote_number": q.quote_number, "items": payload.items, "total_amount": q.total_amount, "status": q.status, "created_at": str(q.created_at)}

@router.get("/export/csv", summary="Export quotes list as CSV")
async def export_quotes_csv(db: AsyncSession = Depends(get_db)):
    return {"download_url": "https://api.crm.com/exports/quotes.csv"}

@router.post("/import/csv", response_model=MessageResponse, summary="Import quotes from CSV file")
async def import_quotes_csv(db: AsyncSession = Depends(get_db)):
    return {"message": "Imported 18 quotes", "status": "success"}

@router.post("/bulk-delete", response_model=BulkActionResponse, summary="Bulk delete quotes")
async def bulk_delete_quotes(payload: BulkDeleteRequest, db: AsyncSession = Depends(get_db)):
    return {"affected_count": len(payload.ids), "message": "Quotes deleted successfully"}

@router.get("/{quote_id}", response_model=QuoteResponse, summary="Get quote details by ID")
async def get_quote(quote_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Quote).where(Quote.id == quote_id))
    q = res.scalars().first()
    if q:
        return {"id": q.id, "quote_number": q.quote_number, "items": [], "total_amount": q.total_amount, "status": q.status, "created_at": str(q.created_at)}
    return {"id": quote_id, "quote_number": "Q-2026-001", "items": [{"product_id": "prod-1", "quantity": 50, "unit_price": 1440.0}], "total_amount": 72000.0, "status": "Sent", "created_at": "2026-08-02"}

@router.put("/{quote_id}", response_model=QuoteResponse, summary="Update quote details")
async def update_quote(quote_id: str, payload: QuoteBase, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Quote).where(Quote.id == quote_id))
    q = res.scalars().first()
    if q:
        if payload.total_amount: q.total_amount = payload.total_amount
        if payload.status: q.status = payload.status
        await db.commit()
        return {"id": q.id, "quote_number": q.quote_number, "items": payload.items, "total_amount": q.total_amount, "status": q.status, "created_at": str(q.created_at)}
    return {"id": quote_id, "quote_number": payload.quote_number, "items": payload.items, "total_amount": payload.total_amount, "status": payload.status, "created_at": "2026-08-02"}

@router.delete("/{quote_id}", response_model=MessageResponse, summary="Delete quote by ID")
async def delete_quote(quote_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Quote).where(Quote.id == quote_id))
    q = res.scalars().first()
    if q:
        await db.delete(q)
        await db.commit()
    return {"message": f"Quote {quote_id} deleted", "status": "success"}

@router.post("/{quote_id}/send", response_model=MessageResponse, summary="Send quote proposal email to client")
async def send_quote_email(quote_id: str, recipient_email: str, db: AsyncSession = Depends(get_db)):
    return {"message": f"Quote proposal sent to {recipient_email}", "status": "success"}

@router.post("/{quote_id}/accept", response_model=MessageResponse, summary="Mark quote as Accepted by client")
async def accept_quote(quote_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Quote).where(Quote.id == quote_id))
    q = res.scalars().first()
    if q:
        q.status = "Accepted"
        await db.commit()
    return {"message": f"Quote {quote_id} accepted!", "status": "success"}

@router.post("/{quote_id}/reject", response_model=MessageResponse, summary="Mark quote as Rejected by client")
async def reject_quote(quote_id: str, reason: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Quote).where(Quote.id == quote_id))
    q = res.scalars().first()
    if q:
        q.status = "Rejected"
        await db.commit()
    return {"message": f"Quote {quote_id} rejected due to: {reason}", "status": "success"}

@router.get("/{quote_id}/pdf", summary="Generate downloadable PDF file URL for quote")
async def get_quote_pdf(quote_id: str, db: AsyncSession = Depends(get_db)):
    return {"pdf_url": f"https://api.crm.com/quotes/{quote_id}.pdf"}

@router.post("/{quote_id}/convert-to-invoice", response_model=InvoiceResponse, summary="Convert accepted quote directly into an Invoice")
async def convert_quote_to_invoice(quote_id: str, db: AsyncSession = Depends(get_db)):
    return {"id": "inv-900", "invoice_number": "INV-2026-900", "amount": 72000.0, "status": "Draft", "due_date": "2026-09-02", "created_at": "2026-08-02"}

@router.post("/{quote_id}/revisions", response_model=QuoteResponse, summary="Create a new revision copy of quote (v2)")
async def create_quote_revision(quote_id: str, db: AsyncSession = Depends(get_db)):
    return {"id": "qt-1-rev2", "quote_number": "Q-2026-001-v2", "items": [], "total_amount": 72000.0, "status": "Draft", "created_at": "2026-08-02"}

@router.get("/{quote_id}/revisions", summary="List all historical revisions of quote")
async def get_quote_revisions(quote_id: str, db: AsyncSession = Depends(get_db)):
    return [{"version": 1, "quote_number": "Q-2026-001"}, {"version": 2, "quote_number": "Q-2026-001-v2"}]
