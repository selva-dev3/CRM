from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user, require_permission
from app.db.session import get_db
from app.models import User
from app.schemas.crm_schemas import PaymentResponse
from app.services.invoice_service import invoice_service
from app.services.payment_service import payment_service

router = APIRouter()


@router.get(
    "",
    response_model=list[PaymentResponse],
    summary="List verified payments for the current organization",
    dependencies=[Depends(require_permission("invoices:read"))],
)
async def list_payments(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status_filter: str | None = Query(None, alias="status"),
    search: str | None = Query(None),
    invoice_id: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    organization_id = await invoice_service.resolve_organization_id(db, current_user)
    return await payment_service.list_payments(
        db,
        organization_id=organization_id,
        page=page,
        limit=limit,
        status=status_filter,
        search=search,
        invoice_id=invoice_id,
    )


@router.get(
    "/{payment_id}",
    response_model=PaymentResponse,
    summary="Get a verified payment for the current organization",
    dependencies=[Depends(require_permission("invoices:read"))],
)
async def get_payment(
    payment_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    organization_id = await invoice_service.resolve_organization_id(db, current_user)
    payment = await payment_service.get_payment(
        db, payment_id=payment_id, organization_id=organization_id
    )
    if not payment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")
    return payment
