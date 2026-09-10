from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.errors import APIException
from app.workers import whatsapp as worker


@pytest.fixture(autouse=True)
def stub_phone_guard(monkeypatch):
    guard = AsyncMock()
    monkeypatch.setattr(worker.service.repository, "lock_phone_guard", guard)
    return guard


class _Result:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value

    def scalar_one(self):
        return self.value

    def scalars(self):
        return self

    def all(self):
        return self.value


class _Context:
    def __init__(self, db):
        self.db = db

    async def __aenter__(self):
        return self.db

    async def __aexit__(self, *_args):
        return False


def _factory(*sessions):
    remaining = list(sessions)

    def factory():
        return _Context(remaining.pop(0))

    return factory


def _outbound_fixture():
    now = datetime.now(UTC)
    message = SimpleNamespace(
        id="message-a",
        organization_id="org-a",
        integration_id="integration-a",
        conversation_id="conversation-a",
        actor_user_id="ai-user",
        direction="OUTBOUND",
        source="AI",
        message_type="text",
        body="stale value",
        ai_topic="invoice",
        ai_query_plan=None,
        template_payload=None,
        status="PENDING",
        work_status="PENDING",
        attempts=0,
        next_attempt_at=now,
        claimed_at=None,
        error_code=None,
        error_message=None,
        provider_message_id=None,
        failed_at=None,
        recipient_phone="+14155552671",
    )
    conversation = SimpleNamespace(
        id="conversation-a",
        organization_id="org-a",
        integration_id="integration-a",
        identity_id="identity-a",
        ai_enabled=True,
        status="OPEN",
        last_customer_message_at=now,
        last_message_at=now,
        assigned_user_id="agent-a",
    )
    config = SimpleNamespace(
        id="integration-a",
        organization_id="org-a",
        enabled=True,
        ai_user_id="ai-user",
        phone_number_id="2002",
        display_phone_number="+12025550100",
        last_successful_message_at=None,
    )
    identity = SimpleNamespace(
        state="MATCHED_CONTACT",
        contact_id="contact-a",
        lead_id=None,
        consent="UNKNOWN",
        normalized_phone_number="+14155552671",
    )
    user = SimpleNamespace(id="ai-user", organization_id="org-a", is_active=True)
    claim_db = AsyncMock()
    claim_db.execute = AsyncMock(return_value=_Result(message))
    process_db = AsyncMock()
    process_db.execute = AsyncMock(side_effect=[_Result(message), _Result(conversation)])
    return message, conversation, config, identity, user, claim_db, process_db


@pytest.mark.asyncio
async def test_status_receipt_is_processed_for_suspended_organization(monkeypatch):
    event = SimpleNamespace(
        id="event-a",
        organization_id="org-a",
        integration_id="integration-a",
        correlation_id="request-a",
        status="PENDING",
        attempts=0,
        next_attempt_at=datetime.now(UTC),
        error_code=None,
        payload={
            "kind": "status",
            "data": {
                "id": "wamid.confirmed",
                "status": "delivered",
                "timestamp": "1788900000",
                "recipient_id": "14155552671",
            },
        },
    )
    config = SimpleNamespace(id="integration-a", organization_id="org-a")
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_Result(event))
    repository = worker.service.repository
    monkeypatch.setattr(repository, "configuration", AsyncMock(return_value=config))
    active = AsyncMock(return_value=False)
    monkeypatch.setattr(repository, "organization_active", active)
    apply_status = AsyncMock(return_value=True)
    monkeypatch.setattr(repository, "apply_status", apply_status)
    monkeypatch.setattr(worker.service, "commit", AsyncMock())

    assert await worker.process_event(db) is True

    active.assert_not_awaited()
    apply_status.assert_awaited_once()
    assert event.status == "DONE"


