from __future__ import annotations

import hashlib
import time
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIException, NotFoundError
from app.models import User
from app.models.deal import Deal
from app.models.quote import Quote
from app.repositories.deal_repository import DealRepository
from app.repositories.invoice_repository import invoice_repository
from app.repositories.notification_repository import NotificationRepository
from app.repositories.quote_repository import QuoteRepository, quote_repository
from app.schemas.crm_schemas import QuoteBase
from app.services.invoice_service import InvoiceService
from app.services.org_service import organization_service
from app.services.sales_totals import calculate_line, decimal_value

QUOTE_STATUSES = {"Draft", "Sent", "Accepted", "Rejected"}


def quote_to_dict(quote: Quote) -> dict:
    return {
        "id": quote.id,
        "deal_id": quote.deal_id,
        "quote_number": quote.quote_number or f"QUO-{quote.id[:6]}",
        "items": [],
        "total_amount": quote.total_amount or 0.0,
        "status": quote.status or "Draft",
        "currency": quote.currency,
        "delivery_status": quote.delivery_status,
        "recipient_email": quote.recipient_email,
        "pdf_available": bool(quote.pdf_s3_key),
        "expires_at": quote.expires_at.isoformat() if quote.expires_at else None,
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

    async def approve_quote(self, db: AsyncSession, *, quote_id: str, organization_id: str,
                            actor_id: str) -> dict:
        try:
            quote = await self.repository.lock_scoped(db, quote_id=quote_id, organization_id=organization_id)
            if not quote:
                raise NotFoundError(message="Quote not found")
            if quote.status == "Approved" and quote.approved_at:
                result = quote_to_dict(quote)
                await db.commit()
                return result
            if quote.status not in {"Draft", "Pending Approval"}:
                raise APIException(message="Quote cannot be approved in its current state", status_code=409)
            items = await self.repository.list_items(db, quote_id=quote_id, organization_id=organization_id)
            if not items or not quote.currency:
                raise APIException(message="Quote must have priced items and a currency")
            calculated = sum((calculate_line(item.quantity, item.unit_price, item.discount_percent,
                item.tax_percent).total for item in items), Decimal(0))
            if calculated != decimal_value(quote.total_amount) or calculated <= 0:
                raise APIException(message="Quote totals are invalid")
            company, contact = await self.deal_repository.get_sales_customer(db,
                organization_id=organization_id, company_id=quote.company_id, contact_id=quote.contact_id)
            if not company or not contact or contact.company_id != company.id or not contact.email:
                raise APIException(message="A valid customer and contact email are required")
            now = datetime.now(UTC)
            await self.repository.approve(db, quote, actor_id=actor_id, at=now, expires_at=now + timedelta(days=30))
            await db.commit()
            return quote_to_dict(quote)
        except Exception:
            await db.rollback()
            raise

    async def accept_public_quote(self, db: AsyncSession, *, token: str) -> dict:
        try:
            quote = await self.repository.lock_public(db, hashlib.sha256(token.encode()).hexdigest())
            if not quote:
                raise NotFoundError(message="Quote link is invalid")
            if not quote.expires_at or quote.expires_at <= datetime.now(UTC):
                raise APIException(message="Quote link has expired", status_code=410)
            if quote.status != "Accepted":
                if quote.status != "Sent" or not quote.approved_at or not quote.sent_at:
                    raise APIException(message="Only a sent, approved quote can be accepted", status_code=409)
                if not quote.expires_at or quote.expires_at <= datetime.now(UTC):
                    raise APIException(message="Quote has expired", status_code=410)
                company, contact = await self.deal_repository.get_sales_customer(db,
                    organization_id=quote.organization_id, company_id=quote.company_id, contact_id=quote.contact_id)
                if not company or not contact or contact.company_id != company.id:
                    raise APIException(message="Quote customer is invalid")
                await self.repository.accept_public(db, quote,
                    customer_email=quote.recipient_email or contact.email, at=datetime.now(UTC))
            invoice = await InvoiceService().create_from_accepted_quote(db, quote)
            await db.commit()
            return {"quote_id": quote.id, "status": quote.status, "invoice_id": invoice.id,
                    "invoice_number": invoice.invoice_number, "invoice_status": invoice.status}
        except Exception:
            await db.rollback()
            raise

    async def public_quote(self, db: AsyncSession, *, token: str) -> dict:
        try:
            quote = await self.repository.lock_public(db, hashlib.sha256(token.encode()).hexdigest())
            if not quote or not quote.approved_at or not quote.sent_at:
                raise NotFoundError(message="Quote link is invalid")
            if not quote.expires_at or quote.expires_at <= datetime.now(UTC):
                raise APIException(message="Quote link has expired", status_code=410)
            if quote.status not in {"Sent", "Accepted", "Rejected"}:
                raise APIException(message="Quote is not available", status_code=409)
            result = await self.get_quote(db, quote_id=quote.id, organization_id=quote.organization_id)
            invoice = await invoice_repository.get_by_quote(db, quote_id=quote.id,
                                                            organization_id=quote.organization_id)
            result["invoice_id"] = invoice.id if invoice else None
            result["invoice_number"] = invoice.invoice_number if invoice else None
            result["invoice_status"] = invoice.status if invoice else None
            await db.commit()
            return result
        except Exception:
            await db.rollback()
            raise

    async def reject_public_quote(self, db: AsyncSession, *, token: str) -> dict:
        try:
            quote = await self.repository.lock_public(db, hashlib.sha256(token.encode()).hexdigest())
            if not quote or not quote.approved_at or not quote.sent_at:
                raise NotFoundError(message="Quote link is invalid")
            if not quote.expires_at or quote.expires_at <= datetime.now(UTC):
                raise APIException(message="Quote link has expired", status_code=410)
            if quote.status not in {"Sent", "Rejected"}:
                raise APIException(message="Quote cannot be rejected in its current state", status_code=409)
            if quote.status == "Sent":
                await self.repository.reject_public(db, quote)
            await db.commit()
            return {"quote_id": quote.id, "status": quote.status}
        except Exception:
            await db.rollback()
            raise

    async def public_checkout(self, db: AsyncSession, *, token: str) -> dict:
        from app.services.invoice_payment_service import InvoicePaymentService

        try:
            quote = await self.repository.lock_public(db, hashlib.sha256(token.encode()).hexdigest())
            if not quote or quote.status != "Accepted":
                raise NotFoundError(message="Accepted quote not found")
            if not quote.expires_at or quote.expires_at <= datetime.now(UTC):
                raise APIException(message="Quote link has expired", status_code=410)
            invoice = await invoice_repository.get_by_quote(db, quote_id=quote.id,
                                                            organization_id=quote.organization_id)
            if not invoice:
                raise NotFoundError(message="Invoice not found")
            invoice_id, organization_id = invoice.id, quote.organization_id
            await db.commit()
            return await InvoicePaymentService().checkout(db, invoice_id=invoice_id,
                organization_id=organization_id, public_customer=True)
        except Exception:
            await db.rollback()
            raise

    async def create_from_won_deal(self, db: AsyncSession, *, deal: Deal, actor_id: str) -> Quote:
        """Caller holds the scoped deal lock and owns the transaction; never commits here."""
        if deal.stage != "Closed Won":
            raise APIException(message="Only a Closed Won deal can generate a quote", code="INVALID_DEAL_STAGE")
        existing = await self.repository.get_automatic(
            db, deal_id=deal.id, organization_id=deal.organization_id,
        )
        if existing:
            return existing
        organization = await self.repository.get_organization(db, deal.organization_id)
        if not organization or not organization.currency:
            raise APIException(message="Configure the organization currency before closing a deal")
        company, contact = await self.deal_repository.get_sales_customer(
            db, organization_id=deal.organization_id, company_id=deal.company_id, contact_id=deal.contact_id,
        )
        if not company or not contact or contact.company_id != company.id:
            raise APIException(message="A same-organization company and linked contact are required")
        lines = await self.deal_repository.list_deal_products(db, deal.id)
        if not lines:
            raise APIException(message="Add products before closing the deal", code="DEAL_ITEMS_REQUIRED")
        quote_id = str(uuid4())
        items = []
        total = Decimal(0)
        for line in lines:
            product = await invoice_repository.get_product_scoped(
                db, product_id=line.product_id, organization_id=deal.organization_id,
            )
            if not product:
                raise APIException(message="A deal product is missing or belongs to another organization")
            amounts = calculate_line(line.quantity, line.unit_price,
                                     line.discount_percent or 0, line.tax_percent or 0)
            total += amounts.total
            decimal_value(total)
            items.append({"quote_id": quote_id, "product_id": product.id,
                          "product_name": line.product_name or product.name,
                          "quantity": line.quantity, "unit_price": line.unit_price,
                          "discount_percent": line.discount_percent or 0,
                          "tax_percent": line.tax_percent or 0,
                          "subtotal": amounts.subtotal, "discount_total": amounts.discount,
                          "tax_total": amounts.tax, "total": amounts.total})
        quote = await self.repository.create(db, data={
            "id": quote_id, "organization_id": deal.organization_id, "deal_id": deal.id,
            "automatic_deal_id": deal.id, "company_id": company.id, "contact_id": contact.id,
            "currency": organization.currency.upper(), "quote_number": f"QUO-{quote_id}",
            "status": "Draft", "total_amount": total,
        })
        await db.flush()
        await self.repository.add_items(db, items)
        await self.repository.record_automatic_creation(db, quote, actor_id)
        await NotificationRepository().create_notification(db, data={
            "organization_id": deal.organization_id, "user_id": actor_id,
            "event_name": "deal.won", "entity_type": "quote", "entity_id": quote.id,
            "title": "Quote automatically created", "message": f"Quote {quote.quote_number} is ready for review.",
        })
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
        items = await self.repository.list_items(db, quote_id=quote_id, organization_id=organization_id)
        result["items"] = [{"id": item.id, "product_id": item.product_id,
                            "product_name": item.product_name, "quantity": item.quantity,
                            "unit_price": item.unit_price, "discount_percent": item.discount_percent,
                            "tax_percent": item.tax_percent, "total": item.total} for item in items]
        _, contact = await self.deal_repository.get_sales_customer(db,
            organization_id=organization_id, company_id=quote.company_id, contact_id=quote.contact_id)
        result["recipient_email"] = quote.recipient_email or (contact.email if contact else None)
        invoice = await self.repository.get_invoice_reference(db, quote_id=quote_id, organization_id=organization_id)
        result.update(invoice_id=invoice.id if invoice else None,
                      invoice_number=invoice.invoice_number if invoice else None,
                      invoice_status=invoice.status if invoice else None)
        return result

    async def create_quote(
        self, db: AsyncSession, *, payload: QuoteBase, current_user: User
    ) -> dict:
        organization_id = await self.resolve_organization_id(db, current_user)
        deal = await self._require_deal(
            db, deal_id=payload.deal_id, organization_id=organization_id
        )
        if payload.status not in QUOTE_STATUSES:
            raise APIException(
                message=f"Invalid quote status '{payload.status}'.",
                code="INVALID_QUOTE_STATUS",
            )
        quote = await self.repository.create(
            db,
            data={
                "organization_id": organization_id,
                "deal_id": deal.id,
                "quote_number": payload.quote_number.strip()
                or f"QUO-{int(time.time())}-{uuid4().hex[:6].upper()}",
                "total_amount": payload.total_amount,
                "status": payload.status,
            },
        )
        await self._commit(db, "Failed to create quote")
        await db.refresh(quote)
        return quote_to_dict(quote)

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
            raise APIException(message="Generated quote totals and customer links cannot be overwritten",
                               code="QUOTE_IMMUTABLE", status_code=409)
        deal = await self._require_deal(
            db, deal_id=payload.deal_id, organization_id=organization_id
        )
        if payload.status not in QUOTE_STATUSES:
            raise APIException(
                message=f"Invalid quote status '{payload.status}'.",
                code="INVALID_QUOTE_STATUS",
            )
        quote.deal_id = deal.id
        quote.quote_number = payload.quote_number.strip() or quote.quote_number
        quote.total_amount = payload.total_amount
        quote.status = payload.status
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
        recipient_email: str,
        organization_id: str,
    ) -> dict:
        from app.services.quote_delivery_service import quote_delivery_service

        await self._require_quote(db, quote_id=quote_id, organization_id=organization_id)
        return await quote_delivery_service.queue(db, quote_id=quote_id,
            organization_id=organization_id, recipient_email=recipient_email)

    async def accept_quote(self, db: AsyncSession, *, quote_id: str, organization_id: str) -> dict:
        await self._require_quote(db, quote_id=quote_id, organization_id=organization_id)
        raise APIException(message="Customer acceptance requires a secure acceptance link",
                           code="CUSTOMER_ACCEPTANCE_REQUIRED", status_code=409)

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
        quote.status = "Rejected"
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
        invoice = await invoice_repository.get_by_quote(db, quote_id=quote.id, organization_id=organization_id)
        if not invoice:
            raise APIException(message="Invoices are created automatically after secure customer acceptance",
                               code="CUSTOMER_ACCEPTANCE_REQUIRED", status_code=409)
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
        return []


quote_service = QuoteService()
