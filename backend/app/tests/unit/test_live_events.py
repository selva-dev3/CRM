import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core import live_events


@pytest.mark.asyncio
async def test_live_event_publish_contains_only_refresh_identifiers(monkeypatch):
    client = AsyncMock()
    monkeypatch.setattr(live_events, "_redis", lambda: client)

    await live_events.publish_live_event(
        "org-a", conversation_id="conversation-a", message_id="message-a"
    )

    channel, raw = client.publish.await_args.args
    assert channel == live_events.LIVE_EVENTS_CHANNEL
    assert json.loads(raw) == {
        "type": "whatsapp.updated",
        "organization_id": "org-a",
        "conversation_id": "conversation-a",
        "message_id": "message-a",
    }
    client.aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_live_event_consumer_strips_tenant_before_socket_broadcast(monkeypatch):
    stop = asyncio.Event()
    callback_args = []

    async def callback(*args):
        callback_args.append(args)
        if len(callback_args) == 1:
            raise RuntimeError("synthetic socket fan-out failure")
        stop.set()

    pubsub = AsyncMock()
    pubsub.get_message.return_value = {
        "data": b'{"type":"whatsapp.updated","organization_id":"org-a","message_id":"m1"}'
    }
    client = MagicMock()
    client.pubsub.return_value = pubsub
    client.aclose = AsyncMock()
    monkeypatch.setattr(live_events, "_redis", lambda: client)

    await live_events.consume_live_events(callback, stop)

    assert len(callback_args) == 2
    payload, organization_id = callback_args[-1]
    assert organization_id == "org-a"
    assert json.loads(payload) == {"type": "whatsapp.updated", "message_id": "m1"}
    pubsub.aclose.assert_awaited_once()
