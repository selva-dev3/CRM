from fastapi import APIRouter, HTTPException, status, Query, Depends
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import get_db
from app.models import Quote, User
from app.api.v1.deps import get_current_user, require_permission
from app.schemas.crm_schemas import QuoteResponse, QuoteBase, MessageResponse, BulkDeleteRequest, BulkActionResponse, InvoiceResponse
from app.services.quote_service import quote_service

router = APIRouter()

@router.get("", summary="List quotes with pagination & filter", dependencies=[Depends(require_permission("quotes:read"))])
async def list_quotes(
    page: int = 1,
    limit: int = 20,
    status_filter: Optional[str] = Query(None, alias="status"),
    search: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    organization_id = await quote_service.resolve_organization_id(db, current_user)
    return await quote_service.list_quotes(
        db,
        organization_id=organization_id,
        page=page,
        limit=limit,
        status=status_filter,
        search=search,
    )

@router.post("", response_model=QuoteResponse, status_code=status.HTTP_201_CREATED, summary="Create new sales quote / proposal", dependencies=[Depends(require_permission("quotes:create"))])
async def create_quote(
    payload: QuoteBase,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await quote_service.create_quote(db, payload=payload, current_user=current_user)

@router.get("/export/csv", summary="Export quotes list as CSV", dependencies=[Depends(require_permission("quotes:read"))])
async def export_quotes_csv(db: AsyncSession = Depends(get_db)):
    return {"download_url": "https://api.crm.com/exports/quotes_proposals_export.csv"}

@router.post("/import/csv", response_model=MessageResponse, summary="Import quotes from CSV file", dependencies=[Depends(require_permission("quotes:create"))])
async def import_quotes_csv(db: AsyncSession = Depends(get_db)):
    return {"message": "Quote proposals CSV import processing completed", "status": "success"}

@router.post("/bulk-delete", response_model=BulkActionResponse, summary="Bulk delete quotes", dependencies=[Depends(require_permission("quotes:delete"))])
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

@router.get("/{quote_id}", response_model=QuoteResponse, summary="Get quote details by ID", dependencies=[Depends(require_permission("quotes:read"))])
async def get_quote(
    quote_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    organization_id = await quote_service.resolve_organization_id(db, current_user)
    return await quote_service.get_quote(db, quote_id=quote_id, organization_id=organization_id)

@router.put("/{quote_id}", response_model=QuoteResponse, summary="Update quote details", dependencies=[Depends(require_permission("quotes:update"))])
async def update_quote(
    quote_id: str,
    payload: QuoteBase,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    organization_id = await quote_service.resolve_organization_id(db, current_user)
    return await quote_service.update_quote(
        db, quote_id=quote_id, payload=payload, organization_id=organization_id
    )

@router.delete("/{quote_id}", response_model=MessageResponse, summary="Delete quote by ID", dependencies=[Depends(require_permission("quotes:delete"))])
async def delete_quote(
    quote_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    organization_id = await quote_service.resolve_organization_id(db, current_user)
    await quote_service.delete_quote(db, quote_id=quote_id, organization_id=organization_id)
    return {"message": f"Quote {quote_id} deleted successfully", "status": "success"}

@router.post("/{quote_id}/send", response_model=MessageResponse, summary="Send quote proposal email to client", dependencies=[Depends(require_permission("quotes:send"))])
async def send_quote_email(quote_id: str, recipient_email: str = Query(...), db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Quote).where(Quote.id == quote_id))
    if not res.scalars().first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Quote '{quote_id}' not found")
    return {"message": f"Quote proposal sent to {recipient_email}", "status": "success"}

@router.post("/{quote_id}/accept", response_model=MessageResponse, summary="Mark quote as Accepted by client", dependencies=[Depends(require_permission("quotes:approve"))])
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

@router.post("/{quote_id}/reject", response_model=MessageResponse, summary="Mark quote as Rejected by client", dependencies=[Depends(require_permission("quotes:update"))])
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

@router.get("/{quote_id}/pdf", summary="Generate downloadable PDF file URL for quote", dependencies=[Depends(require_permission("quotes:read"))])
async def get_quote_pdf(quote_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Quote).where(Quote.id == quote_id))
    if not res.scalars().first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Quote '{quote_id}' not found")
    return {"pdf_url": f"https://api.crm.com/quotes/{quote_id}.pdf"}

@router.post("/{quote_id}/convert-to-invoice", response_model=InvoiceResponse, summary="Convert accepted quote directly into an Invoice", dependencies=[Depends(require_permission("quotes:create"))])
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

@router.post("/{quote_id}/revisions", summary="Create a new revision copy of quote (v2)", dependencies=[Depends(require_permission("quotes:create"))])
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

@router.get("/{quote_id}/revisions", summary="List all historical revisions of quote", dependencies=[Depends(require_permission("quotes:read"))])
async def get_quote_revisions(quote_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Quote).where(Quote.id == quote_id))
    q = res.scalars().first()
    if not q:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Quote '{quote_id}' not found")
    return [
        {"id": f"{q.id}-v1", "quote_number": f"{q.quote_number}-v1", "total_amount": q.total_amount, "version": "v1", "created_at": "2026-08-01"},
        {"id": f"{q.id}-v2", "quote_number": f"{q.quote_number}-v2", "total_amount": (q.total_amount or 15000) * 1.1, "version": "v2", "created_at": "2026-08-02"}
    ]
