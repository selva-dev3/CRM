"""Durable quote delivery using the existing quote repository, storage and mail provider."""

import asyncio
import hashlib
import hmac
from datetime import UTC, datetime
from html import escape
from io import BytesIO
from typing import Any
from uuid import uuid4

from app.core.config import settings
from app.core.errors import APIException, NotFoundError
from app.core.logging import get_logger
from app.repositories.deal_repository import DealRepository
from app.repositories.quote_repository import quote_repository
from app.services.email_service import EmailDeliveryUnknownError, send_tracked_email
from app.services.quote_pdf_service import render_quote_pdf
from app.services.s3_service import s3_service

logger = get_logger(__name__)


def acceptance_token(quote_id: str, delivery_id: str) -> str:
    return hmac.new(
        settings.SECRET_KEY.encode(),
        f"quote-acceptance:{quote_id}:{delivery_id}".encode(),
        hashlib.sha256,
    ).hexdigest()


class QuoteDeliveryService:
    async def queue(self, db, *, quote_id: str, organization_id: str, recipient_email: str) -> dict:
        try:
            quote = await quote_repository.lock_scoped(
                db, quote_id=quote_id, organization_id=organization_id
            )
            if not quote:
                raise NotFoundError(message="Quote not found")
            if quote.delivery_status in {"Pending", "Processing", "Sent"}:
                result = {
                    "message": "Quote delivery already recorded",
                    "status": quote.delivery_status,
                }
                await db.commit()
                return result
            if quote.delivery_status == "Unknown":
                raise APIException(
                    message="Delivery outcome needs provider reconciliation before resending",
                    code="QUOTE_DELIVERY_UNKNOWN",
                    status_code=409,
                )
            if quote.status != "Approved" or not quote.approved_at:
                raise APIException(message="Approve the quote before sending it", status_code=409)
            if not quote.expires_at or quote.expires_at <= datetime.now(UTC):
                raise APIException(message="Quote has expired", status_code=410)
            if quote.delivery_attempts >= 3:
                raise APIException(message="Quote delivery attempt limit reached", status_code=409)
            company, contact = await DealRepository().get_sales_customer(
                db,
                organization_id=organization_id,
                company_id=quote.company_id,
                contact_id=quote.contact_id,
            )
            if not company or not contact or contact.company_id != company.id:
                raise APIException(message="Quote customer is invalid")
            if recipient_email.strip().casefold() != contact.email.strip().casefold():
                raise APIException(message="Send the quote only to its customer contact")
            delivery_id = str(uuid4())
            token = acceptance_token(quote.id, delivery_id)
            await quote_repository.queue_delivery(
                db,
                quote,
                delivery_id=delivery_id,
                recipient_email=contact.email,
                token_hash=hashlib.sha256(token.encode()).hexdigest(),
            )
            await db.commit()
            return {
                "message": "Quote queued for PDF generation and email delivery",
                "status": "Pending",
            }
        except Exception:
            await db.rollback()
            raise

    async def deliver_one(self, session_factory) -> bool:
        # Release the database transaction before calling storage or the email provider.
        async with session_factory() as db:
            now = datetime.now(UTC)
            await quote_repository.expire_delivery_claims(db, now)
            quote = await quote_repository.claim_delivery(db, now)
            if not quote:
                await db.commit()
                return False
            quote_id, org_id, delivery_id = quote.id, quote.organization_id, quote.delivery_id
            try:
                if quote.status != "Approved" or not quote.expires_at or quote.expires_at <= now:
                    raise ValueError("Quote is no longer eligible for delivery")
                organization = await quote_repository.get_organization(db, org_id)
                company, contact = await DealRepository().get_sales_customer(
                    db,
                    organization_id=org_id,
                    company_id=quote.company_id,
                    contact_id=quote.contact_id,
                )
                if (
                    not organization
                    or not company
                    or not contact
                    or contact.company_id != company.id
                ):
                    raise ValueError("Quote customer is invalid")
                items = await quote_repository.list_items(
                    db, quote_id=quote_id, organization_id=org_id
                )
                if not items:
                    raise ValueError("Quote items are missing")
                document: dict[str, Any] = {
                    "organization": {
                        "name": organization.name,
                        "address": organization.address,
                        "email": organization.email,
                    },
                    "customer": {
                        "company": company.name,
                        "name": contact.name,
                        "email": quote.recipient_email,
                    },
                    "quote": {
                        "quote_number": quote.quote_number,
                        "currency": quote.currency,
                        "expires_at": quote.expires_at.date().isoformat(),
                        "total_amount": quote.total_amount,
                    },
                    "items": [
                        {
                            key: getattr(item, key)
                            for key in (
                                "product_name",
                                "quantity",
                                "unit_price",
                                "discount_percent",
                                "tax_percent",
                                "subtotal",
                                "discount_total",
                                "tax_total",
                                "total",
                            )
                        }
                        for item in items
                    ],
                }
                recipient = quote.recipient_email
            except ValueError:
                await quote_repository.delivery_result(db, quote, state="Failed")
                await db.commit()
                return True
            await db.commit()

        pdf_key = None
        message_id = None
        state = "Failed"
        email_started = False
        try:
            pdf = await asyncio.to_thread(render_quote_pdf, **document)
            pdf_key = await asyncio.to_thread(
                s3_service.upload_file,
                BytesIO(pdf),
                f"{org_id}/quotes/{quote_id}/{delivery_id}.pdf",
                "application/pdf",
            )
            pdf_url = await asyncio.to_thread(s3_service.generate_presigned_url, pdf_key, 604800)
            link = f"{settings.FRONTEND_URL.rstrip('/')}/public/quote#{acceptance_token(quote_id, delivery_id)}"
            body = (
                f"<p>Hello {escape(document['customer']['name'])},</p>"
                f"<p>Quote {escape(document['quote']['quote_number'])}: "
                f"{escape(document['quote']['currency'])} {document['quote']['total_amount']:.2f}. "
                f"Valid until {escape(document['quote']['expires_at'])}.</p>"
                f'<p><a href="{escape(link, quote=True)}">Review, accept or reject your quote</a></p>'
                f'<p><a href="{escape(pdf_url, quote=True)}">Download quote PDF (link valid for 7 days)</a></p>'
            )
            email_started = True
            message_id = await asyncio.to_thread(
                send_tracked_email,
                to_email=recipient,
                subject=f"Quote {document['quote']['quote_number']}",
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
                "Quote delivery failed quote_id=%s error_type=%s", quote_id, type(exc).__name__
            )

        async with session_factory() as db:
            quote = await quote_repository.lock_scoped(
                db, quote_id=quote_id, organization_id=org_id
            )
            if quote and quote.delivery_id == delivery_id and quote.delivery_status == "Processing":
                await quote_repository.delivery_result(
                    db,
                    quote,
                    state=state,
                    pdf_key=pdf_key,
                    message_id=message_id,
                    at=datetime.now(UTC),
                )
                await db.commit()
        return True


quote_delivery_service = QuoteDeliveryService()
