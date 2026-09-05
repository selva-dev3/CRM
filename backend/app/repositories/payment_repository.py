from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog, Deal, DealActivity, Invoice, Payment
from app.repositories.notification_repository import NotificationRepository


class PaymentRepository:
    async def get_by_id(self, db: AsyncSession, payment_id: str) -> Payment | None:
        result = await db.execute(select(Payment).where(Payment.id == payment_id))
        return result.scalar_one_or_none()

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

    async def lock_checkout(self, db: AsyncSession, session_id: str) -> Invoice | None:
        result = await db.execute(
            select(Invoice)
            .where(Invoice.stripe_checkout_session_id == session_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def save_checkout(
        self, db: AsyncSession, invoice: Invoice, *, session_id: str, url: str, generation: int
    ) -> None:
        invoice.stripe_checkout_session_id = session_id
        invoice.stripe_checkout_url = url
        invoice.stripe_checkout_generation = generation
        if invoice.deal_id:
            db.add(
                DealActivity(
                    deal_id=invoice.deal_id,
                    action=f"Stripe checkout created for invoice {invoice.invoice_number}",
                )
            )
        db.add(
            AuditLog(
                organization_id=invoice.organization_id,
                action="checkout.created",
                details=invoice.id,
            )
        )

    async def get_payment(self, db: AsyncSession, invoice_id: str) -> Payment | None:
        result = await db.execute(select(Payment).where(Payment.invoice_id == invoice_id))
        return result.scalar_one_or_none()

    async def get_by_event_id(self, db: AsyncSession, event_id: str) -> Payment | None:
        result = await db.execute(select(Payment).where(Payment.provider_event_id == event_id))
        return result.scalar_one_or_none()

    async def record_payment(
        self,
        db: AsyncSession,
        invoice: Invoice,
        *,
        intent_id: str,
        session_id: str,
        event_id: str,
        payment_method: str | None,
        paid_at: datetime,
    ) -> Payment:
        payment = Payment(
            organization_id=invoice.organization_id,
            invoice_id=invoice.id,
            provider="stripe",
            provider_payment_id=intent_id,
            checkout_session_id=session_id,
            provider_event_id=event_id,
            payment_method=payment_method,
            amount=invoice.amount,
            currency=invoice.currency,
            status="Succeeded",
            paid_at=paid_at,
            receipt_delivery_status="Pending",
        )
        db.add(payment)
        invoice.status = "Paid"
        invoice.paid_amount = invoice.amount
        if invoice.deal_id:
            db.add(
                DealActivity(
                    deal_id=invoice.deal_id,
                    action=f"Payment received; invoice {invoice.invoice_number} paid",
                )
            )
        db.add(
            AuditLog(
                organization_id=invoice.organization_id, action="invoice.paid", details=invoice.id
            )
        )
        db.add(
            AuditLog(
                organization_id=invoice.organization_id,
                action="payment.received",
                details=invoice.id,
            )
        )
        recipient = await db.scalar(
            select(Deal.assigned_to).where(
                Deal.id == invoice.deal_id,
                Deal.organization_id == invoice.organization_id,
            )
        )
        if recipient:
            await NotificationRepository().create_for_scoped_user(
                db,
                data={
                    "organization_id": invoice.organization_id,
                    "user_id": recipient,
                    "event_name": "invoice.paid",
                    "entity_type": "invoice",
                    "entity_id": invoice.id,
                    "title": "Payment received",
                    "message": f"Invoice {invoice.invoice_number} has been paid.",
                },
            )
        return payment

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
