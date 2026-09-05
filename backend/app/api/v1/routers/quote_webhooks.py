"""Authenticated provider callbacks for Quote email delivery."""

import hmac
from datetime import UTC, datetime

from fastapi import APIRouter, Header, HTTPException, Request, status
from sqlalchemy import select

from app.core.config import settings
from app.core.logging import get_logger
from app.db.session import AsyncSessionLocal
from app.models import Quote, QuoteDeliveryAttempt

router = APIRouter()
logger = get_logger(__name__)

_EVENT_STATES = {
    "delivered": "Delivered",
    "soft_bounce": "Failed",
    "hard_bounce": "Bounced",
    "blocked": "Failed",
    "invalid_email": "Failed",
    "failed": "Failed",
}
_TERMINAL_STATES = {"Delivered", "Bounced", "Failed"}


def _event_time(value) -> datetime:
    if value is None:
        return datetime.now(UTC)
    try:
        timestamp = float(value)
        if timestamp > 10_000_000_000:
            timestamp /= 1000
        return datetime.fromtimestamp(timestamp, tz=UTC)
    except (TypeError, ValueError, OverflowError):
        return datetime.now(UTC)


@router.post("/brevo", status_code=status.HTTP_200_OK)
async def brevo_quote_webhook(
    request: Request,
    x_brevo_webhook_secret: str | None = Header(None),
):
    configured_secret = settings.BREVO_WEBHOOK_SECRET
    if not configured_secret or not x_brevo_webhook_secret or not hmac.compare_digest(
        x_brevo_webhook_secret, configured_secret
    ):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid webhook")

    try:
        payload = await request.json()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid event payload"
        ) from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid event payload")
    event = str(payload.get("event", "")).strip().lower()
    state = _EVENT_STATES.get(event)
    message_id = payload.get("message-id") or payload.get("messageId")
    event_id = payload.get("id") or payload.get("event_id")
    if not state or not isinstance(message_id, str) or not isinstance(event_id, str):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid event payload")

    async with AsyncSessionLocal() as db:
        existing_event = await db.scalar(
            select(QuoteDeliveryAttempt).where(
                QuoteDeliveryAttempt.provider_event_id == event_id
            )
        )
        if existing_event:
            return {"status": "already_processed"}

        attempt = await db.scalar(
            select(QuoteDeliveryAttempt)
            .where(QuoteDeliveryAttempt.provider_message_id == message_id)
            .with_for_update()
        )
        if not attempt:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Delivery not found")

        now = _event_time(payload.get("ts_event") or payload.get("timestamp"))
        attempt.provider_event_id = event_id
        attempt.delivery_status = state
        attempt.updated_at = now
        if state == "Delivered":
            attempt.delivered_at = now
        else:
            attempt.failed_at = now
            attempt.failure_reason = payload.get("reason") or event

        quote = await db.scalar(
            select(Quote)
            .where(Quote.id == attempt.quote_id, Quote.organization_id == attempt.organization_id)
            .with_for_update()
        )
        if quote and quote.delivery_id == attempt.delivery_id:
            current = quote.delivery_status or ""
            if current not in _TERMINAL_STATES or state == "Delivered":
                quote.delivery_status = state

        await db.commit()
        logger.info(
            "Quote delivery provider event processed quote_id=%s organization_id=%s "
            "delivery_id=%s status=%s",
            attempt.quote_id,
            attempt.organization_id,
            attempt.delivery_id,
            state,
        )
    return {"status": "processed", "delivery_status": state}
