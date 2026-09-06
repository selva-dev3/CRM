from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rate_limiter import limiter
from app.db.session import get_db
from app.schemas.crm_schemas import PublicInvoiceRequest, PublicInvoiceResponse
from app.services.public_invoice_service import public_invoice_service

router = APIRouter()


@router.post("/view", response_model=PublicInvoiceResponse)
@limiter.limit("30/minute")
async def view_public_invoice(
    request: Request,
    response: Response,
    payload: PublicInvoiceRequest,
    db: AsyncSession = Depends(get_db),
):
    response.headers["Cache-Control"] = "no-store"
    return await public_invoice_service.view(db, token=payload.token)


@router.post("/accept", response_model=PublicInvoiceResponse)
@limiter.limit("10/minute")
async def accept_public_invoice(
    request: Request,
    response: Response,
    payload: PublicInvoiceRequest,
    db: AsyncSession = Depends(get_db),
):
    response.headers["Cache-Control"] = "no-store"
    return await public_invoice_service.accept(db, token=payload.token)
