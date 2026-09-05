from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog, Invoice, Payment, Quote
from app.repositories.notification_repository import NotificationRepository


class PaymentRepository:
    async def lock_invoice(self, db: AsyncSession, *, invoice_id: str,
                           organization_id: str) -> Invoice | None:
        result = await db.execute(select(Invoice).where(Invoice.id == invoice_id,
            Invoice.organization_id == organization_id).with_for_update().execution_options(populate_existing=True))
        return result.scalar_one_or_none()

    async def lock_checkout(self, db: AsyncSession, session_id: str) -> Invoice | None:
        result = await db.execute(select(Invoice).where(Invoice.stripe_checkout_session_id == session_id)
            .with_for_update().execution_options(populate_existing=True))
        return result.scalar_one_or_none()

    async def save_checkout(self, db: AsyncSession, invoice: Invoice, *, session_id: str, url: str, generation: int) -> None:
        invoice.stripe_checkout_session_id = session_id
        invoice.stripe_checkout_url = url
        invoice.stripe_checkout_generation = generation
        db.add(AuditLog(organization_id=invoice.organization_id, action="checkout.created", details=invoice.id))

    async def get_payment(self, db: AsyncSession, invoice_id: str) -> Payment | None:
        result = await db.execute(select(Payment).where(Payment.invoice_id == invoice_id))
        return result.scalar_one_or_none()

    async def record_payment(self, db: AsyncSession, invoice: Invoice, *, intent_id: str,
                             session_id: str, paid_at: datetime) -> Payment:
        payment = Payment(organization_id=invoice.organization_id, invoice_id=invoice.id,
            provider="stripe", provider_payment_id=intent_id, checkout_session_id=session_id,
            amount=invoice.amount, currency=invoice.currency, status="Succeeded", paid_at=paid_at)
        db.add(payment)
        invoice.status = "Paid"
        invoice.paid_amount = invoice.amount
        db.add(AuditLog(organization_id=invoice.organization_id, action="invoice.paid", details=invoice.id))
        db.add(AuditLog(organization_id=invoice.organization_id, action="payment.received", details=invoice.id))
        recipient = await db.scalar(select(Quote.approved_by).where(
            Quote.id == invoice.quote_id, Quote.organization_id == invoice.organization_id))
        if recipient:
            await NotificationRepository().create_for_scoped_user(db, data={
                "organization_id": invoice.organization_id, "user_id": recipient,
                "event_name": "invoice.paid", "entity_type": "invoice", "entity_id": invoice.id,
                "title": "Payment received", "message": f"Invoice {invoice.invoice_number} has been paid.",
            })
        return payment
