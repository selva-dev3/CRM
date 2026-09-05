from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from fastapi import status
from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIException, NotFoundError
from app.core.logging import get_logger
from app.models import User
from app.models.deal import Deal
from app.models.quote import Quote
from app.models.quote_delivery import QuoteDeliveryAttempt
from app.repositories.deal_repository import DealRepository
from app.repositories.invoice_repository import invoice_repository
from app.repositories.notification_repository import NotificationRepository
from app.repositories.quote_repository import QuoteRepository, quote_repository
from app.schemas.crm_schemas import QuoteBase
from app.services.invoice_service import InvoiceService
from app.services.org_service import organization_service
from app.services.quote_delivery_service import acceptance_token
from app.services.quote_state import assert_quote_transition
from app.services.sales_totals import calculate_line, decimal_value

EDITABLE_QUOTE_STATUSES = {"Draft", "Pending Approval"}
DEFAULT_QUOTE_TERM_DAYS = 30
_email_adapter = TypeAdapter(EmailStr)
logger = get_logger(__name__)


def quote_to_dict(quote: Quote) -> dict:
    return {
        "id": quote.id,
        "deal_id": quote.deal_id,
        "quote_number": quote.quote_number,
        "items": [],
        "total_amount": quote.total_amount or 0.0,
        "status": quote.status or "Draft",
        "currency": quote.currency,
        "delivery_status": quote.delivery_status,
        "delivery_id": quote.delivery_id,
        "provider_message_id": quote.provider_message_id,
        "sent_at": quote.sent_at.isoformat() if quote.sent_at else None,
        "accepted_at": quote.accepted_at.isoformat() if quote.accepted_at else None,
        "recipient_email": quote.recipient_email,
        "pdf_available": bool(quote.pdf_s3_key),
        "expires_at": quote.expires_at.isoformat() if quote.expires_at else None,
        "due_date": quote.due_date.isoformat() if quote.due_date else None,
        "payment_terms": quote.payment_terms,
        "company_name": None,
        "contact_name": None,
        "contact_email": None,
        "rejection_reason": quote.rejection_reason,
        "created_at": str(quote.created_at) if quote.created_at else "",
    }


