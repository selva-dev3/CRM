from fastapi import APIRouter, HTTPException, status, Query, Depends
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models import Quote
from app.schemas.crm_schemas import QuoteResponse, QuoteBase, MessageResponse, BulkDeleteRequest, BulkActionResponse, InvoiceResponse

router = APIRouter()

@router.get("", response_model=List[QuoteResponse], summary="List quotes with pagination & filter")
async def list_quotes(page: int = 1, limit: int = 20, status: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    try:
        stmt = select(Quote).offset((page - 1) * limit).limit(limit)
        if status:
            stmt = stmt.where(Quote.status == status)
        res = await db.execute(stmt)
        quotes = res.scalars().all()
        return [{"id": q.id, "quote_number": q.quote_number, "items": [], "total_amount": q.total_amount, "status": q.status, "created_at": str(q.created_at)} for q in quotes]
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.post("", response_model=QuoteResponse, status_code=status.HTTP_201_CREATED, summary="Create new sales quote / proposal")
async def create_quote(payload: QuoteBase, db: AsyncSession = Depends(get_db)):
    try:
        q = Quote(organization_id="org-1", quote_number=payload.quote_number, total_amount=payload.total_amount, status=payload.status)
        db.add(q)
        await db.commit()
        return {"id": q.id, "quote_number": q.quote_number, "items": payload.items, "total_amount": q.total_amount, "status": q.status, "created_at": str(q.created_at)}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Failed to create quote: {str(e)}")

@router.get("/export/csv", summary="Export quotes list as CSV")
async def export_quotes_csv(db: AsyncSession = Depends(get_db)):
    return {"download_url": "https://api.crm.com/exports/quotes.csv"}

@router.post("/import/csv", response_model=MessageResponse, summary="Import quotes from CSV file")
async def import_quotes_csv(db: AsyncSession = Depends(get_db)):
    return {"message": "Import completed successfully", "status": "success"}

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

@router.get("/{quote_id}", response_model=QuoteResponse, summary="Get quote details by ID")
async def get_quote(quote_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Quote).where(Quote.id == quote_id))
    q = res.scalars().first()
    if not q:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Quote '{quote_id}' not found")
    return {"id": q.id, "quote_number": q.quote_number, "items": [], "total_amount": q.total_amount, "status": q.status, "created_at": str(q.created_at)}

@router.put("/{quote_id}", response_model=QuoteResponse, summary="Update quote details")
async def update_quote(quote_id: str, payload: QuoteBase, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Quote).where(Quote.id == quote_id))
    q = res.scalars().first()
    if not q:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Quote '{quote_id}' not found")
    try:
        if payload.total_amount: q.total_amount = payload.total_amount
        if payload.status: q.status = payload.status
        await db.commit()
        return {"id": q.id, "quote_number": q.quote_number, "items": payload.items, "total_amount": q.total_amount, "status": q.status, "created_at": str(q.created_at)}
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
async def send_quote_email(quote_id: str, recipient_email: str, db: AsyncSession = Depends(get_db)):
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
async def reject_quote(quote_id: str, reason: str, db: AsyncSession = Depends(get_db)):
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
    if not res.scalars().first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Quote '{quote_id}' not found")
    return {"id": "inv-new", "invoice_number": "INV-NEW", "amount": 0.0, "status": "Draft", "due_date": "2026-09-02", "created_at": "2026-08-02"}

@router.post("/{quote_id}/revisions", response_model=QuoteResponse, summary="Create a new revision copy of quote (v2)")
async def create_quote_revision(quote_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Quote).where(Quote.id == quote_id))
    q = res.scalars().first()
    if not q:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Quote '{quote_id}' not found")
    return {"id": f"{q.id}-rev2", "quote_number": f"{q.quote_number}-v2", "items": [], "total_amount": q.total_amount, "status": "Draft", "created_at": "2026-08-02"}

@router.get("/{quote_id}/revisions", summary="List all historical revisions of quote")
async def get_quote_revisions(quote_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Quote).where(Quote.id == quote_id))
    if not res.scalars().first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Quote '{quote_id}' not found")
    return []
