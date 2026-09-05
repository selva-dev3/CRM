"""Customer capability endpoints. Tokens are in bodies, never URLs or logs."""

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rate_limiter import limiter
from app.db.session import get_db
from app.schemas.crm_schemas import QuoteResponse
from app.services.quote_service import quote_service

router = APIRouter()


class PublicQuoteRequest(BaseModel):
    token: str = Field(min_length=32, max_length=128)
    reason: str | None = Field(default=None, max_length=500)


class CustomerDecisionResponse(BaseModel):
    quote_id: str
    status: str


class CustomerAcceptanceResponse(CustomerDecisionResponse):
    invoice_id: str
    invoice_number: str
    invoice_status: str


class CustomerCheckoutResponse(BaseModel):
    checkout_url: str


@router.post("/view", response_model=QuoteResponse)
@limiter.limit("30/minute")
async def view_public_quote(
    request: Request, payload: PublicQuoteRequest, db: AsyncSession = Depends(get_db)
):
    return await quote_service.public_quote(db, token=payload.token)


@router.post("/reject", response_model=CustomerDecisionResponse)
@limiter.limit("10/minute")
async def reject_public_quote(
    request: Request, payload: PublicQuoteRequest, db: AsyncSession = Depends(get_db)
):
    return await quote_service.reject_public_quote(db, token=payload.token, reason=payload.reason)


@router.post("/checkout", response_model=CustomerCheckoutResponse)
@limiter.limit("5/minute")
async def checkout_public_quote(
    request: Request, payload: PublicQuoteRequest, db: AsyncSession = Depends(get_db)
):
    return await quote_service.public_checkout(db, token=payload.token)


@router.post("/accept", response_model=CustomerAcceptanceResponse)
@limiter.limit("10/minute")
async def accept_public_quote(
    request: Request, payload: PublicQuoteRequest, db: AsyncSession = Depends(get_db)
):
    return await quote_service.accept_public_quote(db, token=payload.token)
