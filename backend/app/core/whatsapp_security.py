"""Provider boundary checks; never log payloads, headers or credentials."""

import hashlib
import hmac
import re
import secrets
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta

from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.config import settings
from app.core.errors import APIException, ForbiddenError
from app.core.logging import get_logger

logger = get_logger(__name__)
WORKER_HEARTBEAT_KEY = "whatsapp:worker:heartbeat"
# Longer than the Celery hard time limit (270s), plus the scheduling interval.
WORKER_HEARTBEAT_TTL_SECONDS = 300
SWEEP_LOCK_KEY = "whatsapp:sweep:lock"
SWEEP_LOCK_TTL_SECONDS = 285


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


async def record_worker_heartbeat(now: datetime | None = None) -> None:
    """Record sweeper liveness; tenant backlog age separately measures processing health."""
    client = Redis.from_url(settings.RATE_LIMIT_STORAGE_URI or settings.CELERY_BROKER_URL)
    try:
        await client.set(
            WORKER_HEARTBEAT_KEY,
            (now or datetime.now(UTC)).isoformat(),
            ex=WORKER_HEARTBEAT_TTL_SECONDS,
        )
    except RedisError:
        logger.warning("whatsapp.worker_heartbeat_failed")
    finally:
        await client.aclose()


@asynccontextmanager
async def whatsapp_sweep_lock():
    """Prevent overlapping recovery sweeps across workers and scheduler retries."""
    token = secrets.token_hex(16)
    client = Redis.from_url(settings.RATE_LIMIT_STORAGE_URI or settings.CELERY_BROKER_URL)
    acquired = False
    try:
        try:
            acquired = bool(
                await client.set(SWEEP_LOCK_KEY, token, nx=True, ex=SWEEP_LOCK_TTL_SECONDS)
            )
        except RedisError:
            logger.warning("whatsapp.sweep_lock_unavailable")
            yield False
            return
        try:
            yield acquired
        finally:
            if acquired:
                try:
                    await client.eval(
                        "if redis.call('GET',KEYS[1])==ARGV[1] then return redis.call('DEL',KEYS[1]) else return 0 end",
                        1,
                        SWEEP_LOCK_KEY,
                        token,
                    )
                except RedisError:
                    logger.warning("whatsapp.sweep_lock_release_failed")
    finally:
        await client.aclose()


async def worker_heartbeat() -> tuple[str, datetime | None]:
    """Return explicit worker health; Redis outages are not reported as healthy."""
    client = Redis.from_url(settings.RATE_LIMIT_STORAGE_URI or settings.CELERY_BROKER_URL)
    try:
        raw = await client.get(WORKER_HEARTBEAT_KEY)
    except RedisError:
        return "UNAVAILABLE", None
    finally:
        await client.aclose()
    if raw is None:
        return "OFFLINE", None
    try:
        value = raw.decode() if isinstance(raw, bytes) else str(raw)
        timestamp = datetime.fromisoformat(value)
        if timestamp.tzinfo is None:
            raise ValueError("Heartbeat timestamp must be timezone-aware")
    except (UnicodeDecodeError, ValueError):
        return "INVALID", None
    age = datetime.now(UTC) - timestamp
    if age < timedelta(seconds=-5):
        return "INVALID", None
    if age > timedelta(seconds=WORKER_HEARTBEAT_TTL_SECONDS):
        return "OFFLINE", timestamp
    return "HEALTHY", timestamp
