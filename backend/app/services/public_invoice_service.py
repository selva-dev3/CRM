"""Customer invoice view and acceptance using an expiring delivery capability."""

import asyncio
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIException, ConflictError, NotFoundError
from app.models.invoice import Invoice
from app.repositories.invoice_repository import InvoiceRepository
from app.schemas.crm_schemas import PublicInvoiceResponse
from app.services.invoice_service import invoice_to_dict
from app.services.public_invoice_token import token_hash
from app.services.s3_service import s3_service


class PublicInvoiceService:
    def __init__(self, repository: InvoiceRepository | None = None) -> None:
        self.repository = repository or InvoiceRepository()

    async def _invoice(self, db: AsyncSession, token: str, *, lock: bool = False) -> Invoice:
        invoice = await self.repository.get_public(db, token_hash(token), lock=lock)
        if not invoice:
            raise NotFoundError(message="Invoice link is invalid")
        expiry = invoice.public_token_expires_at
        if not expiry or (
            expiry.replace(tzinfo=UTC) if expiry.tzinfo is None else expiry
        ) <= datetime.now(UTC):
            raise APIException(
                message="Invoice link has expired", code="INVOICE_LINK_EXPIRED", status_code=410
            )
        if invoice.status not in {"Finalized", "Accepted"} or not invoice.finalized_at:
            raise ConflictError(message="Invoice is unavailable for customer acceptance")
        if not invoice.sent_at:
            raise ConflictError(message="Invoice delivery has not been confirmed")
        return invoice

    async def _response(self, db: AsyncSession, invoice: Invoice) -> PublicInvoiceResponse:
        items = await self.repository.list_items(
            db, invoice_id=invoice.id, organization_id=invoice.organization_id
        )
        data = invoice_to_dict(invoice, items)
        data["pdf_url"] = (
            await asyncio.to_thread(s3_service.generate_presigned_url, invoice.pdf_s3_key, 900)
            if invoice.pdf_s3_key
            else None
        )
        data["billing_snapshot"] = {
            key: value
            for key, value in (invoice.billing_snapshot or {}).items()
            if key
            in {"company", "contact", "email", "street", "city", "state", "country", "postal_code"}
            and (value is None or isinstance(value, str))
        }
        return PublicInvoiceResponse.model_validate(data)

    async def view(self, db: AsyncSession, *, token: str) -> PublicInvoiceResponse:
        return await self._response(db, await self._invoice(db, token))

    async def accept(self, db: AsyncSession, *, token: str) -> PublicInvoiceResponse:
        try:
            invoice = await self._invoice(db, token, lock=True)
            if invoice.status == "Finalized":
                invoice.status = "Accepted"
                invoice.accepted_at = datetime.now(UTC)
                await self.repository.record_event(db, invoice, "invoice.accepted")
            result = await self._response(db, invoice)
            await db.commit()
            return result
        except Exception:
            await db.rollback()
            raise


public_invoice_service = PublicInvoiceService()
