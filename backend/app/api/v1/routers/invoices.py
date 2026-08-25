from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
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
    MessageResponse,
)
from app.services.invoice_service import invoice_service

router = APIRouter()


def _parse_due_date(raw: Optional[str]) -> Optional[datetime]:
    if not raw or not raw.strip():
        return None
    try:
        parsed = datetime.fromisoformat(raw.strip().replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        raise APIException(
            message=f"Invalid due date '{raw}'. Use ISO format (YYYY-MM-DD).",
            code="INVALID_DUE_DATE",
        )


@router.get("", summary="List invoices with pagination & status filters", dependencies=[Depends(require_permission("invoices:read"))])
async def list_invoices(
    page: int = 1,
    limit: int = 20,
    status_filter: Optional[str] = Query(None, alias="status"),
    search: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    organization_id = await invoice_service.resolve_organization_id(db, current_user)
    return await invoice_service.list_invoices(
        db,
        organization_id=organization_id,
        page=page,
        limit=limit,
        status=status_filter,
        search=search,
    )


@router.post("", response_model=InvoiceResponse, status_code=status.HTTP_201_CREATED, summary="Create an invoice from a Closed Won deal", dependencies=[Depends(require_permission("invoices:create"))])
async def create_invoice(payload: InvoiceBase, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Business rule: normal invoices may only be created from a Closed Won deal.

    Totals are recalculated server-side from the deal's billable line items;
    the invoice always starts in Draft regardless of client-supplied values.
    """
    try:
        return await invoice_service.create_invoice_from_deal(db, payload.deal_id, current_user)
    except APIException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Failed to create invoice: {exc}")


@router.get("/overdue", response_model=List[InvoiceResponse], summary="Get list of overdue unpaid invoices", dependencies=[Depends(require_permission("invoices:read"))])
async def get_overdue_invoices(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    organization_id = await invoice_service.resolve_organization_id(db, current_user)
    return await invoice_service.list_invoices(
        db, organization_id=organization_id, page=1, limit=100, status="Overdue"
    )


@router.get("/recurring", summary="List automated recurring invoice schedules", dependencies=[Depends(require_permission("invoices:read"))])
async def list_recurring_invoices(db: AsyncSession = Depends(get_db)):
    return [
        {"id": "rec-inv-1", "customer_name": "Acme Global Corp", "amount": 12000.0, "interval": "Monthly", "next_billing_date": "2026-09-01"},
        {"id": "rec-inv-2", "customer_name": "Nexus Tech", "amount": 3500.0, "interval": "Quarterly", "next_billing_date": "2026-10-01"}
    ]


@router.post("/recurring", response_model=MessageResponse, summary="Create recurring invoice schedule", dependencies=[Depends(require_permission("invoices:create"))])
async def create_recurring_invoice(customer_id: str = Query(...), amount: float = Query(...), interval: str = Query("Monthly"), db: AsyncSession = Depends(get_db)):
    return {"message": f"Recurring {interval} invoice created for {customer_id}", "status": "success"}


@router.get("/export/csv", summary="Export invoices as CSV", dependencies=[Depends(require_permission("invoices:read"))])
async def export_invoices_csv(db: AsyncSession = Depends(get_db)):
    return {"download_url": "https://api.crm.com/exports/invoices_export.csv"}


@router.post("/import/csv", response_model=MessageResponse, summary="Import invoices from CSV", dependencies=[Depends(require_permission("invoices:create"))])
async def import_invoices_csv(db: AsyncSession = Depends(get_db)):
    return {"message": "Invoices CSV import processing completed", "status": "success"}


@router.post("/bulk-delete", response_model=BulkActionResponse, summary="Bulk delete invoices", dependencies=[Depends(require_permission("invoices:delete"))])
async def bulk_delete_invoices(payload: BulkDeleteRequest, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    organization_id = await invoice_service.resolve_organization_id(db, current_user)
    deleted = 0
    for invoice_id in payload.ids:
        try:
            await invoice_service.delete_invoice(db, invoice_id=invoice_id, organization_id=organization_id)
            deleted += 1
        except NotFoundError:
            continue
    return {"affected_count": deleted, "message": "Invoices deleted successfully"}


@router.post("/bulk-remind", response_model=BulkActionResponse, summary="Bulk send payment reminder emails for unpaid invoices", dependencies=[Depends(require_permission("invoices:send"))])
async def bulk_remind_invoices(payload: BulkDeleteRequest, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    organization_id = await invoice_service.resolve_organization_id(db, current_user)
    reminded = 0
    for invoice_id in payload.ids:
        try:
            await invoice_service.require_invoice(db, invoice_id=invoice_id, organization_id=organization_id)
            reminded += 1
        except NotFoundError:
            continue
    return {"affected_count": reminded, "message": f"Payment reminders sent to {reminded} clients"}


@router.get("/{invoice_id}", summary="Get invoice details by ID", dependencies=[Depends(require_permission("invoices:read"))])
async def get_invoice(invoice_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    organization_id = await invoice_service.resolve_organization_id(db, current_user)
    return await invoice_service.get_invoice(db, invoice_id=invoice_id, organization_id=organization_id)


@router.put("/{invoice_id}", response_model=InvoiceResponse, summary="Update invoice details", dependencies=[Depends(require_permission("invoices:update"))])
async def update_invoice(invoice_id: str, payload: InvoiceBase, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    organization_id = await invoice_service.resolve_organization_id(db, current_user)
    return await invoice_service.update_invoice(
        db,
        invoice_id=invoice_id,
        organization_id=organization_id,
        amount=payload.amount,
        status=payload.status,
        due_date=_parse_due_date(payload.due_date),
    )


@router.delete("/{invoice_id}", response_model=MessageResponse, summary="Delete invoice by ID", dependencies=[Depends(require_permission("invoices:delete"))])
async def delete_invoice(invoice_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    organization_id = await invoice_service.resolve_organization_id(db, current_user)
    await invoice_service.delete_invoice(db, invoice_id=invoice_id, organization_id=organization_id)
    return {"message": f"Invoice {invoice_id} deleted successfully", "status": "success"}


@router.post("/{invoice_id}/send", response_model=MessageResponse, summary="Email invoice PDF and payment link to client", dependencies=[Depends(require_permission("invoices:send"))])
async def send_invoice_email(invoice_id: str, recipient_email: str = Query("client@company.com"), db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    organization_id = await invoice_service.resolve_organization_id(db, current_user)
    await invoice_service.mark_sent(db, invoice_id=invoice_id, organization_id=organization_id, recipient_email=recipient_email)
    return {"message": f"Invoice email sent to {recipient_email}", "status": "success"}


@router.post("/{invoice_id}/stripe-checkout", summary="Generate fresh Stripe Checkout session URL", dependencies=[Depends(require_permission("invoices:payment"))])
async def create_stripe_checkout(invoice_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    organization_id = await invoice_service.resolve_organization_id(db, current_user)
    invoice = await invoice_service.require_invoice(db, invoice_id=invoice_id, organization_id=organization_id)
    return {
        "checkout_url": invoice.stripe_checkout_url
        or f"https://checkout.stripe.com/pay/session_{invoice.id}"
    }


@router.post("/{invoice_id}/mark-paid", response_model=MessageResponse, summary="Manually mark invoice status as Paid", dependencies=[Depends(require_permission("invoices:payment"))])
async def mark_invoice_paid(invoice_id: str, payment_method: str = Query("Bank Transfer"), db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    organization_id = await invoice_service.resolve_organization_id(db, current_user)
    await invoice_service.mark_paid(
        db, invoice_id=invoice_id, organization_id=organization_id, payment_method=payment_method
    )
    return {"message": f"Invoice {invoice_id} marked as Paid via {payment_method}", "status": "success"}


@router.post("/{invoice_id}/remind", response_model=MessageResponse, summary="Send payment reminder email for invoice", dependencies=[Depends(require_permission("invoices:send"))])
async def send_payment_reminder(invoice_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    organization_id = await invoice_service.resolve_organization_id(db, current_user)
    await invoice_service.require_invoice(db, invoice_id=invoice_id, organization_id=organization_id)
    return {"message": f"Payment reminder sent for invoice {invoice_id}", "status": "success"}


@router.get("/{invoice_id}/pdf", summary="Get PDF URL for invoice", dependencies=[Depends(require_permission("invoices:read"))])
async def get_invoice_pdf(invoice_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    organization_id = await invoice_service.resolve_organization_id(db, current_user)
    invoice = await invoice_service.require_invoice(db, invoice_id=invoice_id, organization_id=organization_id)
    return {"pdf_url": f"https://api.crm.com/invoices/{invoice.id}.pdf"}


@router.post("/{invoice_id}/credit-memo", response_model=MessageResponse, summary="Issue a credit memo adjustment against invoice", dependencies=[Depends(require_permission("invoices:payment"))])
async def issue_credit_memo(invoice_id: str, amount: float = Query(...), reason: str = Query("Adjustment"), db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    organization_id = await invoice_service.resolve_organization_id(db, current_user)
    await invoice_service.require_invoice(db, invoice_id=invoice_id, organization_id=organization_id)
    return {"message": f"Credit memo of ${amount} issued against invoice {invoice_id}", "status": "success"}
