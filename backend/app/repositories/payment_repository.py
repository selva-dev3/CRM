from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.selectable import Subquery

from app.core.record_access import record_access_filter
from app.models import (
    AuditLog,
    Company,
    Contact,
    Deal,
    DealActivity,
    Invoice,
    Organization,
    Payment,
)
from app.repositories.notification_repository import NotificationRepository


@dataclass(frozen=True)
class InvoicePaymentSummaryRow:
    invoice: Invoice
    company_name: str | None
    contact_name: str | None
    contact_email: str | None
    paid_amount: Decimal
    latest_payment_id: str | None
    payment_number: str | None
    payment_type: str | None
    latest_payment_amount: Decimal | None
    payment_date: date | None
    notes: str | None


class PaymentRepository:
    @staticmethod
    def _payment_status_condition(status: str, paid_amount, invoice_amount):
        normalized = status.strip()
        if normalized == "Pending":
            return paid_amount <= 0
        if normalized == "Partially Paid":
            return and_(paid_amount > 0, paid_amount < invoice_amount)
        if normalized == "Paid":
            return paid_amount >= invoice_amount
        return None

    @staticmethod
    def _summary_subqueries() -> tuple[Subquery, Subquery]:
        paid = (
            select(
                Payment.organization_id.label("organization_id"),
                Payment.invoice_id.label("invoice_id"),
                func.sum(Payment.amount).label("paid_amount"),
            )
            .where(Payment.status == "Succeeded")
            .group_by(Payment.organization_id, Payment.invoice_id)
            .subquery()
        )
        latest = (
            select(
                Payment.organization_id.label("organization_id"),
                Payment.invoice_id.label("invoice_id"),
                Payment.id.label("payment_id"),
                Payment.payment_number.label("payment_number"),
                Payment.payment_type.label("payment_type"),
                Payment.amount.label("payment_amount"),
                Payment.payment_date.label("payment_date"),
                Payment.notes.label("notes"),
                func.row_number()
                .over(
                    partition_by=(Payment.organization_id, Payment.invoice_id),
                    order_by=(Payment.created_at.desc(), Payment.id.desc()),
                )
                .label("row_number"),
            )
            .where(Payment.status == "Succeeded")
            .subquery()
        )
        return paid, latest

    async def list_invoice_summaries(
        self,
        db: AsyncSession,
        *,
        organization_id: str,
        page: int,
        limit: int,
        status: str | None = None,
        search: str | None = None,
        access=None,
    ) -> list[InvoicePaymentSummaryRow]:
        paid, latest = self._summary_subqueries()
        stmt = (
            select(
                Invoice,
                Company.name,
                Contact.name,
                Contact.email,
                func.coalesce(paid.c.paid_amount, 0),
                latest.c.payment_id,
                latest.c.payment_number,
                latest.c.payment_type,
                latest.c.payment_amount,
                latest.c.payment_date,
                latest.c.notes,
            )
            .outerjoin(Company, Company.id == Invoice.company_id)
            .outerjoin(Contact, Contact.id == Invoice.contact_id)
            .outerjoin(
                paid,
                (paid.c.invoice_id == Invoice.id)
                & (paid.c.organization_id == Invoice.organization_id),
            )
            .outerjoin(
                latest,
                (latest.c.invoice_id == Invoice.id)
                & (latest.c.organization_id == Invoice.organization_id)
                & (latest.c.row_number == 1),
            )
            .where(
                Invoice.organization_id == organization_id,
                Invoice.status == "Accepted",
                Invoice.finalized_at.is_not(None),
                Invoice.accepted_at.is_not(None),
            )
        )
        access_filter = record_access_filter(
            access, assigned_column=Invoice.created_by, created_column=Invoice.created_by
        )
        if access_filter is not None:
            stmt = stmt.where(access_filter)
        if status and status.strip():
            condition = self._payment_status_condition(
                status, func.coalesce(paid.c.paid_amount, 0), Invoice.amount
            )
            stmt = stmt.where(condition) if condition is not None else stmt.where(False)
        if search and search.strip():
            term = f"%{search.strip()}%"
            stmt = stmt.where(
                or_(
                    Invoice.invoice_number.ilike(term),
                    Company.name.ilike(term),
                    Contact.name.ilike(term),
                    Contact.email.ilike(term),
                    latest.c.payment_number.ilike(term),
                )
            )
        result = await db.execute(
            stmt.order_by(Invoice.created_at.desc(), Invoice.id.desc())
            .offset((page - 1) * limit)
            .limit(limit)
        )
        return [InvoicePaymentSummaryRow(*tuple(row)) for row in result.all()]

    async def count_invoice_summaries(
        self,
        db: AsyncSession,
        *,
        organization_id: str,
        status: str | None = None,
        search: str | None = None,
        access=None,
    ) -> int:
        paid, latest = self._summary_subqueries()
        stmt = (
            select(func.count())
            .select_from(Invoice)
            .outerjoin(Company, Company.id == Invoice.company_id)
            .outerjoin(Contact, Contact.id == Invoice.contact_id)
            .outerjoin(
                paid,
                (paid.c.invoice_id == Invoice.id)
                & (paid.c.organization_id == Invoice.organization_id),
            )
            .outerjoin(
                latest,
                (latest.c.invoice_id == Invoice.id)
                & (latest.c.organization_id == Invoice.organization_id)
                & (latest.c.row_number == 1),
            )
            .where(
                Invoice.organization_id == organization_id,
                Invoice.status == "Accepted",
                Invoice.finalized_at.is_not(None),
                Invoice.accepted_at.is_not(None),
            )
        )
        access_filter = record_access_filter(
            access, assigned_column=Invoice.created_by, created_column=Invoice.created_by
        )
        if access_filter is not None:
            stmt = stmt.where(access_filter)
        if status and status.strip():
            condition = self._payment_status_condition(
                status, func.coalesce(paid.c.paid_amount, 0), Invoice.amount
            )
            stmt = stmt.where(condition) if condition is not None else stmt.where(False)
        if search and search.strip():
            term = f"%{search.strip()}%"
            stmt = stmt.where(
                or_(
                    Invoice.invoice_number.ilike(term),
                    Company.name.ilike(term),
                    Contact.name.ilike(term),
                    Contact.email.ilike(term),
                    latest.c.payment_number.ilike(term),
                )
            )
        return int((await db.execute(stmt)).scalar_one())

    async def list_eligible_invoices(
        self,
        db: AsyncSession,
        *,
        organization_id: str,
        page: int = 1,
        limit: int = 100,
        access=None,
    ) -> list[tuple[Invoice, str | None, str | None, str | None, Decimal]]:
        paid, _latest = self._summary_subqueries()
        stmt = (
            select(
                Invoice,
                Company.name,
                Contact.name,
                Contact.email,
                func.coalesce(paid.c.paid_amount, 0),
            )
            .outerjoin(Company, Company.id == Invoice.company_id)
            .outerjoin(Contact, Contact.id == Invoice.contact_id)
            .outerjoin(
                paid,
                (paid.c.invoice_id == Invoice.id)
                & (paid.c.organization_id == Invoice.organization_id),
            )
            .where(
                Invoice.organization_id == organization_id,
                Invoice.status == "Accepted",
                Invoice.finalized_at.is_not(None),
                Invoice.accepted_at.is_not(None),
                Invoice.amount > func.coalesce(paid.c.paid_amount, 0),
            )
            .order_by(Invoice.created_at.desc())
            .offset((page - 1) * limit)
            .limit(limit)
        )
        access_filter = record_access_filter(
            access, assigned_column=Invoice.created_by, created_column=Invoice.created_by
        )
        if access_filter is not None:
            stmt = stmt.where(access_filter)
        result = await db.execute(stmt)
        return [tuple(row) for row in result.all()]

    async def list_invoice_ids_for_reconciliation(
        self, db: AsyncSession, *, after_id: str | None = None, limit: int = 200
    ) -> list[tuple[str, str]]:
        stmt = select(Invoice.id, Invoice.organization_id).order_by(Invoice.id).limit(limit)
        if after_id:
            stmt = stmt.where(Invoice.id > after_id)
        return [tuple(row) for row in (await db.execute(stmt)).all()]

    async def record_reconciliation_audit(
        self,
        db: AsyncSession,
        *,
        invoice: Invoice,
        old_paid_amount: Decimal,
        old_payment_status: str,
    ) -> None:
        db.add(
            AuditLog(
                organization_id=invoice.organization_id,
                action="invoice.payment_reconciled",
                details=(
                    f"{invoice.id}: paid {old_paid_amount}->{invoice.paid_amount}; "
                    f"status {old_payment_status}->{invoice.payment_status}"
                ),
            )
        )

    async def sum_succeeded(
        self, db: AsyncSession, *, invoice_id: str, organization_id: str
    ) -> Decimal:
        result = await db.scalar(
            select(func.coalesce(func.sum(Payment.amount), 0)).where(
                Payment.invoice_id == invoice_id,
                Payment.organization_id == organization_id,
                Payment.status == "Succeeded",
            )
        )
        return Decimal(str(result))

    async def get_by_id(self, db: AsyncSession, payment_id: str) -> Payment | None:
        result = await db.execute(select(Payment).where(Payment.id == payment_id))
        return result.scalar_one_or_none()

    async def list_scoped(
        self,
        db: AsyncSession,
        *,
        organization_id: str,
        page: int,
        limit: int,
        status: str | None = None,
        search: str | None = None,
        invoice_id: str | None = None,
        access=None,
    ) -> list[tuple[Payment, str, str | None, str | None, str | None]]:
        stmt = (
            select(Payment, Invoice.invoice_number, Company.name, Contact.name, Contact.email)
            .join(Invoice, Invoice.id == Payment.invoice_id)
            .outerjoin(Company, Company.id == Invoice.company_id)
            .outerjoin(Contact, Contact.id == Invoice.contact_id)
            .where(
                Payment.organization_id == organization_id,
                Invoice.organization_id == organization_id,
            )
        )
        access_filter = record_access_filter(
            access, assigned_column=Invoice.created_by, created_column=Invoice.created_by
        )
        if access_filter is not None:
            stmt = stmt.where(access_filter)
        if status and status.strip():
            stmt = stmt.where(Payment.status == status.strip())
        if invoice_id:
            stmt = stmt.where(Payment.invoice_id == invoice_id)
        if search and search.strip():
            term = f"%{search.strip()}%"
            stmt = stmt.where(
                or_(
                    Payment.id.ilike(term),
                    Payment.payment_number.ilike(term),
                    Invoice.invoice_number.ilike(term),
                    Company.name.ilike(term),
                    Contact.name.ilike(term),
                    Contact.email.ilike(term),
                )
            )
        stmt = (
            stmt.order_by(Payment.paid_at.desc(), Payment.id.desc())
            .offset((page - 1) * limit)
            .limit(limit)
        )
        result = await db.execute(stmt)
        return [tuple(row) for row in result.all()]

    async def count_scoped(
        self,
        db: AsyncSession,
        *,
        organization_id: str,
        status: str | None = None,
        search: str | None = None,
        invoice_id: str | None = None,
        access=None,
    ) -> int:
        stmt = (
            select(func.count())
            .select_from(Payment)
            .join(Invoice, Invoice.id == Payment.invoice_id)
            .outerjoin(Company, Company.id == Invoice.company_id)
            .outerjoin(Contact, Contact.id == Invoice.contact_id)
            .where(
                Payment.organization_id == organization_id,
                Invoice.organization_id == organization_id,
            )
        )
        access_filter = record_access_filter(
            access, assigned_column=Invoice.created_by, created_column=Invoice.created_by
        )
        if access_filter is not None:
            stmt = stmt.where(access_filter)
        if status and status.strip():
            stmt = stmt.where(Payment.status == status.strip())
        if invoice_id:
            stmt = stmt.where(Payment.invoice_id == invoice_id)
        if search and search.strip():
            term = f"%{search.strip()}%"
            stmt = stmt.where(
                or_(
                    Payment.id.ilike(term),
                    Payment.payment_number.ilike(term),
                    Invoice.invoice_number.ilike(term),
                    Company.name.ilike(term),
                    Contact.name.ilike(term),
                    Contact.email.ilike(term),
                )
            )
        result = await db.execute(stmt)
        return int(result.scalar_one())

    async def advance_numbering(self, db: AsyncSession, organization_id: str) -> tuple[str, int]:
        result = await db.execute(
            select(Organization)
            .where(Organization.id == organization_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        organization = result.scalar_one_or_none()
        if not organization:
            raise ValueError("Organization not found while generating payment number")
        organization.payment_sequence += 1
        return organization.payment_prefix, organization.payment_sequence

    async def get_scoped(
        self, db: AsyncSession, *, payment_id: str, organization_id: str
    ) -> tuple[Payment, str, str | None, str | None, str | None] | None:
        result = await db.execute(
            select(Payment, Invoice.invoice_number, Company.name, Contact.name, Contact.email)
            .join(Invoice, Invoice.id == Payment.invoice_id)
            .outerjoin(Company, Company.id == Invoice.company_id)
            .outerjoin(Contact, Contact.id == Invoice.contact_id)
            .where(
                Payment.id == payment_id,
                Payment.organization_id == organization_id,
                Invoice.organization_id == organization_id,
            )
        )
        row = result.first()
        return tuple(row) if row is not None else None

    async def get_scoped_detail(
        self, db: AsyncSession, *, payment_id: str, organization_id: str, access=None
    ) -> tuple | None:
        stmt = (
            select(
                Payment,
                Invoice.invoice_number,
                Invoice.amount,
                Invoice.paid_amount,
                Invoice.payment_status,
                Company.id,
                Company.name,
                Contact.name,
                Contact.email,
            )
            .join(Invoice, Invoice.id == Payment.invoice_id)
            .outerjoin(Company, Company.id == Invoice.company_id)
            .outerjoin(Contact, Contact.id == Invoice.contact_id)
            .where(
                Payment.id == payment_id,
                Payment.organization_id == organization_id,
                Invoice.organization_id == organization_id,
            )
        )
        access_filter = record_access_filter(
            access, assigned_column=Invoice.created_by, created_column=Invoice.created_by
        )
        if access_filter is not None:
            stmt = stmt.where(access_filter)
        result = await db.execute(stmt)
        row = result.first()
        return tuple(row) if row is not None else None

    async def lock_invoice(
        self, db: AsyncSession, *, invoice_id: str, organization_id: str
    ) -> Invoice | None:
        result = await db.execute(
            select(Invoice)
            .where(Invoice.id == invoice_id, Invoice.organization_id == organization_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def get_by_idempotency(
        self, db: AsyncSession, *, invoice_id: str, organization_id: str, key: str
    ) -> Payment | None:
        result = await db.execute(
            select(Payment).where(
                Payment.invoice_id == invoice_id,
                Payment.organization_id == organization_id,
                Payment.idempotency_key == key,
            )
        )
        return result.scalar_one_or_none()

    async def create_manual(self, db: AsyncSession, *, data: dict) -> Payment:
        payment = Payment(**data)
        db.add(payment)
        await db.flush()
        return payment

    async def record_manual_audit(
        self, db: AsyncSession, invoice: Invoice, payment: Payment
    ) -> None:
        db.add(
            AuditLog(
                organization_id=invoice.organization_id,
                action="payment.received",
                details=payment.id,
            )
        )
        if invoice.payment_status == "Paid":
            db.add(
                AuditLog(
                    organization_id=invoice.organization_id,
                    action="invoice.paid",
                    details=invoice.id,
                )
            )
        if invoice.deal_id:
            db.add(
                DealActivity(
                    deal_id=invoice.deal_id,
                    action=f"Payment {payment.payment_number} received for invoice {invoice.invoice_number}",
                )
            )
        recipient = await db.scalar(
            select(Deal.assigned_to).where(
                Deal.id == invoice.deal_id, Deal.organization_id == invoice.organization_id
            )
        )
        if recipient:
            await NotificationRepository().create_for_scoped_user(
                db,
                data={
                    "organization_id": invoice.organization_id,
                    "user_id": recipient,
                    "event_name": (
                        "invoice.paid" if invoice.payment_status == "Paid" else "payment.received"
                    ),
                    "entity_type": "invoice",
                    "entity_id": invoice.id,
                    "title": "Payment received",
                    "message": f"Payment {payment.payment_number} received for invoice {invoice.invoice_number}.",
                },
            )

    async def claim_receipt(self, db: AsyncSession, now: datetime) -> Payment | None:
        result = await db.execute(
            select(Payment)
            .where(
                Payment.receipt_delivery_status == "Pending", Payment.receipt_delivery_attempts < 3
            )
            .order_by(Payment.created_at)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        payment = result.scalar_one_or_none()
        if payment:
            payment.receipt_delivery_status = "Processing"
            payment.receipt_delivery_claimed_at = now
            payment.receipt_delivery_attempts += 1
        return payment

    async def expire_receipt_claims(self, db: AsyncSession, now: datetime) -> None:
        result = await db.execute(
            select(Payment)
            .where(
                Payment.receipt_delivery_status == "Processing",
                Payment.receipt_delivery_claimed_at < now - timedelta(minutes=10),
            )
            .with_for_update(skip_locked=True)
        )
        for payment in result.scalars():
            payment.receipt_delivery_status = "Unknown"

    async def receipt_result(
        self,
        db: AsyncSession,
        payment: Payment,
        *,
        state: str,
        receipt_key: str | None = None,
        message_id: str | None = None,
    ) -> None:
        payment.receipt_delivery_status = state
        if receipt_key:
            payment.receipt_s3_key = receipt_key
        if message_id:
            payment.receipt_provider_message_id = message_id
            db.add(
                AuditLog(
                    organization_id=payment.organization_id,
                    action="receipt.sent",
                    details=payment.id,
                )
            )
