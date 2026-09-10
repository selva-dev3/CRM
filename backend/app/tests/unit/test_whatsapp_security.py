from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError
from redis.exceptions import RedisError

from app.core import whatsapp_security
from app.core.errors import ForbiddenError
from app.core.phone import normalize_phone, normalize_provider_display_phone
from app.core.whatsapp_security import service_window_open, verify_signature
from app.schemas.whatsapp import WebhookPayload


class _RedisClient:
    def __init__(self, value=None, error: Exception | None = None):
        self.value = value
        self.error = error
        self.set_calls = []

    async def get(self, _key):
        if self.error:
            raise self.error
        return self.value

    async def set(self, *args, **kwargs):
        self.set_calls.append((args, kwargs))

    async def aclose(self):
        return None


@pytest.mark.parametrize(
    ("raw", "region", "expected"),
    [
        ("+91 98765-43210", None, "+919876543210"),
        ("(415) 555-2671", "US", "+14155552671"),
        ("+44 (0) 20 7946 0958", None, "+442079460958"),
    ],
)
def test_phone_normalization_uses_e164(raw, region, expected):
    assert normalize_phone(raw, region) == expected


@pytest.mark.parametrize("raw", ["9876543210", "customer +14155552671", "", "+12001230101"])
def test_phone_normalization_rejects_ambiguous_or_invalid_values(raw):
    with pytest.raises(ValueError):
        normalize_phone(raw)


def test_provider_phone_requires_digits_and_adds_plus():
    assert normalize_phone("14155552671", provider=True) == "+14155552671"
    with pytest.raises(ValueError):
        normalize_phone("+14155552671", provider=True)


def test_provider_display_phone_accepts_meta_test_number():
    assert normalize_provider_display_phone("+1 (555) 673-4737") == "+15556734737"


@pytest.mark.parametrize("raw", ["5556734737", "+123", "+1 555 test", ""])
def test_provider_display_phone_rejects_malformed_values(raw):
    with pytest.raises(ValueError):
        normalize_provider_display_phone(raw)


def test_signature_validation_is_constant_format_and_secret_bound():
    import hashlib
    import hmac

    body = b'{"safe":"payload"}'
    signature = "sha256=" + hmac.new(b"secret-value", body, hashlib.sha256).hexdigest()
    verify_signature(body, signature, "secret-value")
    with pytest.raises(ForbiddenError):
        verify_signature(body + b"x", signature, "secret-value")
    with pytest.raises(ForbiddenError):
        verify_signature(body, None, "secret-value")


def test_customer_service_window_is_strictly_less_than_24_hours():
    now = datetime.now(UTC)
    assert service_window_open(now - timedelta(hours=23, minutes=59), now)
    assert not service_window_open(now - timedelta(hours=24), now)
    assert not service_window_open(now + timedelta(seconds=1), now)
    assert not service_window_open(None, now)


@pytest.mark.asyncio
async def test_worker_heartbeat_reports_only_valid_shared_redis_state(monkeypatch):
    now = datetime.now(UTC)
    client = _RedisClient(now.isoformat().encode())
    monkeypatch.setattr(whatsapp_security.Redis, "from_url", lambda _url: client)

    status, timestamp = await whatsapp_security.worker_heartbeat()

    assert status == "HEALTHY"
    assert timestamp == now

    # An in-progress sweep can legitimately exceed the old 60-second TTL.
    client.value = (now - timedelta(seconds=200)).isoformat()
    assert (await whatsapp_security.worker_heartbeat())[0] == "HEALTHY"

    stale = _RedisClient((now - timedelta(minutes=5)).isoformat())
    monkeypatch.setattr(whatsapp_security.Redis, "from_url", lambda _url: stale)
    status, timestamp = await whatsapp_security.worker_heartbeat()
    assert status == "OFFLINE"
    assert timestamp is not None

    unavailable = _RedisClient(error=RedisError("synthetic outage"))
    monkeypatch.setattr(whatsapp_security.Redis, "from_url", lambda _url: unavailable)
    assert await whatsapp_security.worker_heartbeat() == ("UNAVAILABLE", None)


def test_webhook_schema_accepts_message_and_status_without_extra_identity_sources():
    payload = WebhookPayload.model_validate(
        {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": "1001",
                    "changes": [
                        {
                            "field": "messages",
                            "value": {
                                "messaging_product": "whatsapp",
                                "metadata": {"phone_number_id": "2002"},
                                "messages": [
                                    {
                                        "id": "wamid.1",
                                        "from": "14155552671",
                                        "timestamp": "1788921000",
                                        "type": "text",
                                        "text": {"body": "Hi"},
                                    }
                                ],
                                "statuses": [
                                    {
                                        "id": "wamid.2",
                                        "status": "delivered",
                                        "timestamp": "1788921001",
                                        "recipient_id": "14155552671",
                                    }
                                ],
                            },
                        }
                    ],
                }
            ],
        }
    )
    assert payload.entry[0].changes[0].value.messages[0].sender == "14155552671"


@pytest.mark.parametrize(
    "change",
    [
        {
            "field": "messages",
            "value": {"messaging_product": "telegram", "metadata": {"phone_number_id": "2"}},
        },
        {
            "field": "contacts",
            "value": {"messaging_product": "whatsapp", "metadata": {"phone_number_id": "2"}},
        },
        {
            "field": "messages",
            "value": {
                "messaging_product": "whatsapp",
                "metadata": {"phone_number_id": "not-an-id"},
            },
        },
    ],
)
def test_webhook_schema_rejects_unexpected_provider_boundaries(change):
    with pytest.raises(ValidationError):
        WebhookPayload.model_validate(
            {"object": "whatsapp_business_account", "entry": [{"id": "1", "changes": [change]}]}
        )