@pytest.mark.asyncio
async def test_inbound_event_is_retained_while_organization_is_suspended(monkeypatch):
    payload = {
        "kind": "message",
        "data": {
            "id": "wamid.stop",
            "from": "14155552671",
            "timestamp": "1788900000",
            "type": "text",
            "text": {"body": "STOP"},
        },
    }
    event = SimpleNamespace(
        id="event-stop",
        organization_id="org-a",
        integration_id="integration-a",
        correlation_id="request-stop",
        status="PENDING",
        attempts=0,
        next_attempt_at=datetime.now(UTC),
        error_code=None,
        payload=payload,
    )
    config = SimpleNamespace(id="integration-a", organization_id="org-a")
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_Result(event))
    repository = worker.service.repository
    monkeypatch.setattr(repository, "configuration", AsyncMock(return_value=config))
    monkeypatch.setattr(repository, "organization_active", AsyncMock(return_value=False))
    audit = MagicMock()
    monkeypatch.setattr(worker.service, "audit", audit)
    monkeypatch.setattr(worker.service, "commit", AsyncMock())

    assert await worker.process_event(db) is True

    assert event.status == "PENDING"
    assert event.error_code == "ORGANIZATION_INACTIVE"
    assert event.payload == payload
    assert event.next_attempt_at > datetime.now(UTC)
    audit.assert_called_once_with(db, "org-a", "processing_suspended", "event-stop")

    identity = SimpleNamespace(
        id="identity-a",
        state="MATCHED_CONTACT",
        consent="UNKNOWN",
        consent_updated_at=None,
    )
    conversation = SimpleNamespace(
        id="conversation-a", ai_enabled=True, status="OPEN", assigned_user_id=None
    )
    message = SimpleNamespace(
        id="message-stop", body="STOP", message_type="text", work_status="PENDING"
    )
    event.next_attempt_at = datetime.now(UTC)
    repository.organization_active.return_value = True
    monkeypatch.setattr(
        repository, "persist_inbound", AsyncMock(return_value=(conversation, message))
    )
    monkeypatch.setattr(repository, "identity", AsyncMock(return_value=identity))
    monkeypatch.setattr(worker.service, "ensure_eligible_assignee", AsyncMock())
    monkeypatch.setattr(worker.service, "notify", AsyncMock())

    assert await worker.process_event(db) is True

    assert identity.consent == "OPTED_OUT"
    assert conversation.ai_enabled is False
    assert event.status == "DONE"


@pytest.mark.asyncio
async def test_unsupported_inbound_message_is_persisted_for_handoff_without_media_retry(
    monkeypatch,
):
    event = SimpleNamespace(
        id="event-location",
        organization_id="org-a",
        integration_id="integration-a",
        correlation_id="request-location",
        status="PENDING",
        attempts=0,
        next_attempt_at=datetime.now(UTC),
        error_code=None,
        payload={
            "kind": "message",
            "data": {
                "id": "wamid.location",
                "from": "14155552671",
                "timestamp": "1788900000",
                "type": "location",
            },
        },
    )
    config = SimpleNamespace(id="integration-a", organization_id="org-a")
    identity = SimpleNamespace(id="identity-a", state="MATCHED_CONTACT", consent="UNKNOWN")
    conversation = SimpleNamespace(
        id="conversation-a", ai_enabled=True, status="OPEN", assigned_user_id=None
    )
    message = SimpleNamespace(
        id="message-location", body=None, message_type="location", work_status="PENDING"
    )
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_Result(event))
    repository = worker.service.repository
    monkeypatch.setattr(repository, "configuration", AsyncMock(return_value=config))
    monkeypatch.setattr(repository, "organization_active", AsyncMock(return_value=True))
    monkeypatch.setattr(
        repository, "persist_inbound", AsyncMock(return_value=(conversation, message))
    )
    monkeypatch.setattr(repository, "identity", AsyncMock(return_value=identity))
    monkeypatch.setattr(worker.service, "ensure_eligible_assignee", AsyncMock())
    monkeypatch.setattr(worker.service, "notify", AsyncMock())
    monkeypatch.setattr(worker.service, "audit", MagicMock())
    monkeypatch.setattr(worker.service, "commit", AsyncMock())

    queued_messages = []
    assert await worker.process_event(db, queued_messages=queued_messages) is True

    assert event.status == "DONE"
    assert message.work_status == "DONE"
    assert conversation.ai_enabled is False
    assert conversation.status == "HUMAN_HANDOFF"
    assert queued_messages == [("message-location", "org-a")]


