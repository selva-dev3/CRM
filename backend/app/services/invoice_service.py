from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.currency import normalize_currency_code
from app.core.errors import APIException, ConflictError, NotFoundError
from app.core.logging import get_logger
from app.models import User
from app.models.invoice import Invoice, InvoiceItem
from app.models.quote import Quote
from app.repositories.deal_repository import DealRepository
from app.repositories.invoice_repository import InvoiceRepository
from app.repositories.notification_repository import NotificationRepository
from app.repositories.quote_repository import QuoteRepository
from app.services.invoice_state import assert_invoice_transition
from app.services.notification_service import notification_service
from app.services.org_service import organization_service
from app.services.sales_totals import calculate_line, decimal_value

logger = get_logger(__name__)

# Canonical invoice lifecycle statuses (model default + existing frontend filters).
INVOICE_STATUS_DRAFT = "Draft"

# Canonical deal stage representing a confirmed sale (DealService.mark_deal_won writes this value).
DEAL_STAGE_CLOSED_WON = "Closed Won"

DEFAULT_PAYMENT_TERM_DAYS = 30


class DealNotClosedWonError(APIException):
    """Normal customer invoices may only be issued once the deal is Closed Won."""

    status_code = 400
    code = "DEAL_NOT_CLOSED_WON"


