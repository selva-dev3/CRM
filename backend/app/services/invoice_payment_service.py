"""Stripe invoice checkout and verified, idempotent full-payment fulfillment."""

import asyncio
from datetime import UTC, datetime
from urllib.parse import urlparse

import stripe
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import APIException, ConflictError, NotFoundError
from app.repositories.payment_repository import PaymentRepository
from app.services.sales_totals import decimal_value


def stripe_minor_units(amount: object, currency: str) -> int:
    # Explicitly supported two-decimal currencies; refuse unreviewed minor-unit rules.
    if currency.upper() not in {"INR", "USD", "EUR", "GBP", "CAD", "AUD", "SGD"}:
        raise APIException(message="Stripe minor-unit rules for this currency are not configured",
                           code="UNSUPPORTED_PAYMENT_CURRENCY")
    units = decimal_value(amount) * 100
    if units != units.to_integral_value() or units <= 0:
        raise APIException(message="Invoice amount is not payable", code="INVALID_AMOUNT")
    return int(units)


class InvoicePaymentService:
    def __init__(self, repository: PaymentRepository | None = None):
        self.repository = repository or PaymentRepository()

    def _client(self):
        if not settings.STRIPE_SECRET_KEY:
            raise APIException(message="Stripe is not configured", code="PAYMENT_NOT_CONFIGURED", status_code=503)
        return stripe.StripeClient(settings.STRIPE_SECRET_KEY, max_network_retries=0,
                                   http_client=stripe.RequestsClient(timeout=30))

    async def checkout(self, db: AsyncSession, *, invoice_id: str, organization_id: str,
                       public_customer: bool = False) -> dict:
        try:
            invoice = await self.repository.lock_invoice(db, invoice_id=invoice_id, organization_id=organization_id)
            if not invoice:
                raise NotFoundError(message="Invoice not found")
            if invoice.status not in {"Pending", "Overdue"} or invoice.paid_amount:
                raise ConflictError(message="This invoice is not awaiting a full payment")
            amount = stripe_minor_units(invoice.amount, invoice.currency)
            client = self._client()
            generation = invoice.stripe_checkout_generation
            if invoice.stripe_checkout_session_id:
                session = await asyncio.to_thread(client.v1.checkout.sessions.retrieve, invoice.stripe_checkout_session_id)
                if session.status == "open" and session.url:
                    await db.commit()
                    return {"checkout_url": session.url}
                if session.status != "expired":
                    raise ConflictError(message="Checkout is completed or expired; reconcile payment before issuing another session")
                generation += 1
            frontend = settings.FRONTEND_URL.split(",")[0].strip().rstrip("/")
            if urlparse(frontend).scheme not in {"http", "https"} or not urlparse(frontend).netloc:
                raise APIException(message="Configure a valid frontend URL")
            return_path = "/public/quote" if public_customer else f"/invoices/{invoice.id}"
            session = await asyncio.to_thread(client.v1.checkout.sessions.create, {
                "mode": "payment", "client_reference_id": invoice.id,
                "metadata": {"invoice_id": invoice.id, "organization_id": organization_id},
                "line_items": [{"price_data": {"currency": invoice.currency.lower(), "unit_amount": amount,
                    "product_data": {"name": invoice.invoice_number}}, "quantity": 1}],
                "success_url": f"{frontend}{return_path}?checkout=returned",
                "cancel_url": f"{frontend}{return_path}?checkout=cancelled",
            }, {"idempotency_key": f"crm-invoice-{invoice.id}-{generation}"})
            if not session.id or not session.url:
                raise APIException(message="Stripe returned an incomplete checkout", status_code=502)
            await self.repository.save_checkout(db, invoice, session_id=session.id, url=session.url, generation=generation)
            await db.commit()
            return {"checkout_url": session.url}
        except stripe.StripeError as exc:
            await db.rollback()
            raise APIException(message="Stripe checkout failed", code="PAYMENT_PROVIDER_FAILED", status_code=502) from exc
        except Exception:
            await db.rollback()
            raise

    async def webhook(self, db: AsyncSession, *, payload: bytes, signature: str) -> dict:
        if not settings.STRIPE_WEBHOOK_SECRET:
            raise APIException(message="Payment webhook is not configured", status_code=503)
        try:
            event = stripe.Webhook.construct_event(payload, signature, settings.STRIPE_WEBHOOK_SECRET)
        except (ValueError, stripe.SignatureVerificationError) as exc:
            raise APIException(message="Invalid payment webhook signature", code="INVALID_WEBHOOK", status_code=400) from exc
        if event.type not in {"checkout.session.completed", "checkout.session.async_payment_succeeded"}:
            return {"received": True}
        session = event.data.object.to_dict()
        if session.get("mode") != "payment" or session.get("payment_status") != "paid":
            return {"received": True}
        try:
            invoice = await self.repository.lock_checkout(db, session["id"])
            if not invoice:
                raise APIException(message="Checkout has not been recorded; retry webhook", code="CHECKOUT_NOT_RECORDED", status_code=503)
            metadata = session.get("metadata", {})
            if (metadata.get("invoice_id") != invoice.id or metadata.get("organization_id") != invoice.organization_id
                or session.get("currency") != invoice.currency.lower()
                or session.get("amount_total") != stripe_minor_units(invoice.amount, invoice.currency)):
                raise ConflictError(message="Payment does not match invoice", code="PAYMENT_MISMATCH")
            intent_id = session.get("payment_intent")
            if not isinstance(intent_id, str) or not intent_id:
                raise APIException(message="Payment intent is missing", status_code=400)
            existing = await self.repository.get_payment(db, invoice.id)
            if existing:
                if existing.provider_payment_id != intent_id:
                    raise ConflictError(message="Invoice already has a different payment")
                await db.commit()
                return {"received": True}
            if invoice.status not in {"Pending", "Overdue"} or invoice.paid_amount:
                raise ConflictError(message="Invoice is not payable")
            await self.repository.record_payment(db, invoice, intent_id=intent_id,
                session_id=session["id"], paid_at=datetime.now(UTC))
            await db.commit()
            return {"received": True}
        except Exception:
            await db.rollback()
            raise


invoice_payment_service = InvoicePaymentService()