@pytest.mark.asyncio
async def test_reactivated_organization_cannot_send_template_after_retained_opt_out(monkeypatch):
    message, _conversation, config, identity, _user, claim_db, process_db = _outbound_fixture()
    message.message_type = "template"
    message.template_payload = {"template_id": "template-a", "parameters": []}
    identity.consent = "OPTED_OUT"
    repository = worker.service.repository
    monkeypatch.setattr(repository, "configuration", AsyncMock(return_value=config))
    monkeypatch.setattr(repository, "identity", AsyncMock(return_value=identity))
    monkeypatch.setattr(repository, "organization_active", AsyncMock(return_value=True))
    provider = AsyncMock()
    monkeypatch.setattr(worker.service, "provider", provider)
    monkeypatch.setattr(worker.service, "commit", AsyncMock())
    monkeypatch.setattr(worker.service, "notify", AsyncMock())
    monkeypatch.setattr(worker.service, "audit", MagicMock())

    assert await worker.process_message(_factory(claim_db, process_db)) is True

    provider.assert_not_awaited()
    assert message.status == "FAILED"
    assert message.error_code == "WHATSAPP_SENDING_DISABLED"


@pytest.mark.asyncio
async def test_ai_outbound_is_reauthorized_and_rerendered_before_send(
    monkeypatch, stub_phone_guard
):
    message, conversation, config, identity, user, claim_db, process_db = _outbound_fixture()
    repository = worker.service.repository
    monkeypatch.setattr(repository, "configuration", AsyncMock(return_value=config))
    monkeypatch.setattr(repository, "identity", AsyncMock(return_value=identity))
    monkeypatch.setattr(repository, "organization_active", AsyncMock(return_value=True))
    monkeypatch.setattr(repository, "has_pending_inbound_events", AsyncMock(return_value=False))
    monkeypatch.setattr(repository, "user", AsyncMock(return_value=user))
    monkeypatch.setattr(repository, "conversation", AsyncMock(return_value=conversation))
    monkeypatch.setattr(
        repository,
        "match",
        AsyncMock(return_value=("MATCHED_CONTACT", "contact-a", None)),
    )
    customer_answer = AsyncMock(return_value="Invoice INV-7 outstanding: INR 10.00")
    monkeypatch.setattr(repository, "customer_answer", customer_answer)
    monkeypatch.setattr(
        worker.service,
        "permissions",
        AsyncMock(
            return_value={
                "ai:generate",
                "whatsapp:send",
                "whatsapp:read_all",
                "contacts:read",
                "invoices:read",
            }
        ),
    )
    provider = MagicMock()
    provider.send_text = AsyncMock(return_value="wamid.confirmed")
    monkeypatch.setattr(worker.service, "provider", AsyncMock(return_value=provider))
    monkeypatch.setattr(worker.service, "commit", AsyncMock())
    monkeypatch.setattr(worker.service, "audit", MagicMock())
    monkeypatch.setattr(worker, "enforce_rate_limit", AsyncMock())

    assert await worker.process_message(_factory(claim_db, process_db)) is True
    stub_phone_guard.assert_awaited_once_with(process_db, "org-a")

    customer_answer.assert_awaited_once()
    provider.send_text.assert_awaited_once_with(
        "2002", "+14155552671", "Invoice INV-7 outstanding: INR 10.00", "message-a"
    )
    assert message.status == "ACCEPTED"
    assert message.provider_message_id == "wamid.confirmed"


