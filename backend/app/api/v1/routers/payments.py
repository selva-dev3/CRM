from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user, require_permission
from app.core.errors import NotFoundError
from app.db.session import get_db
from app.models import User
from app.schemas.crm_schemas import EligiblePaymentInvoiceResponse, PaymentResponse
from app.services.invoice_service import invoice_service
from app.services.payment_service import payment_service

router = APIRouter()


@router.get(
    "",
    response_model=list[PaymentResponse],
    summary="List recorded payments for the current organization",
    dependencies=[Depends(require_permission("invoices:read"))],
)
async def list_payments(
    response: Response,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status_filter: str | None = Query(None, alias="status"),
    search: str | None = Query(None),
    invoice_id: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    organization_id = await invoice_service.resolve_organization_id(db, current_user)
    payments = await payment_service.list_payments(
        db,
        organization_id=organization_id,
        page=page,
        limit=limit,
        status=status_filter,
        search=search,
        invoice_id=invoice_id,
    )
    total = await payment_service.count_payments(
        db,
        organization_id=organization_id,
        status=status_filter,
        search=search,
        invoice_id=invoice_id,
    )
    response.headers["X-Total-Count"] = str(total)
    return payments


@router.get(
    "/eligible-invoices",
    response_model=list[EligiblePaymentInvoiceResponse],
    summary="List accepted invoices with an outstanding balance",
    dependencies=[Depends(require_permission("invoices:payment"))],
)
async def list_eligible_payment_invoices(
    page: int = Query(1, ge=1),
    limit: int = Query(100, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    organization_id = await invoice_service.resolve_organization_id(db, current_user)
    return await payment_service.list_eligible_invoices(
        db, organization_id=organization_id, page=page, limit=limit
    )


@router.get(
    "/{payment_id}",
    response_model=PaymentResponse,
    summary="Get a recorded payment for the current organization",
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
        raise NotFoundError(message="Payment not found")
    return payment
