from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime, time
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIException, ConflictError, NotFoundError
from app.core.logging import get_logger
from app.repositories.payment_repository import InvoicePaymentSummaryRow, PaymentRepository
from app.schemas.crm_schemas import ManualPaymentCreate
from app.services.record_access_service import record_access_service
from app.services.sales_totals import decimal_value

logger = get_logger(__name__)


@dataclass(frozen=True)
class PaymentBalance:
    paid_amount: Decimal
    outstanding_amount: Decimal
    payment_status: str


def calculate_payment_balance(invoice_total: object, paid_amount: object) -> PaymentBalance:
    """Return the canonical invoice payment aggregate from persisted payment totals."""
    total = decimal_value(invoice_total)
    paid = decimal_value(paid_amount)
    outstanding = max(Decimal(0), total - paid)
    if paid <= 0:
        status = "Pending"
    elif paid < total:
        status = "Partially Paid"
    else:
        status = "Paid"
    return PaymentBalance(paid, outstanding, status)


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
    (
        payment,
        invoice_number,
        invoice_total,
        paid_amount,
        _payment_status,
        customer_id,
        company_name,
        contact_name,
        contact_email,
    ) = row
    balance = calculate_payment_balance(invoice_total, paid_amount)
    result = payment_to_dict((payment, invoice_number, company_name, contact_name, contact_email))
    result.update(
        {
            "invoice_total": invoice_total or Decimal(0),
            "invoice_paid_amount": balance.paid_amount,
            "invoice_outstanding_amount": balance.outstanding_amount,
            "invoice_payment_status": balance.payment_status,
            "customer": {"id": customer_id, "name": company_name},
        }
    )
    return result


def eligible_invoice_to_dict(row: tuple) -> dict[str, object]:
    invoice, company_name, contact_name, _contact_email, paid_amount = row
    balance = calculate_payment_balance(invoice.amount, paid_amount)
    return {
        "id": invoice.id,
        "invoice_number": invoice.invoice_number,
        "customer_name": company_name,
        "contact_name": contact_name,
        "amount": invoice.amount or Decimal(0),
        "paid_amount": balance.paid_amount,
        "outstanding_amount": balance.outstanding_amount,
        "currency": invoice.currency,
        "payment_status": balance.payment_status,
    }