@pytest.mark.asyncio
async def test_ai_outbound_replays_persisted_contact_context_plan(monkeypatch):
    message, conversation, config, identity, user, claim_db, process_db = _outbound_fixture()
    message.ai_topic = "combined"
    message.ai_query_plan = {
        "topic": "combined",
        "sources": ["deal", "meeting"],
        "reference": None,
        "time_scope": "upcoming",
        "limit": 3,
    }
    repository = worker.service.repository
    monkeypatch.setattr(repository, "configuration", AsyncMock(return_value=config))
    monkeypatch.setattr(repository, "identity", AsyncMock(return_value=identity))
    monkeypatch.setattr(repository, "organization_active", AsyncMock(return_value=True))
    monkeypatch.setattr(repository, "has_pending_inbound_events", AsyncMock(return_value=False))
    monkeypatch.setattr(repository, "user", AsyncMock(return_value=user))
    monkeypatch.setattr(repository, "conversation", AsyncMock(return_value=conversation))
    monkeypatch.setattr(
        repository,
        "match",
        AsyncMock(return_value=("MATCHED_CONTACT", "contact-a", None)),
    )
    context_answer = AsyncMock(return_value="Your deal is active.\n\nYour meeting is tomorrow.")
    monkeypatch.setattr(
        "app.services.customer_crm_context_service.customer_crm_context_service.answer",
        context_answer,
    )
    monkeypatch.setattr(
        worker.service,
        "permissions",
        AsyncMock(
            return_value={
                "ai:generate",
                "whatsapp:send",
                "whatsapp:read_all",
                "contacts:read",
                "deals:read",
                "meetings:read",
            }
        ),
    )
    provider = MagicMock()
    provider.send_text = AsyncMock(return_value="wamid.confirmed")
    monkeypatch.setattr(worker.service, "provider", AsyncMock(return_value=provider))
    monkeypatch.setattr(worker.service, "commit", AsyncMock())
    monkeypatch.setattr(worker.service, "audit", MagicMock())
    monkeypatch.setattr(worker, "enforce_rate_limit", AsyncMock())

    assert await worker.process_message(_factory(claim_db, process_db)) is True

    plan = context_answer.await_args.args[-1]
    assert plan.topic == "combined"
    assert plan.sources == ["deal", "meeting"]
    provider.send_text.assert_awaited_once_with(
        "2002",
        "+14155552671",
        "Your deal is active.\n\nYour meeting is tomorrow.",
        "message-a",
    )


@pytest.mark.asyncio
async def test_ai_outbound_falls_back_safely_when_persisted_plan_is_invalid(monkeypatch):
    message, conversation, config, identity, user, claim_db, process_db = _outbound_fixture()
    message.ai_query_plan = {"topic": "invoice", "limit": 999}
    repository = worker.service.repository
    monkeypatch.setattr(repository, "configuration", AsyncMock(return_value=config))
    monkeypatch.setattr(repository, "identity", AsyncMock(return_value=identity))
    monkeypatch.setattr(repository, "organization_active", AsyncMock(return_value=True))
    monkeypatch.setattr(repository, "has_pending_inbound_events", AsyncMock(return_value=False))
    monkeypatch.setattr(repository, "user", AsyncMock(return_value=user))
    monkeypatch.setattr(repository, "conversation", AsyncMock(return_value=conversation))
    monkeypatch.setattr(
        repository,
        "match",
        AsyncMock(return_value=("MATCHED_CONTACT", "contact-a", None)),
    )
    context_answer = AsyncMock(return_value="Current invoice answer")
    monkeypatch.setattr(
        "app.services.customer_crm_context_service.customer_crm_context_service.answer",
        context_answer,
    )
    monkeypatch.setattr(
        worker.service,
        "permissions",
        AsyncMock(
            return_value={
                "ai:generate",
                "whatsapp:send",
                "whatsapp:read_all",
                "contacts:read",
                "invoices:read",
            }
        ),
    )
    provider = MagicMock()
    provider.send_text = AsyncMock(return_value="wamid.confirmed")
    monkeypatch.setattr(worker.service, "provider", AsyncMock(return_value=provider))
    monkeypatch.setattr(worker.service, "commit", AsyncMock())
    monkeypatch.setattr(worker.service, "audit", MagicMock())
    monkeypatch.setattr(worker, "enforce_rate_limit", AsyncMock())

    assert await worker.process_message(_factory(claim_db, process_db)) is True

    fallback_plan = context_answer.await_args.args[-1]
    assert fallback_plan.topic == "invoice"
    assert fallback_plan.limit == 3
    provider.send_text.assert_awaited_once_with(
        "2002", "+14155552671", "Current invoice answer", "message-a"
    )


