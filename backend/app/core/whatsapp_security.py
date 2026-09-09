"""Provider boundary checks; never log payloads, headers or credentials."""

import hashlib
import hmac
import re
from datetime import UTC, datetime, timedelta

from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.config import settings
from app.core.errors import APIException, ForbiddenError


def verify_signature(body: bytes, signature: str | None, secret: str | None) -> None:
    if not secret or not signature or not re.fullmatch(r"sha256=[a-f0-9]{64}", signature):
        raise ForbiddenError(message="Invalid webhook signature.")
    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise ForbiddenError(message="Invalid webhook signature.")


def service_window_open(
    last_customer_message_at: datetime | None, now: datetime | None = None
) -> bool:
    now = now or datetime.now(UTC)
    return last_customer_message_at is not None and timedelta(
        0
    ) <= now - last_customer_message_at < timedelta(hours=24)


async def enforce_rate_limit(scope: str, limit: int) -> None:
    """Atomic shared counter, fail closed if Redis is unavailable."""
    client = Redis.from_url(settings.RATE_LIMIT_STORAGE_URI or settings.CELERY_BROKER_URL)
    try:
        count = await client.eval(
            "local n=redis.call('INCR',KEYS[1]); if n==1 then redis.call('EXPIRE',KEYS[1],60) end; return n",
            1,
            "whatsapp:rate:" + scope,
        )
        if count > limit:
            raise APIException(
                message="WhatsApp rate limit reached. Try again later.",
                code="WHATSAPP_RATE_LIMITED",
                status_code=429,
            )
    except RedisError as exc:
        raise APIException(
            message="WhatsApp is temporarily unavailable.",
            code="WHATSAPP_RATE_LIMIT_UNAVAILABLE",
            status_code=503,
        ) from exc
    finally:
        await client.aclose()