def invoice_payment_summary_to_dict(row: InvoicePaymentSummaryRow) -> dict[str, object]:
    balance = calculate_payment_balance(row.invoice.amount, row.paid_amount)
    return {
        "id": row.invoice.id,
        "invoice_id": row.invoice.id,
        "invoice_number": row.invoice.invoice_number,
        "company_name": row.company_name,
        "contact_name": row.contact_name,
        "contact_email": row.contact_email,
        "amount": row.invoice.amount,
        "paid_amount": balance.paid_amount,
        "outstanding_amount": balance.outstanding_amount,
        "currency": row.invoice.currency,
        "payment_status": balance.payment_status,
        "latest_payment_id": row.latest_payment_id,
        "payment_number": row.payment_number,
        "payment_type": row.payment_type,
        "latest_payment_amount": row.latest_payment_amount,
        "payment_date": row.payment_date.isoformat() if row.payment_date else None,
        "notes": row.notes,
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
            current_balance = calculate_payment_balance(invoice.amount, paid)
            if payload.amount > current_balance.outstanding_amount:
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
            new_balance = calculate_payment_balance(invoice.amount, paid + payload.amount)
            invoice.paid_amount = new_balance.paid_amount
            invoice.payment_status = new_balance.payment_status
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
        current_user=None,
    ) -> list[dict[str, object]]:
        access = (
            await record_access_service.resolve(db, current_user, "payments")
            if current_user
            else None
        )
        rows = await self.repository.list_scoped(
            db,
            organization_id=organization_id,
            page=page,
            limit=limit,
            status=status,
            search=search,
            invoice_id=invoice_id,
            access=access,
        )
        return [payment_to_dict(row) for row in rows]

    async def count_payments(
        self,
        db,
        *,
        organization_id: str,
        status: str | None = None,
        search: str | None = None,
        invoice_id: str | None = None,
        current_user=None,
    ) -> int:
        access = (
            await record_access_service.resolve(db, current_user, "payments")
            if current_user
            else None
        )
        return await self.repository.count_scoped(
            db,
            organization_id=organization_id,
            status=status,
            search=search,
            invoice_id=invoice_id,
            access=access,
        )

    async def list_invoice_summaries(
        self,
        db: AsyncSession,
        *,
        organization_id: str,
        page: int,
        limit: int,
        status: str | None = None,
        search: str | None = None,
        current_user=None,
    ) -> list[dict[str, object]]:
        access = (
            await record_access_service.resolve(db, current_user, "payments")
            if current_user
            else None
        )
        rows = await self.repository.list_invoice_summaries(
            db,
            organization_id=organization_id,
            page=page,
            limit=limit,
            status=status,
            search=search,
            access=access,
        )
        return [invoice_payment_summary_to_dict(row) for row in rows]

    async def count_invoice_summaries(
        self,
        db: AsyncSession,
        *,
        organization_id: str,
        status: str | None = None,
        search: str | None = None,
        current_user=None,
    ) -> int:
        access = (
            await record_access_service.resolve(db, current_user, "payments")
            if current_user
            else None
        )
        return await self.repository.count_invoice_summaries(
            db, organization_id=organization_id, status=status, search=search, access=access
        )

    async def list_eligible_invoices(
        self,
        db: AsyncSession,
        *,
        organization_id: str,
        page: int = 1,
        limit: int = 100,
        current_user=None,
    ) -> list[dict[str, object]]:
        access = (
            await record_access_service.resolve(db, current_user, "payments")
            if current_user
            else None
        )
        rows = await self.repository.list_eligible_invoices(
            db, organization_id=organization_id, page=page, limit=limit, access=access
        )
        return [eligible_invoice_to_dict(row) for row in rows]

    async def get_payment(
        self, db, *, payment_id: str, organization_id: str, current_user=None
    ) -> dict[str, object] | None:
        access = (
            await record_access_service.resolve(db, current_user, "payments")
            if current_user
            else None
        )
        row = await self.repository.get_scoped_detail(
            db, payment_id=payment_id, organization_id=organization_id, access=access
        )
        return payment_detail_to_dict(row) if row else None

    async def reconcile_invoice(
        self,
        db: AsyncSession,
        *,
        invoice_id: str,
        organization_id: str,
    ) -> bool:
        """Repair a persisted invoice aggregate from successful payment rows."""
        try:
            invoice = await self.repository.lock_invoice(
                db, invoice_id=invoice_id, organization_id=organization_id
            )
            if invoice is None:
                await db.rollback()
                return False
            paid = await self.repository.sum_succeeded(
                db, invoice_id=invoice.id, organization_id=organization_id
            )
            balance = calculate_payment_balance(invoice.amount, paid)
            old_paid = decimal_value(invoice.paid_amount)
            old_status = invoice.payment_status
            if old_paid == balance.paid_amount and old_status == balance.payment_status:
                await db.rollback()
                return False
            invoice.paid_amount = balance.paid_amount
            invoice.payment_status = balance.payment_status
            await self.repository.record_reconciliation_audit(
                db,
                invoice=invoice,
                old_paid_amount=old_paid,
                old_payment_status=old_status,
            )
            await db.commit()
            logger.info(
                "Invoice payment aggregate reconciled invoice_id=%s organization_id=%s",
                invoice.id,
                organization_id,
            )
            return True
        except Exception:
            await db.rollback()
            logger.exception(
                "Invoice payment reconciliation failed invoice_id=%s organization_id=%s",
                invoice_id,
                organization_id,
            )
            raise


payment_service = PaymentService()