@pytest.mark.asyncio
async def test_pre_send_rate_limit_is_retried_without_provider_call(monkeypatch):
    message, conversation, config, identity, user, claim_db, process_db = _outbound_fixture()
    repository = worker.service.repository
    monkeypatch.setattr(repository, "configuration", AsyncMock(return_value=config))
    monkeypatch.setattr(repository, "identity", AsyncMock(return_value=identity))
    monkeypatch.setattr(repository, "organization_active", AsyncMock(return_value=True))
    monkeypatch.setattr(repository, "has_pending_inbound_events", AsyncMock(return_value=False))
    monkeypatch.setattr(repository, "user", AsyncMock(return_value=user))
    monkeypatch.setattr(repository, "conversation", AsyncMock(return_value=conversation))
    monkeypatch.setattr(
        repository,
        "match",
        AsyncMock(return_value=("MATCHED_CONTACT", "contact-a", None)),
    )
    monkeypatch.setattr(repository, "customer_answer", AsyncMock(return_value="Current answer"))
    monkeypatch.setattr(
        worker.service,
        "permissions",
        AsyncMock(return_value={"ai:generate", "whatsapp:send", "whatsapp:read_all"}),
    )
    provider = AsyncMock()
    monkeypatch.setattr(worker.service, "provider", provider)
    monkeypatch.setattr(worker.service, "commit", AsyncMock())
    monkeypatch.setattr(worker.service, "notify", AsyncMock())
    monkeypatch.setattr(worker.service, "audit", MagicMock())
    monkeypatch.setattr(
        worker,
        "enforce_rate_limit",
        AsyncMock(
            side_effect=APIException(
                message="Temporarily throttled", code="WHATSAPP_RATE_LIMITED", status_code=429
            )
        ),
    )

    assert await worker.process_message(_factory(claim_db, process_db)) is True

    provider.assert_not_awaited()
    assert message.work_status == "PENDING"
    assert message.status == "PENDING"
    assert message.attempts == 1


@pytest.mark.asyncio
async def test_provider_rate_limit_uses_retry_after_without_marking_message_failed(monkeypatch):
    message, conversation, config, identity, user, claim_db, process_db = _outbound_fixture()
    repository = worker.service.repository
    monkeypatch.setattr(repository, "configuration", AsyncMock(return_value=config))
    monkeypatch.setattr(repository, "identity", AsyncMock(return_value=identity))
    monkeypatch.setattr(repository, "organization_active", AsyncMock(return_value=True))
    monkeypatch.setattr(repository, "has_pending_inbound_events", AsyncMock(return_value=False))
    monkeypatch.setattr(repository, "user", AsyncMock(return_value=user))
    monkeypatch.setattr(repository, "conversation", AsyncMock(return_value=conversation))
    monkeypatch.setattr(
        repository,
        "match",
        AsyncMock(return_value=("MATCHED_CONTACT", "contact-a", None)),
    )
    monkeypatch.setattr(repository, "customer_answer", AsyncMock(return_value="Current answer"))
    monkeypatch.setattr(
        worker.service,
        "permissions",
        AsyncMock(return_value={"ai:generate", "whatsapp:send", "whatsapp:read_all"}),
    )
    provider = MagicMock()
    provider.send_text = AsyncMock(
        side_effect=APIException(
            message="Provider throttled the request.",
            code="WHATSAPP_PROVIDER_RATE_LIMITED",
            fields={"retry_after_seconds": 90},
            status_code=503,
        )
    )
    monkeypatch.setattr(worker.service, "provider", AsyncMock(return_value=provider))
    monkeypatch.setattr(worker.service, "commit", AsyncMock())
    monkeypatch.setattr(worker.service, "notify", AsyncMock())
    monkeypatch.setattr(worker.service, "audit", MagicMock())
    monkeypatch.setattr(worker, "enforce_rate_limit", AsyncMock())
    started_at = datetime.now(UTC)
    scheduled_messages = []

    assert await worker.process_message(
        _factory(claim_db, process_db), scheduled_messages=scheduled_messages
    ) is True

    assert message.work_status == "PENDING"
    assert message.status == "PENDING"
    assert message.error_code == "WHATSAPP_PROVIDER_RATE_LIMITED"
    assert message.next_attempt_at >= started_at + worker.timedelta(seconds=90)
    assert scheduled_messages == [("message-a", "org-a", 90)]


