"""Durable invoice, reminder, and verified-payment receipt delivery."""

import asyncio
from datetime import UTC, datetime, timedelta
from html import escape
from io import BytesIO
from uuid import uuid4

from app.core.config import settings
from app.core.errors import APIException, ConflictError, NotFoundError
from app.core.logging import get_logger
from app.repositories.invoice_repository import invoice_repository
from app.repositories.payment_repository import PaymentRepository
from app.repositories.quote_repository import quote_repository
from app.services.email_service import EmailDeliveryUnknownError, send_tracked_email
from app.services.invoice_payment_service import invoice_payment_service
from app.services.invoice_pdf_service import render_invoice_pdf, render_receipt_pdf
from app.services.s3_service import s3_service

logger = get_logger(__name__)


class InvoiceDeliveryService:
    def __init__(self) -> None:
        self.payment_repository = PaymentRepository()

    async def pdf_url(self, db, *, invoice_id: str, organization_id: str) -> str:
        invoice = await invoice_repository.get_scoped(
            db, invoice_id=invoice_id, organization_id=organization_id
        )
        if not invoice:
            raise NotFoundError(message="Invoice not found")
        if not invoice.pdf_s3_key:
            raise ConflictError(message="Invoice PDF has not been generated yet")
        return await asyncio.to_thread(s3_service.generate_presigned_url, invoice.pdf_s3_key, 3600)

    async def send_reminder(self, db, *, invoice_id: str, organization_id: str) -> dict:
        invoice = await self.payment_repository.lock_invoice(
            db, invoice_id=invoice_id, organization_id=organization_id
        )
        if not invoice:
            raise NotFoundError(message="Invoice not found")
        if invoice.status not in {"Pending", "Overdue"} or invoice.paid_amount:
            raise ConflictError(message="Only unpaid invoices can receive payment reminders")
        now = datetime.now(UTC)
        if invoice.reminder_count >= 3:
            raise ConflictError(message="The automatic reminder limit has been reached")
        if invoice.last_reminded_at and invoice.last_reminded_at > now - timedelta(hours=24):
            raise ConflictError(message="A reminder was already sent in the last 24 hours")
        if not invoice.recipient_email or not invoice.stripe_checkout_url:
            raise ConflictError(message="Deliver the invoice and create its payment link first")
        if not settings.BREVO_API_KEY:
            raise APIException(message="Email provider is not configured", status_code=503)
        recipient = invoice.recipient_email
        subject = f"Payment reminder: invoice {invoice.invoice_number}"
        body = (
            f"<p>Payment for invoice {escape(invoice.invoice_number)} is still pending.</p>"
            f"<p>Amount due: {escape(invoice.currency)} {invoice.amount:.2f}.</p>"
            f'<p><a href="{escape(invoice.stripe_checkout_url, quote=True)}">Pay securely with Stripe</a></p>'
        )
        idempotency_key = f"invoice-reminder-{invoice.id}-{now.date().isoformat()}"
        try:
            message_id = await asyncio.to_thread(
                send_tracked_email,
                to_email=recipient,
                subject=subject,
                html_content=body,
                idempotency_key=idempotency_key,
            )
        except (EmailDeliveryUnknownError, ValueError) as exc:
            await db.rollback()
            raise APIException(
                message="Payment reminder delivery could not be confirmed",
                code="REMINDER_DELIVERY_FAILED",
                status_code=502,
            ) from exc
        await invoice_repository.record_reminder(db, invoice, now)
        if invoice.due_date < now:
            invoice.status = "Overdue"
        await db.commit()
        return {
            "message": "Payment reminder sent",
            "status": "success",
            "provider_message_id": message_id,
        }

    async def deliver_one(self, session_factory) -> bool:
        async with session_factory() as db:
            now = datetime.now(UTC)
            await invoice_repository.expire_delivery_claims(db, now)
            invoice = await invoice_repository.claim_delivery(db, now)
            if not invoice:
                await db.commit()
                return False
            invoice_id = invoice.id
            org_id = invoice.organization_id
            delivery_id = invoice.delivery_id or str(uuid4())
            invoice.delivery_id = delivery_id
            try:
                organization = await quote_repository.get_organization(db, org_id)
                items = await invoice_repository.list_items(
                    db, invoice_id=invoice_id, organization_id=org_id
                )
                quote = (
                    await quote_repository.get_scoped(
                        db, quote_id=invoice.quote_id, organization_id=org_id
                    )
                    if invoice.quote_id
                    else None
                )
                customer = invoice.billing_snapshot or {}
                if (
                    not organization
                    or not items
                    or not invoice.recipient_email
                    or invoice.status not in {"Pending", "Overdue"}
                ):
                    raise ValueError("Invoice is not eligible for delivery")
                document = {
                    "organization": {
                        "name": organization.name,
                        "address": organization.address,
                        "email": organization.email,
                    },
                    "customer": customer,
                    "invoice": {
                        "invoice_number": invoice.invoice_number,
                        "quote_number": quote.quote_number if quote else None,
                        "due_date": invoice.due_date.date().isoformat(),
                        "currency": invoice.currency,
                        "subtotal": invoice.subtotal,
                        "discount_total": invoice.discount_total,
                        "tax_total": invoice.tax_total,
                        "amount": invoice.amount,
                    },
                    "items": [
                        {
                            "product_name": item.product_name,
                            "quantity": item.quantity,
                            "unit_price": item.unit_price,
                            "discount_percent": item.discount_percent,
                            "tax_percent": item.tax_percent,
                            "total": item.total,
                        }
                        for item in items
                    ],
                    "recipient": invoice.recipient_email,
                }
            except ValueError:
                await invoice_repository.delivery_result(db, invoice, state="Failed")
                await db.commit()
                return True
            await db.commit()

        pdf_key = None
        message_id = None
        state = "Failed"
        email_started = False
        try:
            async with session_factory() as db:
                checkout = await invoice_payment_service.checkout(
                    db, invoice_id=invoice_id, organization_id=org_id
                )
            pdf = await asyncio.to_thread(
                render_invoice_pdf,
                **{key: document[key] for key in ("organization", "customer", "invoice", "items")},
            )
            pdf_key = await asyncio.to_thread(
                s3_service.upload_file,
                BytesIO(pdf),
                f"{org_id}/invoices/{invoice_id}/{delivery_id}.pdf",
                "application/pdf",
            )
            pdf_url = await asyncio.to_thread(s3_service.generate_presigned_url, pdf_key, 604800)
            body = (
                f"<p>Hello {escape(str(document['customer'].get('contact') or 'Customer'))},</p>"
                f"<p>Invoice {escape(document['invoice']['invoice_number'])}: "
                f"{escape(document['invoice']['currency'])} {document['invoice']['amount']:.2f}. "
                f"Due {escape(document['invoice']['due_date'])}.</p>"
                f'<p><a href="{escape(checkout["checkout_url"], quote=True)}">Pay securely with Stripe</a></p>'
                f'<p><a href="{escape(pdf_url, quote=True)}">Download invoice PDF (link valid for 7 days)</a></p>'
            )
            email_started = True
            message_id = await asyncio.to_thread(
                send_tracked_email,
                to_email=document["recipient"],
                subject=f"Invoice {document['invoice']['invoice_number']}",
                html_content=body,
                idempotency_key=delivery_id,
            )
            state = "Sent"
        except EmailDeliveryUnknownError:
            state = "Unknown"
        except ValueError:
            state = "Failed"
        except Exception as exc:
            state = "Unknown" if email_started else "Failed"
            logger.warning(
                "Invoice delivery failed invoice_id=%s error_type=%s",
                invoice_id,
                type(exc).__name__,
            )

        async with session_factory() as db:
            invoice = await invoice_repository.get_scoped(
                db, invoice_id=invoice_id, organization_id=org_id
            )
            if (
                invoice
                and invoice.delivery_id == delivery_id
                and invoice.delivery_status == "Processing"
            ):
                await invoice_repository.delivery_result(
                    db,
                    invoice,
                    state=state,
                    pdf_key=pdf_key,
                    message_id=message_id,
                    at=datetime.now(UTC),
                )
                await db.commit()
        return True

    async def deliver_receipt_one(self, session_factory) -> bool:
        async with session_factory() as db:
            now = datetime.now(UTC)
            await self.payment_repository.expire_receipt_claims(db, now)
            payment = await self.payment_repository.claim_receipt(db, now)
            if not payment:
                await db.commit()
                return False
            payment_id = payment.id
            org_id = payment.organization_id
            invoice = await invoice_repository.get_scoped(
                db, invoice_id=payment.invoice_id, organization_id=org_id
            )
            organization = await quote_repository.get_organization(db, org_id)
            if not invoice or not organization or invoice.status != "Paid":
                await self.payment_repository.receipt_result(db, payment, state="Failed")
                await db.commit()
                return True
            customer = invoice.billing_snapshot or {}
            recipient = customer.get("email")
            if not recipient:
                await self.payment_repository.receipt_result(db, payment, state="Failed")
                await db.commit()
                return True
            document = {
                "organization": {
                    "name": organization.name,
                    "address": organization.address,
                },
                "customer": customer,
                "invoice": {"invoice_number": invoice.invoice_number},
                "payment": {
                    "payment_id": payment.id,
                    "provider_reference": payment.provider_payment_id,
                    "paid_at": payment.paid_at.isoformat(),
                    "payment_method": payment.payment_method,
                    "currency": payment.currency,
                    "amount": payment.amount,
                },
            }
            await db.commit()

        receipt_key = None
        message_id = None
        state = "Failed"
        email_started = False
        try:
            pdf = await asyncio.to_thread(render_receipt_pdf, **document)
            receipt_key = await asyncio.to_thread(
                s3_service.upload_file,
                BytesIO(pdf),
                f"{org_id}/receipts/{payment_id}.pdf",
                "application/pdf",
            )
            receipt_url = await asyncio.to_thread(
                s3_service.generate_presigned_url, receipt_key, 604800
            )
            body = (
                f"<p>Payment received for invoice {escape(document['invoice']['invoice_number'])}.</p>"
                f"<p>Amount: {escape(document['payment']['currency'])} {document['payment']['amount']:.2f}.</p>"
                f'<p><a href="{escape(receipt_url, quote=True)}">Download receipt (link valid for 7 days)</a></p>'
            )
            email_started = True
            message_id = await asyncio.to_thread(
                send_tracked_email,
                to_email=recipient,
                subject=f"Payment receipt for {document['invoice']['invoice_number']}",
                html_content=body,
                idempotency_key=f"payment-receipt-{payment_id}",
            )
            state = "Sent"
        except EmailDeliveryUnknownError:
            state = "Unknown"
        except ValueError:
            state = "Failed"
        except Exception as exc:
            state = "Unknown" if email_started else "Failed"
            logger.warning(
                "Receipt delivery failed payment_id=%s error_type=%s",
                payment_id,
                type(exc).__name__,
            )
        async with session_factory() as db:
            payment = await self.payment_repository.get_by_id(db, payment_id)
            if payment and payment.receipt_delivery_status == "Processing":
                await self.payment_repository.receipt_result(
                    db,
                    payment,
                    state=state,
                    receipt_key=receipt_key,
                    message_id=message_id,
                )
                await db.commit()
        return True


invoice_delivery_service = InvoiceDeliveryService()
