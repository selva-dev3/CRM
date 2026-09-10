"""Tenant-scoped, best-effort live update fan-out through Redis pub/sub."""

import asyncio
import json
from collections.abc import Awaitable, Callable

from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)
LIVE_EVENTS_CHANNEL = "crm:live-events"


def _redis() -> Redis:
    return Redis.from_url(settings.RATE_LIMIT_STORAGE_URI or settings.CELERY_BROKER_URL)


async def publish_live_event(
    organization_id: str,
    *,
    conversation_id: str | None = None,
    message_id: str | None = None,
) -> None:
    """Publish identifiers only; clients refetch authorized data over HTTP."""
    client = _redis()
    payload = json.dumps(
        {
            "type": "whatsapp.updated",
            "organization_id": organization_id,
            "conversation_id": conversation_id,
            "message_id": message_id,
        },
        separators=(",", ":"),
    )
    try:
        await client.publish(LIVE_EVENTS_CHANNEL, payload)
    except RedisError:
        # Real-time delivery is an optimization. Polling and the durable DB rows remain authoritative.
        logger.warning("whatsapp.live_event_publish_failed")
    finally:
        await client.aclose()


async def consume_live_events(
    callback: Callable[[str, str], Awaitable[None]], stop: asyncio.Event
) -> None:
    """Fan Redis events into this web process's authenticated sockets."""
    while not stop.is_set():
        client = _redis()
        pubsub = client.pubsub()
        try:
            await pubsub.subscribe(LIVE_EVENTS_CHANNEL)
            while not stop.is_set():
                item = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if not item:
                    continue
                raw = item.get("data")
                text = raw.decode() if isinstance(raw, bytes) else str(raw)
                data = json.loads(text)
                organization_id = data.pop("organization_id", None)
                if isinstance(organization_id, str):
                    try:
                        await callback(
                            json.dumps(data, separators=(",", ":")), organization_id
                        )
                    except Exception:
                        # A failed socket fan-out must not terminate Redis consumption.
                        logger.exception("live_event_callback_failed")
        except (RedisError, UnicodeDecodeError, ValueError, TypeError):
            if not stop.is_set():
                logger.warning("live_event_subscription_interrupted")
                await asyncio.sleep(1)
        finally:
            await pubsub.aclose()
            await client.aclose()
