"""Best-effort Celery dispatch backed by the durable WhatsApp database queues."""

from app.core.logging import get_logger
from app.workers.celery_app import celery_app

logger = get_logger(__name__)
WHATSAPP_QUEUE = "whatsapp"
TARGET_TASK_EXPIRES_SECONDS = 90


def enqueue_webhook_event(event_id: str, organization_id: str) -> None:
    try:
        celery_app.send_task(
            "app.workers.whatsapp.process_webhook_event",
            args=[event_id, organization_id],
            queue=WHATSAPP_QUEUE,
            expires=TARGET_TASK_EXPIRES_SECONDS,
        )
    except Exception:
        logger.warning("whatsapp.event_dispatch_failed", extra={"request_id": event_id})


def enqueue_message(
    message_id: str, organization_id: str, *, delay_seconds: int = 0
) -> None:
    delay_seconds = max(0, delay_seconds)
    options = {
        "queue": WHATSAPP_QUEUE,
        "expires": TARGET_TASK_EXPIRES_SECONDS + delay_seconds,
    }
    if delay_seconds:
        options["countdown"] = delay_seconds
    try:
        celery_app.send_task(
            "app.workers.whatsapp.process_message",
            args=[message_id, organization_id],
            **options,
        )
    except Exception:
        logger.warning("whatsapp.message_dispatch_failed", extra={"request_id": message_id})