@pytest.mark.asyncio
async def test_outbound_waits_without_consuming_retry_while_inbound_events_are_pending(
    monkeypatch,
):
    message, _conversation, config, identity, _user, claim_db, process_db = _outbound_fixture()
    repository = worker.service.repository
    monkeypatch.setattr(repository, "configuration", AsyncMock(return_value=config))
    monkeypatch.setattr(repository, "identity", AsyncMock(return_value=identity))
    monkeypatch.setattr(repository, "organization_active", AsyncMock(return_value=True))
    monkeypatch.setattr(repository, "has_pending_inbound_events", AsyncMock(return_value=True))
    provider = AsyncMock()
    monkeypatch.setattr(worker.service, "provider", provider)
    monkeypatch.setattr(worker.service, "commit", AsyncMock())

    scheduled_messages = []
    assert await worker.process_message(
        _factory(claim_db, process_db), scheduled_messages=scheduled_messages
    ) is True

    provider.assert_not_awaited()
    assert message.work_status == "PENDING"
    assert message.status == "PENDING"
    assert message.attempts == 0
    assert message.claimed_at is None
    assert scheduled_messages == [("message-a", "org-a", 30)]


@pytest.mark.asyncio
async def test_suspended_organization_is_blocked_before_provider_call(monkeypatch):
    message, conversation, config, identity, _user, claim_db, process_db = _outbound_fixture()
    repository = worker.service.repository
    monkeypatch.setattr(repository, "configuration", AsyncMock(return_value=config))
    monkeypatch.setattr(repository, "identity", AsyncMock(return_value=identity))
    monkeypatch.setattr(repository, "organization_active", AsyncMock(return_value=False))
    provider = AsyncMock()
    monkeypatch.setattr(worker.service, "provider", provider)
    monkeypatch.setattr(worker.service, "commit", AsyncMock())
    monkeypatch.setattr(worker.service, "notify", AsyncMock())
    monkeypatch.setattr(worker.service, "audit", MagicMock())

    assert await worker.process_message(_factory(claim_db, process_db)) is True

    provider.assert_not_awaited()
    assert message.status == "FAILED"
    assert message.error_code == "WHATSAPP_ORGANIZATION_INACTIVE"


@pytest.mark.asyncio
async def test_interrupted_inbound_retries_then_hands_off_when_exhausted(monkeypatch):
    retry = SimpleNamespace(
        id="inbound-retry",
        organization_id="org-a",
        conversation_id="conversation-a",
        direction="INBOUND",
        work_status="PROCESSING",
        attempts=1,
        claimed_at=datetime.now(UTC),
        next_attempt_at=datetime.now(UTC),
        error_code=None,
    )
    exhausted = SimpleNamespace(
        id="inbound-exhausted",
        organization_id="org-a",
        conversation_id="conversation-a",
        direction="INBOUND",
        work_status="PROCESSING",
        attempts=3,
        claimed_at=datetime.now(UTC),
        error_code=None,
    )
    conversation = SimpleNamespace(id="conversation-a", ai_enabled=True, status="OPEN")
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_Result([retry, exhausted]))
    db.scalar = AsyncMock(side_effect=[conversation, conversation])
    notify = AsyncMock()
    monkeypatch.setattr(worker.service, "notify", notify)
    monkeypatch.setattr(worker.service, "audit", MagicMock())
    monkeypatch.setattr(worker.service, "commit", AsyncMock())

    await worker.recover_interrupted(db)

    assert retry.work_status == "PENDING"
    assert retry.error_code == "AI_WORKER_INTERRUPTED_RETRY"
    assert exhausted.work_status == "FAILED"
    assert conversation.ai_enabled is False
    assert conversation.status == "HUMAN_HANDOFF"
    notify.assert_awaited_once()
