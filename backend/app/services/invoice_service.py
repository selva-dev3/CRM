from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIException, ConflictError, NotFoundError
from app.core.logging import get_logger
from app.models import User
from app.models.invoice import Invoice, InvoiceItem
from app.repositories.invoice_repository import InvoiceRepository
from app.services.notification_service import notification_service
from app.services.org_service import organization_service

logger = get_logger(__name__)

# Canonical invoice lifecycle statuses (model default + existing frontend filters).
INVOICE_STATUS_DRAFT = "Draft"
INVOICE_STATUS_PENDING = "Pending"
INVOICE_STATUS_PAID = "Paid"
INVOICE_STATUS_OVERDUE = "Overdue"
INVOICE_STATUSES = {
    INVOICE_STATUS_DRAFT,
    INVOICE_STATUS_PENDING,
    INVOICE_STATUS_PAID,
    INVOICE_STATUS_OVERDUE,
}

# Canonical deal stage representing a confirmed sale (DealService.mark_deal_won writes this value).
DEAL_STAGE_CLOSED_WON = "Closed Won"

DEFAULT_PAYMENT_TERM_DAYS = 30


class DealNotClosedWonError(APIException):
    """Normal customer invoices may only be issued once the deal is Closed Won."""

    status_code = 400
    code = "DEAL_NOT_CLOSED_WON"


def _generate_invoice_number() -> str:
    """INV-prefixed number following the existing router convention, made collision-safe."""
    return f"INV-{int(time.time())}-{uuid4().hex[:6].upper()}"


def invoice_to_dict(
    inv: Invoice,
    items: list[InvoiceItem] | None = None,
) -> dict:
    data = {
        "id": inv.id,
        "invoice_number": inv.invoice_number or f"INV-{inv.id[:6]}",
        "deal_id": inv.deal_id,
        "company_id": inv.company_id,
        "contact_id": inv.contact_id,
        "currency": inv.currency or "USD",
        "amount": inv.amount or 0.0,
        "subtotal": inv.subtotal or 0.0,
        "discount_total": inv.discount_total or 0.0,
        "tax_total": inv.tax_total or 0.0,
        "paid_amount": inv.paid_amount or 0.0,
        "status": inv.status or INVOICE_STATUS_DRAFT,
        "due_date": str(inv.due_date) if inv.due_date else None,
        "notes": inv.notes,
        "sent_at": str(inv.sent_at) if inv.sent_at else None,
        "stripe_checkout_url": inv.stripe_checkout_url,
        "created_at": str(inv.created_at) if inv.created_at else None,
    }
    if items is not None:
        data["items"] = [
            {
                "id": item.id,
                "product_id": item.product_id,
                "description": item.description,
                "quantity": item.quantity,
                "unit_price": item.unit_price or 0.0,
                "discount_percent": item.discount_percent or 0.0,
                "tax_percent": item.tax_percent or 0.0,
            }
            for item in items
        ]
    return data