def invoice_to_dict(
    inv: Invoice,
    items: list[InvoiceItem] | None = None,
) -> dict:
    data: dict[str, object] = {
        "id": inv.id,
        "quote_id": inv.quote_id,
        "order_id": inv.order_id,
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
        "outstanding_amount": max(
            Decimal(0), decimal_value(inv.amount or 0) - decimal_value(inv.paid_amount or 0)
        ),
        "payment_status": inv.payment_status or "Pending",
        "review_submitted_at": str(inv.review_submitted_at) if inv.review_submitted_at else None,
        "review_submitted_by": inv.review_submitted_by,
        "review_rejection_reason": inv.review_rejection_reason,
        "finalized_at": str(inv.finalized_at) if inv.finalized_at else None,
        "finalized_by": inv.finalized_by,
        "accepted_at": str(inv.accepted_at) if inv.accepted_at else None,
        "billing_snapshot": inv.billing_snapshot,
        "status": inv.status or INVOICE_STATUS_DRAFT,
        "due_date": str(inv.due_date) if inv.due_date else None,
        "notes": inv.notes,
        "sent_at": str(inv.sent_at) if inv.sent_at else None,
        "delivery_status": inv.delivery_status,
        "pdf_available": bool(inv.pdf_s3_key),
        "recipient_email": inv.recipient_email,
        "reminder_count": inv.reminder_count or 0,
        "last_reminded_at": str(inv.last_reminded_at) if inv.last_reminded_at else None,
        "created_at": str(inv.created_at) if inv.created_at else None,
    }
    if items is not None:
        data["items"] = [
            {
                "id": item.id,
                "product_id": item.product_id,
                "product_name": item.product_name,
                "description": item.description,
                "quantity": item.quantity,
                "unit_price": item.unit_price or 0.0,
                "discount_percent": item.discount_percent or 0.0,
                "tax_percent": item.tax_percent or 0.0,
                "subtotal": item.subtotal or 0.0,
                "discount_total": item.discount_total or 0.0,
                "tax_total": item.tax_total or 0.0,
                "total": item.total or 0.0,
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

    def __init__(
        self,
        repository: InvoiceRepository | None = None,
        quote_repository: QuoteRepository | None = None,
    ) -> None:
        self.repository = repository or InvoiceRepository()
        self.quote_repository = quote_repository or QuoteRepository()

    async def create_from_accepted_quote(self, db: AsyncSession, quote: Quote) -> Invoice:
        """The caller owns the quote lock and commits acceptance and invoice together."""
        if quote.status != "Accepted" or not quote.approved_at or not quote.accepted_at:
            raise ConflictError(message="The quote must be approved and accepted")
        existing = await self.repository.get_by_quote(
            db, quote_id=quote.id, organization_id=quote.organization_id
        )
        if existing:
            return existing
        from app.services.order_service import OrderService

        order = await OrderService().ensure_from_accepted_quote(db, quote)
        if not quote.deal_id:
            raise ConflictError(message="Accepted quote has no deal")
        deal = await self.repository.get_deal_scoped(
            db, deal_id=quote.deal_id, organization_id=quote.organization_id
        )
        if not deal or deal.stage != DEAL_STAGE_CLOSED_WON:
            raise DealNotClosedWonError(message="The quoted deal must still be Closed Won")
        company, contact = await DealRepository().get_sales_customer(
            db,
            organization_id=quote.organization_id,
            company_id=quote.company_id,
            contact_id=quote.contact_id,
        )
        if not company or not contact or contact.company_id != company.id:
            raise APIException(message="The quoted customer is invalid")
        address = await self.repository.get_billing_address(
            db, contact_id=contact.id, organization_id=quote.organization_id
        )
        if not address or not address.street or not address.country:
            raise APIException(
                message="Customer billing street and country are required",
                code="BILLING_ADDRESS_REQUIRED",
            )
        lines = await self.quote_repository.list_items(
            db, quote_id=quote.id, organization_id=quote.organization_id
        )
        if not lines or not quote.currency:
            raise APIException(message="Quote items and currency are required")
        totals = [
            calculate_line(line.quantity, line.unit_price, line.discount_percent, line.tax_percent)
            for line in lines
        ]
        total = sum((line.total for line in totals), Decimal(0))
        if total != decimal_value(quote.total_amount) or total <= 0:
            raise APIException(message="Quote total is invalid", code="INVALID_QUOTE_TOTAL")
        if any(not line.product_name for line in lines):
            raise APIException(message="Quote product snapshots are incomplete")
        organization = await self.repository.lock_numbering(db, quote.organization_id)
        if (
            not organization
            or not organization.is_active
            or not organization.invoice_prefix
            or not organization.currency
        ):
            raise NotFoundError(message="Organization not found")
        sequence = await self.repository.advance_numbering(db, organization)
        now = datetime.now(UTC)
        invoice = await self.repository.create(
            db,
            data={
                "id": str(uuid4()),
                "organization_id": quote.organization_id,
                "quote_id": quote.id,
                "order_id": order.id,
                "deal_id": quote.deal_id,
                "company_id": company.id,
                "contact_id": contact.id,
                "currency": quote.currency,
                "invoice_number": f"{organization.invoice_prefix}-{now.year}-{sequence:06d}",
                "amount": total,
                "subtotal": sum((line.subtotal for line in totals), Decimal(0)),
                "discount_total": sum((line.discount for line in totals), Decimal(0)),
                "tax_total": sum((line.tax for line in totals), Decimal(0)),
                "paid_amount": 0,
                "status": INVOICE_STATUS_DRAFT,
                "payment_status": "Pending",
                "due_date": quote.due_date or (now + timedelta(days=DEFAULT_PAYMENT_TERM_DAYS)),
                "billing_snapshot": {
                    "company": company.name,
                    "contact": contact.name,
                    "email": contact.email,
                    "street": address.street,
                    "city": address.city,
                    "state": address.state,
                    "country": address.country,
                    "postal_code": address.postal_code,
                },
            },
        )
        await db.flush()
        await self.repository.add_items(
            db,
            items=[
                {
                    "invoice_id": invoice.id,
                    "product_id": line.product_id,
                    "product_name": line.product_name,
                    "description": line.product_name,
                    "quantity": line.quantity,
                    "unit_price": line.unit_price,
                    "discount_percent": line.discount_percent,
                    "tax_percent": line.tax_percent,
                    "subtotal": total_line.subtotal,
                    "discount_total": total_line.discount,
                    "tax_total": total_line.tax,
                    "total": total_line.total,
                }
                for line, total_line in zip(lines, totals, strict=True)
            ],
        )
        await self.repository.record_creation(db, invoice)
        await NotificationRepository().create_for_scoped_user(
            db,
            data={
                "organization_id": quote.organization_id,
                "user_id": deal.assigned_to or quote.approved_by,
                "event_name": "invoice.created",
                "entity_type": "invoice",
                "entity_id": invoice.id,
                "title": "Invoice automatically created",
                "message": f"Invoice {invoice.invoice_number} is ready for review and finalization.",
            },
        )
        await db.flush()
        return invoice

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

    async def count_invoices(
        self,
        db: AsyncSession,
        *,
        organization_id: str,
        status: str | None = None,
        search: str | None = None,
    ) -> int:
        return await self.repository.count_scoped(
            db, organization_id=organization_id, status=status, search=search
        )

    async def get_invoice(self, db: AsyncSession, *, invoice_id: str, organization_id: str) -> dict:
        invoice = await self.require_invoice(
            db, invoice_id=invoice_id, organization_id=organization_id
        )
        items = await self.repository.list_items(
            db, invoice_id=invoice.id, organization_id=organization_id
        )
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

        generated_quote = await self.quote_repository.get_automatic(
            db, deal_id=deal_id, organization_id=organization_id
        )
        if generated_quote:
            existing_invoice = await self.repository.get_by_quote(
                db, quote_id=generated_quote.id, organization_id=organization_id
            )
            if existing_invoice:
                return await self.get_invoice(
                    db, invoice_id=existing_invoice.id, organization_id=organization_id
                )
            raise ConflictError(
                message="The invoice is created automatically when the customer accepts the quote"
            )

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
        existing = await self.repository.get_by_deal_scoped(
            db, deal_id=deal_id, organization_id=organization_id
        )
        if existing is not None:
            items = await self.repository.list_items(
                db, invoice_id=existing.id, organization_id=organization_id
            )
            return invoice_to_dict(existing, items)

        if not deal.company_id and not deal.contact_id:
            raise APIException(
                message="Deal has no customer attached. Attach a company or contact before invoicing.",
                code="DEAL_MISSING_CUSTOMER",
            )

        deal_products = await self.repository.list_deal_products(
            db, deal_id=deal.id, organization_id=organization_id
        )
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
                    "product_name": product.name,
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
        calculated = [
            calculate_line(
                item["quantity"],
                item["unit_price"],
                item["discount_percent"],
                item["tax_percent"],
            )
            for item in billable
        ]
        subtotal = sum((line.subtotal for line in calculated), Decimal(0))
        discount_total = sum((line.discount for line in calculated), Decimal(0))
        tax_total = sum((line.tax for line in calculated), Decimal(0))
        total = sum((line.total for line in calculated), Decimal(0))

        organization = await self.repository.lock_numbering(db, organization_id)
        if (
            not organization
            or not organization.is_active
            or not organization.invoice_prefix
            or not organization.currency
        ):
            raise NotFoundError(message="Organization not found")
        sequence = await self.repository.advance_numbering(db, organization)
        now = datetime.now(UTC)
        due_date = deal.expected_close_date or (now + timedelta(days=DEFAULT_PAYMENT_TERM_DAYS))

        invoice = await self.repository.create(
            db,
            data={
                "organization_id": organization_id,
                "deal_id": deal.id,
                "company_id": deal.company_id,
                "contact_id": deal.contact_id,
                "invoice_number": (f"{organization.invoice_prefix}-{now.year}-{sequence:06d}"),
                "currency": organization.currency,
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
            items=[
                {
                    **item,
                    "invoice_id": invoice.id,
                    "subtotal": line.subtotal,
                    "discount_total": line.discount,
                    "tax_total": line.tax,
                    "total": line.total,
                }
                for item, line in zip(billable, calculated, strict=True)
            ],
        )
        await self.repository.record_creation(db, invoice)

        try:
            await db.commit()
        except IntegrityError as exc:
            # Concurrent duplicate conversion lost the race on the partial unique index.
            await db.rollback()
            winner = await self.repository.get_by_deal_scoped(
                db, deal_id=deal_id, organization_id=organization_id
            )
            if winner is not None:
                logger.info(
                    "Duplicate invoice conversion for deal %s returned existing invoice %s",
                    deal_id,
                    winner.id,
                )
                items = await self.repository.list_items(
                    db, invoice_id=winner.id, organization_id=organization_id
                )
                return invoice_to_dict(winner, items)
            raise ConflictError(
                message="Failed to create invoice: conflicting record.",
                code="INVOICE_CREATE_CONFLICT",
            ) from exc
        except Exception as exc:
            await db.rollback()
            raise APIException(
                message="Failed to create invoice.", code="INVOICE_CREATE_FAILED"
            ) from exc

        await db.refresh(invoice)
        items = await self.repository.list_items(
            db, invoice_id=invoice.id, organization_id=organization_id
        )

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
        invoice = await self.repository.get_by_deal_scoped(
            db, deal_id=deal_id, organization_id=organization_id
        )
        if invoice is None:
            return []
        items = await self.repository.list_items(
            db, invoice_id=invoice.id, organization_id=organization_id
        )
        return [invoice_to_dict(invoice, items)]

    async def finalize_invoice(
        self, db: AsyncSession, *, invoice_id: str, organization_id: str, user_id: str
    ) -> dict:
        try:
            invoice = await self.repository.lock_scoped(
                db, invoice_id=invoice_id, organization_id=organization_id
            )
            if not invoice:
                raise NotFoundError(message="Invoice not found")
            if invoice.status != "In Review":
                raise ConflictError(message="Only invoices in review can be finalized")
            assert_invoice_transition(invoice.status, "Finalized")
            company, contact = await DealRepository().get_sales_customer(
                db,
                organization_id=organization_id,
                company_id=invoice.company_id,
                contact_id=invoice.contact_id,
            )
            if not company or not contact or contact.company_id != company.id:
                raise APIException(message="Invoice customer is invalid")
            snapshot = invoice.billing_snapshot or {}
            if any(snapshot.get(key) is not None and not isinstance(snapshot[key], str)
                   for key in ("city", "state", "postal_code")):
                raise APIException(message="Billing city, state and postal code must be text")
            if not all(
                isinstance(snapshot.get(key), str) and snapshot[key].strip()
                for key in ("company", "contact", "email", "street", "country")
            ):
                raise APIException(
                    message="Billing company, contact, email, street and country are required"
                )
            try:
                TypeAdapter(EmailStr).validate_python(snapshot["email"])
            except ValidationError as exc:
                raise APIException(message="Billing email is invalid") from exc
            if (
                not contact.email
                or snapshot["email"].strip().casefold() != contact.email.strip().casefold()
            ):
                raise APIException(message="Billing email must match the invoice customer")
            try:
                currency = normalize_currency_code(invoice.currency)
            except ValueError as exc:
                raise APIException(message="Invoice currency is invalid") from exc
            if currency != invoice.currency:
                raise APIException(message="Invoice currency is invalid")
            if not invoice.due_date:
                raise APIException(message="Invoice due date is required")
            items = await self.repository.list_items(
                db, invoice_id=invoice_id, organization_id=organization_id
            )
            if not items or any(
                not item.product_name or not item.product_name.strip() for item in items
            ):
                raise APIException(message="Invoice needs complete line items")
            totals = [
                calculate_line(
                    item.quantity, item.unit_price, item.discount_percent, item.tax_percent
                )
                for item in items
            ]
            for item, line in zip(items, totals, strict=True):
                if any(
                    decimal_value(getattr(item, field)) != getattr(line, calculated)
                    for field, calculated in (
                        ("subtotal", "subtotal"),
                        ("discount_total", "discount"),
                        ("tax_total", "tax"),
                        ("total", "total"),
                    )
                ):
                    raise APIException(message="Invoice line totals are inconsistent")
            for field, calculated in (
                ("subtotal", "subtotal"),
                ("discount_total", "discount"),
                ("tax_total", "tax"),
                ("amount", "total"),
            ):
                if decimal_value(getattr(invoice, field)) != sum(
                    (getattr(line, calculated) for line in totals), Decimal(0)
                ):
                    raise APIException(message="Invoice totals are inconsistent")
            if (
                decimal_value(invoice.amount) <= 0
                or decimal_value(invoice.paid_amount or 0) > invoice.amount
            ):
                raise APIException(message="Invoice amount or paid balance is invalid")
            invoice.status = "Finalized"
            invoice.finalized_at = datetime.now(UTC)
            invoice.finalized_by = user_id
            await self.repository.record_event(
                db, invoice, "invoice.finalized", user_id=user_id
            )
            result = invoice_to_dict(invoice, items)
            await db.commit()
            return result
        except Exception:
            await db.rollback()
            raise

    async def submit_for_review(
        self, db: AsyncSession, *, invoice_id: str, organization_id: str, user_id: str
    ) -> dict:
        try:
            invoice = await self.repository.lock_scoped(
                db, invoice_id=invoice_id, organization_id=organization_id
            )
            if not invoice:
                raise NotFoundError(message="Invoice not found")
            assert_invoice_transition(invoice.status, "In Review")
            invoice.status = "In Review"
            invoice.review_submitted_at = datetime.now(UTC)
            invoice.review_submitted_by = user_id
            invoice.review_rejection_reason = None
            await self.repository.record_event(
                db, invoice, "invoice.review_submitted", user_id=user_id
            )
            await db.commit()
            await db.refresh(invoice)
            items = await self.repository.list_items(
                db, invoice_id=invoice.id, organization_id=organization_id
            )
            return invoice_to_dict(invoice, items)
        except Exception:
            await db.rollback()
            raise

    async def return_to_draft(
        self,
        db: AsyncSession,
        *,
        invoice_id: str,
        organization_id: str,
        user_id: str,
        reason: str | None,
    ) -> dict:
        normalized_reason = (reason or "").strip()
        if not normalized_reason:
            raise APIException(
                message="A review rejection reason is required",
                code="REVIEW_REASON_REQUIRED",
                status_code=422,
            )
        try:
            invoice = await self.repository.lock_scoped(
                db, invoice_id=invoice_id, organization_id=organization_id
            )
            if not invoice:
                raise NotFoundError(message="Invoice not found")
            assert_invoice_transition(invoice.status, "Draft")
            invoice.status = "Draft"
            invoice.review_rejection_reason = normalized_reason
            await self.repository.record_event(
                db, invoice, "invoice.review_rejected", user_id=user_id
            )
            await db.commit()
            await db.refresh(invoice)
            items = await self.repository.list_items(
                db, invoice_id=invoice.id, organization_id=organization_id
            )
            return invoice_to_dict(invoice, items)
        except Exception:
            await db.rollback()
            raise

    async def update_invoice(
        self,
        db: AsyncSession,
        *,
        invoice_id: str,
        organization_id: str,
        amount: float | None,
        status: str | None,
        due_date: datetime | None,
        billing_snapshot: dict | None = None,
    ) -> dict:
        try:
            invoice = await self.repository.lock_scoped(
                db, invoice_id=invoice_id, organization_id=organization_id
            )
            if not invoice:
                raise NotFoundError(message="Invoice not found")
            if status == "Cancelled":
                if invoice.delivery_status in {"Processing", "Unknown"}:
                    raise ConflictError(
                        message="Resolve the active or uncertain delivery before cancellation"
                    )
                if decimal_value(invoice.paid_amount or 0) > 0:
                    raise ConflictError(message="Invoices with payments cannot be cancelled")
                assert_invoice_transition(invoice.status, status)
                invoice.status = status
                invoice.public_token_hash = None
                invoice.public_token_expires_at = None
                invoice.delivery_status = None
                await self.repository.record_event(db, invoice, "invoice.cancelled")
            elif invoice.status != "Draft":
                raise ConflictError(message="Only Draft invoices can be edited")
            if amount is not None and decimal_value(amount) != decimal_value(invoice.amount):
                raise ConflictError(message="Invoice amount must match its line items")
            if status is not None and status not in {"Draft", "Cancelled"}:
                raise ConflictError(message="Use the finalize or public acceptance endpoint")
            if due_date is not None:
                if invoice.status != "Draft":
                    raise ConflictError(message="Only Draft invoices can be edited")
                invoice.due_date = due_date
            if billing_snapshot is not None:
                if invoice.status != "Draft":
                    raise ConflictError(message="Only Draft invoices can be edited")
                invoice.billing_snapshot = billing_snapshot
            await db.commit()
            await db.refresh(invoice)
            items = await self.repository.list_items(
                db, invoice_id=invoice.id, organization_id=organization_id
            )
            return invoice_to_dict(invoice, items)
        except Exception:
            await db.rollback()
            raise

    async def delete_invoice(
        self, db: AsyncSession, *, invoice_id: str, organization_id: str
    ) -> Invoice:
        invoice = await self.repository.lock_scoped(
            db, invoice_id=invoice_id, organization_id=organization_id
        )
        if not invoice:
            raise NotFoundError(message="Invoice not found")
        if (
            invoice.quote_id
            or invoice.status != "Draft"
            or decimal_value(invoice.paid_amount or 0) > 0
        ):
            raise ConflictError(message="Generated or paid invoices cannot be deleted")
        await self.repository.delete(db, invoice)
        await db.commit()
        return invoice

    async def mark_sent(
        self, db: AsyncSession, *, invoice_id: str, organization_id: str, recipient_email: str
    ) -> dict:
        """Queue real PDF generation and email delivery."""
        try:
            invoice = await self.repository.lock_scoped(
                db, invoice_id=invoice_id, organization_id=organization_id
            )
            if not invoice:
                raise NotFoundError(message="Invoice not found")
            if invoice.status not in {"Finalized", "Accepted"} or not invoice.finalized_at:
                raise ConflictError(message="Finalize the invoice before sending")
            expected_email = (invoice.billing_snapshot or {}).get("email")
            if (
                not expected_email
                or recipient_email.strip().casefold() != str(expected_email).strip().casefold()
            ):
                raise APIException(message="Send the invoice only to its customer contact")
            expiry = invoice.public_token_expires_at
            expired = not expiry or (
                expiry.replace(tzinfo=UTC) if expiry.tzinfo is None else expiry
            ) <= datetime.now(UTC)
            renew = invoice.delivery_status == "Sent" and expired
            if invoice.delivery_status in {"Pending", "Processing", "Sent"} and not renew:
                await db.commit()
                return invoice_to_dict(invoice)
            if invoice.delivery_status == "Unknown":
                raise ConflictError(message="Delivery outcome requires provider reconciliation")
            if invoice.delivery_attempts >= 3 and not renew:
                raise ConflictError(message="Invoice delivery attempt limit reached")
            if renew:
                invoice.delivery_attempts = 0
                invoice.delivery_claimed_at = None
            await self.repository.queue_delivery(
                db,
                invoice,
                delivery_id=str(uuid4()),
                recipient_email=str(expected_email),
            )
            await db.commit()
            await db.refresh(invoice)
            return invoice_to_dict(invoice)
        except Exception:
            await db.rollback()
            raise

    async def mark_paid(
        self, db: AsyncSession, *, invoice_id: str, organization_id: str, payment_method: str
    ) -> dict:
        await self.require_invoice(db, invoice_id=invoice_id, organization_id=organization_id)
        raise ConflictError(
            message="Use POST /invoices/{invoice_id}/payments to record a manual payment",
            code="MANUAL_PAYMENT_REQUIRED",
        )


invoice_service = InvoiceService()