class QuoteService:
    def __init__(
        self,
        repository: QuoteRepository | None = None,
        deal_repository: DealRepository | None = None,
    ) -> None:
        self.repository = repository or quote_repository
        self.deal_repository = deal_repository or DealRepository()

    async def approve_quote(
        self, db: AsyncSession, *, quote_id: str, organization_id: str, actor_id: str
    ) -> dict:
        await self._require_quote(db, quote_id=quote_id, organization_id=organization_id)
        raise APIException(
            message="Internal approval is not part of the customer quote workflow; send the quote to the linked contact",
            code="INTERNAL_APPROVAL_REMOVED",
            status_code=409,
        )

    async def accept_public_quote(self, db: AsyncSession, *, token: str) -> dict:
        try:
            quote = await self.repository.lock_public(
                db, hashlib.sha256(token.encode()).hexdigest()
            )
            if not quote:
                raise NotFoundError(message="Quote link is invalid")
            if not quote.expires_at or quote.expires_at <= datetime.now(UTC):
                raise APIException(message="Quote link has expired", status_code=410)
            if quote.status != "Accepted":
                if quote.status != "Sent" or not quote.sent_at:
                    raise APIException(
                        message="Only a sent, approved quote can be accepted", status_code=409
                    )
                if not quote.expires_at or quote.expires_at <= datetime.now(UTC):
                    raise APIException(message="Quote has expired", status_code=410)
                company, contact = await self.deal_repository.get_sales_customer(
                    db,
                    organization_id=quote.organization_id,
                    company_id=quote.company_id,
                    contact_id=quote.contact_id,
                )
                if not company or not contact or contact.company_id != company.id:
                    raise APIException(message="Quote customer is invalid")
                await self.repository.accept_public(
                    db,
                    quote,
                    customer_email=quote.recipient_email or contact.email,
                    at=datetime.now(UTC),
                )
            invoice = await InvoiceService().create_from_accepted_quote(db, quote)
            await db.commit()
            return {
                "quote_id": quote.id,
                "status": quote.status,
                "invoice_id": invoice.id,
                "invoice_number": invoice.invoice_number,
                "invoice_status": invoice.status,
            }
        except Exception:
            await db.rollback()
            raise

    async def public_quote(self, db: AsyncSession, *, token: str) -> dict:
        try:
            quote = await self.repository.lock_public(
                db, hashlib.sha256(token.encode()).hexdigest()
            )
            if not quote or not quote.sent_at:
                raise NotFoundError(message="Quote link is invalid")
            if not quote.expires_at or quote.expires_at <= datetime.now(UTC):
                raise APIException(message="Quote link has expired", status_code=410)
            if quote.status not in {"Sent", "Accepted", "Rejected"}:
                raise APIException(message="Quote is not available", status_code=409)
            result = await self.get_quote(
                db, quote_id=quote.id, organization_id=quote.organization_id
            )
            invoice = await invoice_repository.get_by_quote(
                db, quote_id=quote.id, organization_id=quote.organization_id
            )
            result["invoice_id"] = invoice.id if invoice else None
            result["invoice_number"] = invoice.invoice_number if invoice else None
            result["invoice_status"] = invoice.status if invoice else None
            await db.commit()
            return result
        except Exception:
            await db.rollback()
            raise

    async def reject_public_quote(
        self, db: AsyncSession, *, token: str, reason: str | None = None
    ) -> dict:
        try:
            quote = await self.repository.lock_public(
                db, hashlib.sha256(token.encode()).hexdigest()
            )
            if not quote or not quote.sent_at:
                raise NotFoundError(message="Quote link is invalid")
            if not quote.expires_at or quote.expires_at <= datetime.now(UTC):
                raise APIException(message="Quote link has expired", status_code=410)
            if quote.status not in {"Sent", "Rejected"}:
                raise APIException(
                    message="Quote cannot be rejected in its current state", status_code=409
                )
            if quote.status == "Sent":
                await self.repository.reject_public(db, quote, reason=reason)
            await db.commit()
            return {"quote_id": quote.id, "status": quote.status}
        except Exception:
            await db.rollback()
            raise

    async def public_checkout(self, db: AsyncSession, *, token: str) -> dict:
        from app.services.invoice_payment_service import InvoicePaymentService

        try:
            quote = await self.repository.lock_public(
                db, hashlib.sha256(token.encode()).hexdigest()
            )
            if not quote or quote.status != "Accepted":
                raise NotFoundError(message="Accepted quote not found")
            if not quote.expires_at or quote.expires_at <= datetime.now(UTC):
                raise APIException(message="Quote link has expired", status_code=410)
            invoice = await invoice_repository.get_by_quote(
                db, quote_id=quote.id, organization_id=quote.organization_id
            )
            if not invoice:
                raise NotFoundError(message="Invoice not found")
            invoice_id, organization_id = invoice.id, quote.organization_id
            await db.commit()
            return await InvoicePaymentService().checkout(
                db, invoice_id=invoice_id, organization_id=organization_id, public_customer=True
            )
        except Exception:
            await db.rollback()
            raise

    async def create_from_won_deal(self, db: AsyncSession, *, deal: Deal, actor_id: str) -> Quote:
        """Caller holds the scoped deal lock and owns the transaction; never commits here."""
        if deal.stage != "Closed Won":
            raise APIException(
                message="Only a Closed Won deal can generate a quote", code="INVALID_DEAL_STAGE"
            )
        existing = await self.repository.get_automatic(
            db,
            deal_id=deal.id,
            organization_id=deal.organization_id,
        )
        if existing:
            return existing
        organization = await self.repository.lock_numbering(db, deal.organization_id)
        if not organization or not organization.currency or not organization.quote_prefix:
            raise APIException(
                message="Configure the organization currency and quote prefix before closing a deal"
            )
        if not deal.company_id:
            raise APIException(
                message="Select a company before marking the deal won",
                code="DEAL_COMPANY_REQUIRED",
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            )
        if not deal.contact_id:
            raise APIException(
                message="Select a contact before marking the deal won",
                code="DEAL_CONTACT_REQUIRED",
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            )
        company, contact = await self.deal_repository.get_sales_customer(
            db,
            organization_id=deal.organization_id,
            company_id=deal.company_id,
            contact_id=deal.contact_id,
        )
        if not company:
            raise APIException(
                message="The selected company is not available in this organization",
                code="DEAL_COMPANY_REQUIRED",
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            )
        if not contact:
            raise APIException(
                message="The selected contact is not available in this organization",
                code="DEAL_CONTACT_REQUIRED",
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            )
        if contact.company_id != company.id:
            raise APIException(
                message="The selected contact is not linked to the selected company",
                code="DEAL_CONTACT_COMPANY_MISMATCH",
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            )
        lines = await self.deal_repository.list_deal_products(
            db, deal.id, organization_id=deal.organization_id
        )
        if not lines:
            raise APIException(
                message="Add products before closing the deal", code="DEAL_ITEMS_REQUIRED"
            )
        quote_id = str(uuid4())
        items = []
        total = Decimal(0)
        for line in lines:
            product = await invoice_repository.get_product_scoped(
                db,
                product_id=line.product_id,
                organization_id=deal.organization_id,
            )
            if not product:
                raise APIException(
                    message="A deal product is missing or belongs to another organization"
                )
            amounts = calculate_line(
                line.quantity, line.unit_price, line.discount_percent or 0, line.tax_percent or 0
            )
            total += amounts.total
            decimal_value(total)
            items.append(
                {
                    "quote_id": quote_id,
                    "product_id": product.id,
                    "product_name": line.product_name or product.name,
                    "quantity": line.quantity,
                    "unit_price": line.unit_price,
                    "discount_percent": line.discount_percent or 0,
                    "tax_percent": line.tax_percent or 0,
                    "subtotal": amounts.subtotal,
                    "discount_total": amounts.discount,
                    "tax_total": amounts.tax,
                    "total": amounts.total,
                }
            )
        sequence = await self.repository.advance_numbering(db, organization)
        now = datetime.now(UTC)
        quote = await self.repository.create(
            db,
            data={
                "id": quote_id,
                "organization_id": deal.organization_id,
                "deal_id": deal.id,
                "automatic_deal_id": deal.id,
                "company_id": company.id,
                "contact_id": contact.id,
                "currency": organization.currency.upper(),
                "quote_number": f"{organization.quote_prefix}-{now.year}-{sequence:06d}",
                "status": "Draft",
                "total_amount": total,
                "payment_terms": f"Net {DEFAULT_QUOTE_TERM_DAYS}",
                "due_date": now + timedelta(days=DEFAULT_QUOTE_TERM_DAYS),
            },
        )
        await db.flush()
        await self.repository.add_items(db, items)
        await self.repository.record_automatic_creation(db, quote, actor_id)
        await NotificationRepository().create_for_scoped_user(
            db,
            data={
                "organization_id": deal.organization_id,
                "user_id": deal.assigned_to or actor_id,
                "event_name": "deal.won",
                "entity_type": "quote",
                "entity_id": quote.id,
                "title": "Quote automatically created",
                "message": f"Quote {quote.quote_number} is ready for review.",
            },
        )
        await db.flush()
        return quote

    async def resolve_organization_id(self, db: AsyncSession, current_user: User) -> str:
        return await organization_service.resolve_valid_org_id(db, current_user)

    async def _commit(self, db: AsyncSession, message: str) -> None:
        try:
            await db.commit()
        except Exception as exc:
            await db.rollback()
            raise APIException(message=message) from exc

    async def _require_quote(
        self, db: AsyncSession, *, quote_id: str, organization_id: str
    ) -> Quote:
        quote = await self.repository.get_scoped(
            db, quote_id=quote_id, organization_id=organization_id
        )
        if not quote:
            raise NotFoundError(message=f"Quote '{quote_id}' not found")
        return quote

    async def _require_deal(self, db: AsyncSession, *, deal_id: str, organization_id: str) -> Deal:
        deal = await self.deal_repository.get_by_id_scoped(
            db, deal_id=deal_id, organization_id=organization_id
        )
        if not deal:
            raise NotFoundError(message=f"Deal '{deal_id}' not found")
        return deal

    async def list_quotes(
        self,
        db: AsyncSession,
        *,
        organization_id: str,
        page: int,
        limit: int,
        status: str | None,
        search: str | None,
    ) -> list[dict]:
        quotes = await self.repository.list_scoped(
            db,
            organization_id=organization_id,
            page=page,
            limit=limit,
            status=status,
            search=search,
        )
        return [quote_to_dict(quote) for quote in quotes]

    async def list_quotes_for_deal(
        self, db: AsyncSession, *, deal_id: str, organization_id: str
    ) -> list[dict]:
        quotes = await self.repository.list_by_deal(
            db, deal_id=deal_id, organization_id=organization_id
        )
        return [quote_to_dict(quote) for quote in quotes]

    async def get_quote(self, db: AsyncSession, *, quote_id: str, organization_id: str) -> dict:
        quote = await self._require_quote(db, quote_id=quote_id, organization_id=organization_id)
        result = quote_to_dict(quote)
        items = await self.repository.list_items(
            db, quote_id=quote_id, organization_id=organization_id
        )
        result["items"] = [
            {
                "id": item.id,
                "product_id": item.product_id,
                "product_name": item.product_name,
                "quantity": item.quantity,
                "unit_price": item.unit_price,
                "discount_percent": item.discount_percent,
                "tax_percent": item.tax_percent,
                "subtotal": item.subtotal,
                "discount_total": item.discount_total,
                "tax_total": item.tax_total,
                "total": item.total,
            }
            for item in items
        ]
        company, contact = await self.deal_repository.get_sales_customer(
            db,
            organization_id=organization_id,
            company_id=quote.company_id,
            contact_id=quote.contact_id,
        )
        result["recipient_email"] = quote.recipient_email or (contact.email if contact else None)
        result["company_name"] = company.name if company else None
        result["contact_name"] = contact.name if contact else None
        result["contact_email"] = contact.email if contact else None
        invoice = await self.repository.get_invoice_reference(
            db, quote_id=quote_id, organization_id=organization_id
        )
        result.update(
            invoice_id=invoice.id if invoice else None,
            invoice_number=invoice.invoice_number if invoice else None,
            invoice_status=invoice.status if invoice else None,
        )
        return result

    async def create_quote(
        self, db: AsyncSession, *, payload: QuoteBase, current_user: User
    ) -> dict:
        await self.resolve_organization_id(db, current_user)
        raise APIException(
            message="Quotes are created automatically when a deal is marked Closed Won",
            code="AUTOMATIC_QUOTE_REQUIRED",
            status_code=409,
        )

    async def update_quote(
        self,
        db: AsyncSession,
        *,
        quote_id: str,
        payload: QuoteBase,
        organization_id: str,
    ) -> dict:
        quote = await self._require_quote(db, quote_id=quote_id, organization_id=organization_id)
        if quote.automatic_deal_id:
            raise APIException(
                message="Generated quote totals and customer links cannot be overwritten",
                code="QUOTE_IMMUTABLE",
                status_code=409,
            )
        deal = await self._require_deal(
            db, deal_id=payload.deal_id, organization_id=organization_id
        )
        if payload.status not in EDITABLE_QUOTE_STATUSES:
            raise APIException(
                message="Quote delivery and customer decision states cannot be set manually",
                code="INVALID_QUOTE_TRANSITION",
                status_code=409,
            )
        quote.deal_id = deal.id
        quote.quote_number = payload.quote_number.strip() or quote.quote_number
        quote.total_amount = decimal_value(payload.total_amount)
        assert_quote_transition(quote.status, payload.status)
        quote.status = payload.status
        if payload.payment_terms:
            quote.payment_terms = payload.payment_terms.strip()
        if payload.due_date:
            try:
                parsed_due_date = datetime.fromisoformat(payload.due_date.replace("Z", "+00:00"))
            except ValueError as exc:
                raise APIException(message="Invalid quote due date", code="INVALID_DUE_DATE") from exc
            quote.due_date = parsed_due_date if parsed_due_date.tzinfo else parsed_due_date.replace(tzinfo=UTC)
        await self._commit(db, "Failed to update quote")
        await db.refresh(quote)
        return quote_to_dict(quote)

    async def delete_quote(self, db: AsyncSession, *, quote_id: str, organization_id: str) -> None:
        deleted = await self.repository.delete_scoped(
            db, quote_id=quote_id, organization_id=organization_id
        )
        if not deleted:
            raise NotFoundError(message=f"Quote '{quote_id}' not found")
        await self._commit(db, "Failed to delete quote")

    async def bulk_delete_quotes(
        self, db: AsyncSession, *, quote_ids: list[str], organization_id: str
    ) -> dict:
        affected_count = await self.repository.bulk_delete_scoped(
            db, quote_ids=quote_ids, organization_id=organization_id
        )
        await self._commit(db, "Failed to bulk delete quotes")
        return {
            "affected_count": affected_count,
            "message": "Quotes deleted successfully",
        }

    async def send_quote(
        self,
        db: AsyncSession,
        *,
        quote_id: str,
        recipient_email: str | None,
        organization_id: str,
    ) -> dict:
        from app.services.quote_delivery_service import quote_delivery_service

        await self._require_quote(db, quote_id=quote_id, organization_id=organization_id)
        return await quote_delivery_service.queue(
            db, quote_id=quote_id, organization_id=organization_id, recipient_email=recipient_email
        )

    async def accept_quote(self, db: AsyncSession, *, quote_id: str, organization_id: str) -> dict:
        await self._require_quote(db, quote_id=quote_id, organization_id=organization_id)
        raise APIException(
            message="Customer acceptance requires a secure acceptance link",
            code="CUSTOMER_ACCEPTANCE_REQUIRED",
            status_code=409,
        )

    async def reject_quote(
        self,
        db: AsyncSession,
        *,
        quote_id: str,
        reason: str | None,
        organization_id: str,
    ) -> dict:
        quote = await self._require_quote(db, quote_id=quote_id, organization_id=organization_id)
        if quote.automatic_deal_id or quote.status == "Accepted":
            raise APIException(message="Use the secure customer decision workflow", status_code=409)
        assert_quote_transition(quote.status, "Rejected")
        quote.status = "Rejected"
        quote.rejection_reason = reason
        await self._commit(db, "Failed to reject quote")
        return {
            "message": f"Quote {quote_id} rejected due to: {reason}",
            "status": "success",
        }

    async def get_quote_pdf(self, db: AsyncSession, *, quote_id: str, organization_id: str) -> dict:
        import asyncio

        from app.services.s3_service import s3_service

        quote = await self._require_quote(db, quote_id=quote_id, organization_id=organization_id)
        if not quote.pdf_s3_key:
            raise NotFoundError(message="Quote PDF has not been generated yet")
        url = await asyncio.to_thread(s3_service.generate_presigned_url, quote.pdf_s3_key)
        return {"pdf_url": url}

    async def convert_quote_to_invoice(
        self, db: AsyncSession, *, quote_id: str, organization_id: str
    ) -> dict:
        quote = await self._require_quote(db, quote_id=quote_id, organization_id=organization_id)
        invoice = await invoice_repository.get_by_quote(
            db, quote_id=quote.id, organization_id=organization_id
        )
        if not invoice:
            raise APIException(
                message="Invoices are created automatically after secure customer acceptance",
                code="CUSTOMER_ACCEPTANCE_REQUIRED",
                status_code=409,
            )
        from app.services.invoice_service import invoice_to_dict

        return invoice_to_dict(invoice)

    async def create_quote_revision(
        self, db: AsyncSession, *, quote_id: str, organization_id: str
    ) -> dict:
        await self._require_quote(db, quote_id=quote_id, organization_id=organization_id)
        raise APIException(message="Quote revisions are not supported", status_code=409)

    async def get_quote_revisions(
        self, db: AsyncSession, *, quote_id: str, organization_id: str
    ) -> list[dict]:
        await self._require_quote(db, quote_id=quote_id, organization_id=organization_id)
        raise APIException(message="Quote revisions are not supported", status_code=501)


quote_service = QuoteService()
