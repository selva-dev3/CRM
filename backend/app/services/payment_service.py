from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, time
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIException, ConflictError, NotFoundError
from app.repositories.payment_repository import PaymentRepository
from app.schemas.crm_schemas import ManualPaymentCreate
from app.services.sales_totals import decimal_value


def payment_to_dict(row: tuple) -> dict[str, object]:
    payment, invoice_number, company_name, contact_name, contact_email = row
    return {
        "id": payment.id,
        "invoice_id": payment.invoice_id,
        "invoice_number": invoice_number,
        "payment_number": payment.payment_number,
        "company_name": company_name,
        "contact_name": contact_name,
        "contact_email": contact_email,
        "amount": payment.amount or 0.0,
        "currency": payment.currency,
        "payment_method": payment.payment_method,
        "status": payment.status,
        "payment_type": payment.payment_type,
        "payment_date": payment.payment_date.isoformat(),
        "notes": payment.notes,
        "paid_at": payment.paid_at.isoformat(),
        "created_at": payment.created_at.isoformat() if payment.created_at else None,
    }


def payment_detail_to_dict(row: tuple) -> dict[str, object]:
    payment, invoice_number, invoice_total, paid_amount, payment_status, customer_id, company_name, contact_name, contact_email = row
    result = payment_to_dict((payment, invoice_number, company_name, contact_name, contact_email))
    result.update(
        {
            "invoice_total": invoice_total or Decimal(0),
            "invoice_paid_amount": paid_amount or Decimal(0),
            "invoice_outstanding_amount": max(Decimal(0), Decimal(str(invoice_total or 0)) - Decimal(str(paid_amount or 0))),
            "invoice_payment_status": payment_status or "Pending",
            "customer": {"id": customer_id, "name": company_name},
        }
    )
    return result


def eligible_invoice_to_dict(row: tuple) -> dict[str, object]:
    invoice, company_name, contact_name, _contact_email = row
    return {
        "id": invoice.id,
        "invoice_number": invoice.invoice_number,
        "customer_name": company_name,
        "contact_name": contact_name,
        "amount": invoice.amount or Decimal(0),
        "paid_amount": invoice.paid_amount or Decimal(0),
        "outstanding_amount": max(Decimal(0), Decimal(str(invoice.amount or 0)) - Decimal(str(invoice.paid_amount or 0))),
        "currency": invoice.currency,
        "payment_status": invoice.payment_status or "Pending",
    }


class PaymentService:
    def __init__(self, repository: PaymentRepository | None = None) -> None:
        self.repository = repository or PaymentRepository()

    async def record_payment(
        self,
        db: AsyncSession,
        *,
        invoice_id: str,
        organization_id: str,
        user_id: str,
        payload: ManualPaymentCreate,
        idempotency_key: str,
    ) -> dict:
        if not idempotency_key.strip() or len(idempotency_key) > 128:
            raise APIException(
                message="A non-empty Idempotency-Key of at most 128 characters is required"
            )
        canonical = payload.model_dump(mode="json")
        canonical["amount"] = format(payload.amount, ".2f")
        digest = hashlib.sha256(
            json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        try:
            invoice = await self.repository.lock_invoice(
                db, invoice_id=invoice_id, organization_id=organization_id
            )
            if not invoice:
                raise NotFoundError(message="Invoice not found")
            existing = await self.repository.get_by_idempotency(
                db, invoice_id=invoice_id, organization_id=organization_id, key=idempotency_key
            )
            if existing:
                if existing.request_hash != digest:
                    raise ConflictError(
                        message="Idempotency-Key was already used with a different payment",
                        code="PAYMENT_IDEMPOTENCY_CONFLICT",
                    )
                result = await self.get_payment(
                    db, payment_id=existing.id, organization_id=organization_id
                )
                if result is None:
                    raise NotFoundError(message="Recorded payment not found")
                await db.commit()
                return result
            if invoice.status != "Accepted" or not invoice.finalized_at or not invoice.accepted_at:
                raise ConflictError(
                    message="Payments require a finalized invoice accepted by the customer",
                    code="INVOICE_ACCEPTANCE_REQUIRED",
                )
            paid = await self.repository.sum_succeeded(
                db, invoice_id=invoice_id, organization_id=organization_id
            )
            outstanding = decimal_value(invoice.amount) - paid
            if payload.amount > outstanding:
                raise ConflictError(
                    message="Payment exceeds the outstanding invoice amount",
                    code="PAYMENT_EXCEEDS_BALANCE",
                )
            if payload.payment_date > datetime.now(UTC).date():
                raise APIException(message="Payment date cannot be in the future")
            prefix, sequence = await self.repository.advance_numbering(db, organization_id)
            now = datetime.now(UTC)
            payment = await self.repository.create_manual(
                db,
                data={
                    "organization_id": organization_id,
                    "invoice_id": invoice_id,
                    "payment_number": f"{prefix}-{now.year}-{sequence:06d}",
                    "amount": payload.amount,
                    "currency": invoice.currency,
                    "payment_type": payload.payment_type,
                    "payment_method": payload.payment_type,
                    "payment_date": payload.payment_date,
                    "notes": payload.notes,
                    "status": "Succeeded",
                    "paid_at": datetime.combine(payload.payment_date, time.min, tzinfo=UTC),
                    "recorded_by": user_id,
                    "idempotency_key": idempotency_key,
                    "request_hash": digest,
                    "receipt_delivery_status": "Pending",
                },
            )
            invoice.paid_amount = paid + payload.amount
            invoice.payment_status = (
                "Paid" if invoice.paid_amount == invoice.amount else "Partially Paid"
            )
            await self.repository.record_manual_audit(db, invoice, payment)
            await db.flush()
            result = await self.get_payment(
                db, payment_id=payment.id, organization_id=organization_id
            )
            if result is None:
                raise NotFoundError(message="Recorded payment not found")
            await db.commit()
            return result
        except Exception:
            await db.rollback()
            raise

    async def list_payments(
        self,
        db,
        *,
        organization_id: str,
        page: int,
        limit: int,
        status: str | None = None,
        search: str | None = None,
        invoice_id: str | None = None,
    ) -> list[dict[str, object]]:
        rows = await self.repository.list_scoped(
            db,
            organization_id=organization_id,
            page=page,
            limit=limit,
            status=status,
            search=search,
            invoice_id=invoice_id,
        )
        return [payment_to_dict(row) for row in rows]

    async def list_eligible_invoices(
        self, db: AsyncSession, *, organization_id: str, page: int = 1, limit: int = 100
    ) -> list[dict[str, object]]:
        rows = await self.repository.list_eligible_invoices(
            db, organization_id=organization_id, page=page, limit=limit
        )
        return [eligible_invoice_to_dict(row) for row in rows]

    async def get_payment(
        self, db, *, payment_id: str, organization_id: str
    ) -> dict[str, object] | None:
        row = await self.repository.get_scoped_detail(
            db, payment_id=payment_id, organization_id=organization_id
        )
        return payment_detail_to_dict(row) if row else None


payment_service = PaymentService()