class InvoiceService:
    """Business logic for the Invoice domain.

    Enforces the core CRM billing rule: a normal customer invoice can only be
    created from a deal whose stage is ``Closed Won``. Tenant isolation is
    mandatory — every query is scoped by the organization resolved from the
    authenticated user.
    """

    def __init__(self, repository: InvoiceRepository | None = None) -> None:
        self.repository = repository or InvoiceRepository()

    async def require_invoice(
        self, db: AsyncSession, *, invoice_id: str, organization_id: str
    ) -> Invoice:
        invoice = await self.repository.get_scoped(
            db, invoice_id=invoice_id, organization_id=organization_id
        )
        if not invoice:
            raise NotFoundError(message=f"Invoice '{invoice_id}' not found")
        return invoice

    async def resolve_organization_id(self, db: AsyncSession, current_user: User | None) -> str:
        return await organization_service.resolve_valid_org_id(db, current_user)

    async def list_invoices(
        self,
        db: AsyncSession,
        *,
        organization_id: str,
        page: int,
        limit: int,
        status: str | None = None,
        search: str | None = None,
    ) -> list[dict]:
        invoices = await self.repository.list_scoped(
            db,
            organization_id=organization_id,
            page=page,
            limit=limit,
            status=status,
            search=search,
        )
        return [invoice_to_dict(inv) for inv in invoices]

    async def get_invoice(self, db: AsyncSession, *, invoice_id: str, organization_id: str) -> dict:
        invoice = await self.require_invoice(db, invoice_id=invoice_id, organization_id=organization_id)
        items = await self.repository.list_items(db, invoice.id)
        return invoice_to_dict(invoice, items)

    async def create_invoice_from_deal(
        self, db: AsyncSession, deal_id: str, current_user: User | None
    ) -> dict:
        """Convert a Closed Won deal into a Draft invoice (idempotent).

        Steps: resolve tenant → load deal scoped to tenant → enforce Closed Won →
        validate billable line items → compute totals server-side → persist
        invoice + items in one transaction. Duplicate/concurrent conversions
        return the already-existing invoice instead of creating a second one.
        """
        organization_id = await self.resolve_organization_id(db, current_user)

        deal = await self.repository.get_deal_scoped(
            db, deal_id=deal_id, organization_id=organization_id
        )
        if not deal:
            raise NotFoundError(message=f"Deal '{deal_id}' not found")

        if deal.stage != DEAL_STAGE_CLOSED_WON:
            raise DealNotClosedWonError(
                message=(
                    f"Invoice can only be created after the deal is "
                    f"'{DEAL_STAGE_CLOSED_WON}'. Current stage: {deal.stage}"
                )
            )

        # Idempotency pre-check: repeated clicks / retried requests reuse the invoice.
        existing = await self.repository.get_by_deal(db, deal_id)
        if existing is not None:
            items = await self.repository.list_items(db, existing.id)
            return invoice_to_dict(existing, items)

        if not deal.company_id and not deal.contact_id:
            raise APIException(
                message="Deal has no customer attached. Attach a company or contact before invoicing.",
                code="DEAL_MISSING_CUSTOMER",
            )

        deal_products = await self.repository.list_deal_products(db, deal.id)
        billable: list[dict] = []
        for deal_product in deal_products:
            product = await self.repository.get_product_scoped(
                db, product_id=deal_product.product_id, organization_id=organization_id
            )
            if not product:
                raise APIException(
                    message=f"Product '{deal_product.product_id}' on this deal is invalid or belongs to another organization.",
                    code="DEAL_PRODUCT_INVALID",
                )
            quantity = deal_product.quantity or 0
            unit_price = deal_product.unit_price or 0.0
            if quantity < 1:
                raise APIException(
                    message=f"Product '{product.name}' has an invalid quantity ({quantity}).",
                    code="INVALID_LINE_ITEM_QUANTITY",
                )
            if unit_price < 0:
                raise APIException(
                    message=f"Product '{product.name}' has an invalid unit price.",
                    code="INVALID_LINE_ITEM_PRICE",
                )
            billable.append(
                {
                    "product_id": deal_product.product_id,
                    "description": product.name,
                    "quantity": quantity,
                    "unit_price": unit_price,
                    "discount_percent": 0.0,
                    "tax_percent": 0.0,
                }
            )

        if not billable:
            raise APIException(
                message="Deal has no billable line items. Add products before invoicing.",
                code="DEAL_NO_BILLABLE_ITEMS",
            )

        # Single calculation site for invoice money math.
        line_subtotals = [round(item["quantity"] * item["unit_price"], 2) for item in billable]
        subtotal = round(sum(line_subtotals), 2)
        discount_total = round(
            sum(
                line * (item["discount_percent"] / 100.0)
                for line, item in zip(line_subtotals, billable, strict=True)
            ),
            2,
        )
        tax_total = round(
            sum(
                line
                * (1 - item["discount_percent"] / 100.0)
                * (item["tax_percent"] / 100.0)
                for line, item in zip(line_subtotals, billable, strict=True)
            ),
            2,
        )
        total = round(subtotal - discount_total + tax_total, 2)

        now = datetime.now(UTC)
        due_date = deal.expected_close_date or (now + timedelta(days=DEFAULT_PAYMENT_TERM_DAYS))

        invoice = await self.repository.create(
            db,
            data={
                "organization_id": organization_id,
                "deal_id": deal.id,
                "company_id": deal.company_id,
                "contact_id": deal.contact_id,
                "invoice_number": _generate_invoice_number(),
                "currency": "USD",
                "amount": total,
                "subtotal": subtotal,
                "discount_total": discount_total,
                "tax_total": tax_total,
                "paid_amount": 0.0,
                # Server-authoritative lifecycle start: creation never marks an invoice paid.
                "status": INVOICE_STATUS_DRAFT,
                "due_date": due_date,
            },
        )
        # Materialize the server-generated invoice id (Python-side default) before
        # line items reference it — otherwise invoice_items.invoice_id would be NULL.
        await db.flush()
        await self.repository.add_items(
            db,
            items=[{**item, "invoice_id": invoice.id} for item in billable],
        )

        try:
            await db.commit()
        except IntegrityError as exc:
            # Concurrent duplicate conversion lost the race on the partial unique index.
            await db.rollback()
            winner = await self.repository.get_by_deal(db, deal_id)
            if winner is not None:
                logger.info(
                    "Duplicate invoice conversion for deal %s returned existing invoice %s",
                    deal_id,
                    winner.id,
                )
                items = await self.repository.list_items(db, winner.id)
                return invoice_to_dict(winner, items)
            raise ConflictError(
                message="Failed to create invoice: conflicting record.",
                code="INVOICE_CREATE_CONFLICT",
            ) from exc
        except Exception as exc:
            await db.rollback()
            raise APIException(message="Failed to create invoice.", code="INVOICE_CREATE_FAILED") from exc

        await db.refresh(invoice)
        items = await self.repository.list_items(db, invoice.id)

        await notification_service.notify(
            db,
            event_name="invoice.created",
            organization_id=organization_id,
            actor_user_id=current_user.id if current_user else None,
            entity_type="invoice",
            entity_id=invoice.id,
            assigned_to=deal.assigned_to,
            data={
                "id": invoice.id,
                "invoice_number": invoice.invoice_number,
                "amount": invoice.amount,
                "currency": invoice.currency,
                "status": invoice.status,
                "deal_id": deal.id,
            },
        )
        return invoice_to_dict(invoice, items)

    async def list_invoices_for_deal(
        self, db: AsyncSession, *, deal_id: str, organization_id: str
    ) -> list[dict]:
        deal = await self.repository.get_deal_scoped(
            db, deal_id=deal_id, organization_id=organization_id
        )
        if not deal:
            raise NotFoundError(message=f"Deal '{deal_id}' not found")
        invoice = await self.repository.get_by_deal(db, deal_id)
        if invoice is None:
            return []
        items = await self.repository.list_items(db, invoice.id)
        return [invoice_to_dict(invoice, items)]

    async def update_invoice(
        self,
        db: AsyncSession,
        *,
        invoice_id: str,
        organization_id: str,
        amount: float | None,
        status: str | None,
        due_date: datetime | None,
    ) -> dict:
        invoice = await self.require_invoice(db, invoice_id=invoice_id, organization_id=organization_id)
        if amount is not None:
            invoice.amount = amount
        if status is not None:
            if status not in INVOICE_STATUSES:
                raise APIException(
                    message=f"Invalid invoice status '{status}'.",
                    code="INVALID_INVOICE_STATUS",
                )
            invoice.status = status
        if due_date is not None:
            invoice.due_date = due_date
        await db.commit()
        await db.refresh(invoice)
        items = await self.repository.list_items(db, invoice.id)
        return invoice_to_dict(invoice, items)

    async def delete_invoice(self, db: AsyncSession, *, invoice_id: str, organization_id: str) -> Invoice:
        invoice = await self.require_invoice(db, invoice_id=invoice_id, organization_id=organization_id)
        await self.repository.delete(db, invoice)
        await db.commit()
        return invoice

    async def mark_sent(
        self, db: AsyncSession, *, invoice_id: str, organization_id: str, recipient_email: str
    ) -> dict:
        """Persist the send transition: Draft → Pending, stamping ``sent_at``."""
        invoice = await self.require_invoice(db, invoice_id=invoice_id, organization_id=organization_id)
        if invoice.status == INVOICE_STATUS_DRAFT:
            invoice.status = INVOICE_STATUS_PENDING
        invoice.sent_at = datetime.now(UTC)
        await db.commit()
        await db.refresh(invoice)
        return invoice_to_dict(invoice)

    async def mark_paid(
        self, db: AsyncSession, *, invoice_id: str, organization_id: str, payment_method: str
    ) -> dict:
        invoice = await self.require_invoice(db, invoice_id=invoice_id, organization_id=organization_id)
        if invoice.status == INVOICE_STATUS_PAID:
            raise ConflictError(message="Invoice is already marked as Paid.", code="INVOICE_ALREADY_PAID")
        invoice.status = INVOICE_STATUS_PAID
        invoice.paid_amount = invoice.amount or 0.0
        await db.commit()
        await db.refresh(invoice)
        await notification_service.notify(
            db,
            event_name="invoice.paid",
            organization_id=organization_id,
            entity_type="invoice",
            entity_id=invoice.id,
            data={
                "id": invoice.id,
                "invoice_number": invoice.invoice_number,
                "amount": invoice.amount,
                "paid_amount": invoice.paid_amount,
                "status": invoice.status,
                "payment_method": payment_method,
            },
        )
        return invoice_to_dict(invoice)


invoice_service = InvoiceService()
