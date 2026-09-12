from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Header, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user, require_permission
from app.core.errors import APIException, NotFoundError
from app.db.session import get_db
from app.models import User
from app.schemas.crm_schemas import (
    BulkActionResponse,
    BulkDeleteRequest,
    InvoiceBase,
    InvoiceResponse,
    InvoiceUpdate,
    ManualPaymentCreate,
    MessageResponse,
    PaymentResponse,
    ReviewDecisionRequest,
)
from app.services.invoice_delivery_service import invoice_delivery_service
from app.services.invoice_service import invoice_service
from app.services.payment_service import payment_service

router = APIRouter()


async def require_invoice_record_access(
    invoice_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    organization_id = await invoice_service.resolve_organization_id(db, current_user)
    await invoice_service.require_invoice(
        db,
        invoice_id=invoice_id,
        organization_id=organization_id,
        current_user=current_user,
    )


def _parse_due_date(raw: str | None) -> datetime | None:
    if not raw or not raw.strip():
        return None
    try:
        parsed = datetime.fromisoformat(raw.strip().replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    except ValueError as exc:
        raise APIException(
            message=f"Invalid due date '{raw}'. Use ISO format (YYYY-MM-DD).",
            code="INVALID_DUE_DATE",
        ) from exc


@router.get(
    "",
    summary="List invoices with pagination & status filters",
    response_model=list[InvoiceResponse],
    dependencies=[Depends(require_permission("invoices:read"))],
)
async def list_invoices(
    response: Response,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status_filter: str | None = Query(None, alias="status"),
    search: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    organization_id = await invoice_service.resolve_organization_id(db, current_user)
    invoices = await invoice_service.list_invoices(
        db,
        organization_id=organization_id,
        page=page,
        limit=limit,
        status=status_filter,
        search=search,
        current_user=current_user,
    )
    total = await invoice_service.count_invoices(
        db,
        organization_id=organization_id,
        status=status_filter,
        search=search,
        current_user=current_user,
    )
    response.headers["X-Total-Count"] = str(total)
    return invoices


@router.post(
    "",
    response_model=InvoiceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an invoice from a Closed Won deal",
    dependencies=[Depends(require_permission("invoices:create"))],
)
async def create_invoice(
    payload: InvoiceBase,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Business rule: normal invoices may only be created from a Closed Won deal.

    Totals are recalculated server-side from the deal's billable line items;
    the invoice always starts in Draft regardless of client-supplied values.
    """
    return await invoice_service.create_invoice_from_deal(db, payload.deal_id, current_user)


@router.get(
    "/overdue",
    response_model=list[InvoiceResponse],
    summary="Get list of overdue unpaid invoices",
    dependencies=[Depends(require_permission("invoices:read"))],
)
async def get_overdue_invoices(
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    organization_id = await invoice_service.resolve_organization_id(db, current_user)
    return await invoice_service.list_invoices(
        db,
        organization_id=organization_id,
        page=1,
        limit=100,
        status="Overdue",
        current_user=current_user,
    )


@router.get(
    "/recurring",
    summary="List automated recurring invoice schedules",
    dependencies=[Depends(require_permission("invoices:read"))],
)
async def list_recurring_invoices(db: AsyncSession = Depends(get_db)):
    raise APIException(
        message="Recurring invoice schedules are not implemented",
        code="RECURRING_INVOICES_UNAVAILABLE",
        status_code=501,
    )


@router.post(
    "/recurring",
    response_model=MessageResponse,
    summary="Create recurring invoice schedule",
    dependencies=[Depends(require_permission("invoices:create"))],
)
async def create_recurring_invoice(
    customer_id: str = Query(...),
    amount: float = Query(...),
    interval: str = Query("Monthly"),
    db: AsyncSession = Depends(get_db),
):
    raise APIException(
        message="Recurring invoice schedules are not implemented",
        code="RECURRING_INVOICES_UNAVAILABLE",
        status_code=501,
    )


@router.get(
    "/export/csv",
    summary="Export invoices as CSV",
    dependencies=[Depends(require_permission("invoices:export"))],
)
async def export_invoices_csv(db: AsyncSession = Depends(get_db)):
    raise APIException(message="Invoice export is not implemented", status_code=501)


@router.post(
    "/import/csv",
    response_model=MessageResponse,
    summary="Import invoices from CSV",
    dependencies=[Depends(require_permission("invoices:import"))],
)
async def import_invoices_csv(db: AsyncSession = Depends(get_db)):
    raise APIException(message="Invoice import is not implemented", status_code=501)


@router.post(
    "/bulk-delete",
    response_model=BulkActionResponse,
    summary="Bulk delete invoices",
    dependencies=[Depends(require_permission("invoices:delete"))],
)
async def bulk_delete_invoices(
    payload: BulkDeleteRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    organization_id = await invoice_service.resolve_organization_id(db, current_user)
    deleted = 0
    for invoice_id in payload.ids:
        try:
            await invoice_service.delete_invoice(
                db,
                invoice_id=invoice_id,
                organization_id=organization_id,
                current_user=current_user,
            )
            deleted += 1
        except NotFoundError:
            continue
    return {"affected_count": deleted, "message": "Invoices deleted successfully"}


@router.post(
    "/bulk-remind",
    response_model=BulkActionResponse,
    summary="Bulk send payment reminder emails for unpaid invoices",
    dependencies=[Depends(require_permission("invoices:send"))],
)
async def bulk_remind_invoices(
    payload: BulkDeleteRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    organization_id = await invoice_service.resolve_organization_id(db, current_user)
    reminded = 0
    for invoice_id in payload.ids:
        try:
            await invoice_service.require_invoice(
                db,
                invoice_id=invoice_id,
                organization_id=organization_id,
                current_user=current_user,
            )
            await invoice_delivery_service.send_reminder(
                db, invoice_id=invoice_id, organization_id=organization_id
            )
            reminded += 1
        except NotFoundError:
            continue
    return {"affected_count": reminded, "message": f"Payment reminders sent to {reminded} clients"}


@router.get(
    "/{invoice_id}",
    summary="Get invoice details by ID",
    dependencies=[Depends(require_permission("invoices:read"))],
)
async def get_invoice(
    invoice_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    organization_id = await invoice_service.resolve_organization_id(db, current_user)
    return await invoice_service.get_invoice(
        db,
        invoice_id=invoice_id,
        organization_id=organization_id,
        current_user=current_user,
    )


@router.put(
    "/{invoice_id}",
    response_model=InvoiceResponse,
    summary="Update invoice details",
    dependencies=[Depends(require_permission("invoices:update"))],
)
async def update_invoice(
    invoice_id: str,
    payload: InvoiceUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    organization_id = await invoice_service.resolve_organization_id(db, current_user)
    return await invoice_service.update_invoice(
        db,
        invoice_id=invoice_id,
        organization_id=organization_id,
        amount=payload.amount,
        status=payload.status,
        due_date=payload.due_date,
        billing_snapshot=payload.billing_snapshot,
        current_user=current_user,
    )


@router.delete(
    "/{invoice_id}",
    response_model=MessageResponse,
    summary="Delete invoice by ID",
    dependencies=[Depends(require_permission("invoices:delete"))],
)
async def delete_invoice(
    invoice_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    organization_id = await invoice_service.resolve_organization_id(db, current_user)
    await invoice_service.delete_invoice(
        db,
        invoice_id=invoice_id,
        organization_id=organization_id,
        current_user=current_user,
    )
    return {"message": f"Invoice {invoice_id} deleted successfully", "status": "success"}


@router.post(
    "/{invoice_id}/send",
    response_model=MessageResponse,
    summary="Queue finalized invoice PDF and secure review link for the customer",
    dependencies=[
        Depends(require_permission("invoices:send")),
        Depends(require_invoice_record_access),
    ],
)
async def send_invoice_email(
    invoice_id: str,
    recipient_email: str = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    organization_id = await invoice_service.resolve_organization_id(db, current_user)
    invoice = await invoice_service.mark_sent(
        db, invoice_id=invoice_id, organization_id=organization_id, recipient_email=recipient_email
    )
    return {
        "message": f"Invoice delivery queued for {recipient_email}",
        "status": invoice.get("delivery_status") or "Pending",
    }


@router.post(
    "/{invoice_id}/payments",
    response_model=PaymentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record a manual invoice payment",
    dependencies=[
        Depends(require_permission("invoices:payment")),
        Depends(require_invoice_record_access),
    ],
)
async def record_invoice_payment(
    invoice_id: str,
    payload: ManualPaymentCreate,
    idempotency_key: str = Header(..., alias="Idempotency-Key", min_length=1, max_length=128),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    organization_id = await invoice_service.resolve_organization_id(db, current_user)
    return await payment_service.record_payment(
        db,
        invoice_id=invoice_id,
        organization_id=organization_id,
        user_id=current_user.id,
        payload=payload,
        idempotency_key=idempotency_key,
    )


@router.post(
    "/{invoice_id}/submit-for-review",
    response_model=InvoiceResponse,
    dependencies=[
        Depends(require_permission("invoices:update")),
        Depends(require_invoice_record_access),
    ],
)
async def submit_invoice_for_review(
    invoice_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    organization_id = await invoice_service.resolve_organization_id(db, current_user)
    return await invoice_service.submit_for_review(
        db, invoice_id=invoice_id, organization_id=organization_id, user_id=current_user.id
    )


@router.post(
    "/{invoice_id}/finalize",
    response_model=InvoiceResponse,
    dependencies=[
        Depends(require_permission("invoices:update")),
        Depends(require_invoice_record_access),
    ],
)
async def finalize_invoice(
    invoice_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    organization_id = await invoice_service.resolve_organization_id(db, current_user)
    return await invoice_service.finalize_invoice(
        db, invoice_id=invoice_id, organization_id=organization_id, user_id=current_user.id
    )


@router.post(
    "/{invoice_id}/return-to-draft",
    response_model=InvoiceResponse,
    dependencies=[
        Depends(require_permission("invoices:update")),
        Depends(require_invoice_record_access),
    ],
)
async def return_invoice_to_draft(
    invoice_id: str,
    payload: ReviewDecisionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    organization_id = await invoice_service.resolve_organization_id(db, current_user)
    return await invoice_service.return_to_draft(
        db,
        invoice_id=invoice_id,
        organization_id=organization_id,
        user_id=current_user.id,
        reason=payload.reason,
    )


@router.post(
    "/{invoice_id}/mark-paid",
    response_model=MessageResponse,
    summary="Use the manual payments endpoint to record payment",
    dependencies=[
        Depends(require_permission("invoices:payment")),
        Depends(require_invoice_record_access),
    ],
)
async def mark_invoice_paid(
    invoice_id: str,
):
    raise APIException(
        message="Record payment using POST /invoices/{invoice_id}/payments with an Idempotency-Key",
        code="MANUAL_PAYMENT_REQUIRED",
        status_code=501,
    )


@router.post(
    "/{invoice_id}/remind",
    response_model=MessageResponse,
    summary="Send payment reminder email for invoice",
    dependencies=[
        Depends(require_permission("invoices:send")),
        Depends(require_invoice_record_access),
    ],
)
async def send_payment_reminder(
    invoice_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    organization_id = await invoice_service.resolve_organization_id(db, current_user)
    return await invoice_delivery_service.send_reminder(
        db, invoice_id=invoice_id, organization_id=organization_id
    )


@router.get(
    "/{invoice_id}/pdf",
    summary="Get PDF URL for invoice",
    dependencies=[
        Depends(require_permission("invoices:read")),
        Depends(require_invoice_record_access),
    ],
)
async def get_invoice_pdf(
    invoice_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    organization_id = await invoice_service.resolve_organization_id(db, current_user)
    pdf_url = await invoice_delivery_service.pdf_url(
        db, invoice_id=invoice_id, organization_id=organization_id
    )
    return {"pdf_url": pdf_url}


@router.post(
    "/{invoice_id}/credit-memo",
    response_model=MessageResponse,
    summary="Issue a credit memo adjustment against invoice",
    dependencies=[
        Depends(require_permission("invoices:payment")),
        Depends(require_invoice_record_access),
    ],
)
async def issue_credit_memo(
    invoice_id: str,
    amount: float = Query(...),
    reason: str = Query("Adjustment"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    organization_id = await invoice_service.resolve_organization_id(db, current_user)
    await invoice_service.require_invoice(
        db, invoice_id=invoice_id, organization_id=organization_id
    )
    raise APIException(
        message="Credit memos are not implemented",
        code="CREDIT_MEMO_UNAVAILABLE",
        status_code=501,
    )
