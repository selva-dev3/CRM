from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIException, NotFoundError
from app.models import CallLog, Contact, Lead, User
from app.repositories.call_repository import CallRepository
from app.repositories.contact_repository import ContactRepository
from app.schemas.crm_schemas import CallLogBase, CallLogUpdate
from app.services.call_service import CallService, _request_hash


def _make_call(**overrides) -> CallLog:
    defaults = {
        "id": "call-1",
        "organization_id": "org-1",
        "contact_id": "c-101",
        "call_type": "Outbound",
        "disposition": "Completed",
        "duration_seconds": 120,
        "subject": "Proposal review",
        "notes": "Discussed pricing",
        "follow_up_required": False,
        "created_by": "user-1",
        "timestamp": datetime(2026, 8, 1, tzinfo=UTC),
    }
    defaults.update(overrides)
    return CallLog(**defaults)


def _service_with(
    repo: CallRepository,
    ai_service: Any | None = None,
    contact_repository: ContactRepository | None = None,
) -> CallService:
    service = CallService(repository=repo, ai_service_instance=ai_service)
    if contact_repository is not None:
        service.contact_repository = contact_repository
    return service


def _user() -> User:
    return User(id="user-1", email="user@crm.com", organization_id="org-1")


@pytest.fixture(autouse=True)
def _stub_organization_resolution(monkeypatch):
    monkeypatch.setattr(
        "app.services.call_service.organization_service.resolve_valid_org_id",
        AsyncMock(return_value="org-1"),
    )


@pytest.mark.asyncio
async def test_get_call_raises_not_found_when_missing():
    repo: Any = CallRepository()
    repo.get_by_id = AsyncMock(return_value=None)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(NotFoundError):
        await service.get_call(db, "missing-call", _user())
    repo.get_by_id.assert_awaited_once_with(db, "missing-call", "org-1")


@pytest.mark.asyncio
async def test_log_call_resolves_org_and_serializes(monkeypatch):
    call = _make_call()
    repo: Any = CallRepository()
    repo.create = AsyncMock(return_value=call)
    repo.get_by_idempotency_key = AsyncMock(return_value=None)
    contact_repository: Any = ContactRepository()
    contact_repository.get_by_id_scoped = AsyncMock(
        return_value=Contact(id="c-101", organization_id="org-1", name="Contact")
    )
    service = _service_with(repo, contact_repository=contact_repository)
    db = AsyncMock(spec=AsyncSession)
    db.scalar.return_value = Contact(id="c-101", organization_id="org-1", name="Contact")

    from app.services.call_service import organization_service

    monkeypatch.setattr(
        organization_service, "resolve_valid_org_id", AsyncMock(return_value="org-1")
    )

    payload = CallLogBase(
        contact_id="c-101", call_type="Inbound", duration_seconds=90, notes="Call back"
    )
    result = await service.log_call(db, payload, _user())

    assert result["id"] == "call-1"
    assert result["call_type"] == "Outbound"
    assert result["notes"] == "Discussed pricing"
    repo.create.assert_awaited_once()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("call_type", "Sideways"),
        ("disposition", "Unknown outcome"),
        ("duration_seconds", -1),
        ("duration_seconds", 86401),
        ("duration_seconds", True),
        ("duration_seconds", "12"),
        ("notes", "x" * 10001),
    ],
)
def test_call_payload_rejects_invalid_values(field, value):
    with pytest.raises(ValidationError):
        CallLogBase(lead_id="lead-1", **{field: value})


def test_call_payload_requires_date_for_follow_up():
    with pytest.raises(ValidationError):
        CallLogBase(lead_id="lead-1", follow_up_required=True)


def test_call_payload_rejects_date_when_follow_up_is_disabled():
    with pytest.raises(ValidationError):
        CallLogBase(
            lead_id="lead-1",
            follow_up_required=False,
            follow_up_at=datetime(2026, 8, 2, tzinfo=UTC),
        )


@pytest.mark.asyncio
async def test_log_call_attributes_creator_and_all_validated_relationships():
    call = _make_call(lead_id="lead-1", contact_id=None)
    repo: Any = CallRepository()
    repo.create = AsyncMock(return_value=call)
    repo.get_by_idempotency_key = AsyncMock(return_value=None)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)
    db.scalar.return_value = Lead(id="lead-1", organization_id="org-1")
    payload = CallLogBase(
        lead_id="lead-1",
        disposition="No Answer",
        duration_seconds=0,
        subject="First outreach",
    )

    await service.log_call(db, payload, _user(), idempotency_key="request-1")

    data = repo.create.await_args.kwargs["data"]
    assert data["organization_id"] == "org-1"
    assert data["lead_id"] == "lead-1"
    assert data["created_by"] == "user-1"
    assert data["idempotency_key"] == "request-1"
    assert len(data["idempotency_request_hash"]) == 64


@pytest.mark.asyncio
async def test_log_call_returns_original_for_same_idempotent_request():
    payload = CallLogBase(lead_id="lead-1", notes="Same call")
    existing = _make_call(
        lead_id="lead-1",
        contact_id=None,
        notes="Same call",
        idempotency_key="request-1",
        idempotency_request_hash=_request_hash(payload),
    )
    repo: Any = CallRepository()
    repo.get_by_idempotency_key = AsyncMock(return_value=existing)
    repo.create = AsyncMock()
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)
    db.scalar.return_value = Lead(id="lead-1", organization_id="org-1")

    result = await service.log_call(db, payload, _user(), idempotency_key="request-1")

    assert result["id"] == "call-1"
    repo.create.assert_not_called()


@pytest.mark.asyncio
async def test_log_call_rejects_idempotency_key_with_different_payload():
    payload = CallLogBase(lead_id="lead-1", notes="Changed call")
    existing = _make_call(
        lead_id="lead-1",
        contact_id=None,
        idempotency_key="request-1",
        idempotency_request_hash="different-hash",
    )
    repo: Any = CallRepository()
    repo.get_by_idempotency_key = AsyncMock(return_value=existing)
    repo.create = AsyncMock()
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)
    db.scalar.return_value = Lead(id="lead-1", organization_id="org-1")

    with pytest.raises(APIException) as exc_info:
        await service.log_call(db, payload, _user(), idempotency_key="request-1")

    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "IDEMPOTENCY_KEY_REUSED"
    repo.create.assert_not_called()


@pytest.mark.asyncio
async def test_concurrent_idempotent_create_returns_committed_winner():
    payload = CallLogBase(lead_id="lead-1", notes="Concurrent call")
    winner = _make_call(
        id="call-winner",
        lead_id="lead-1",
        contact_id=None,
        notes="Concurrent call",
        idempotency_key="request-1",
        idempotency_request_hash=_request_hash(payload),
    )
    repo: Any = CallRepository()
    repo.get_by_idempotency_key = AsyncMock(side_effect=[None, winner])
    repo.create = AsyncMock(return_value=_make_call(lead_id="lead-1", contact_id=None))
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)
    db.scalar.return_value = Lead(id="lead-1", organization_id="org-1")
    db.commit.side_effect = IntegrityError("insert", {}, Exception("unique"))

    result = await service.log_call(db, payload, _user(), idempotency_key="request-1")

    assert result["id"] == "call-winner"
    db.rollback.assert_awaited_once()
    assert repo.get_by_idempotency_key.await_count == 2


@pytest.mark.asyncio
async def test_update_call_preserves_lead_and_organization_ownership():
    call = _make_call(lead_id="lead-1", contact_id=None)
    repo: Any = CallRepository()
    repo.get_by_id = AsyncMock(return_value=call)
    repo.update = AsyncMock(return_value=call)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)
    db.scalar.return_value = Lead(id="lead-1", organization_id="org-1")

    await service.update_call(db, "call-1", CallLogUpdate(notes="Updated"), _user())

    data = repo.update.await_args.kwargs["data"]
    assert data == {"notes": "Updated", "follow_up_at": None}
    assert call.lead_id == "lead-1"
    assert call.organization_id == "org-1"


@pytest.mark.asyncio
async def test_update_call_rejects_removing_the_last_relationship():
    call = _make_call(lead_id=None, contact_id="contact-1", company_id=None, deal_id=None)
    repo: Any = CallRepository()
    repo.get_by_id = AsyncMock(return_value=call)
    repo.update = AsyncMock()
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(APIException) as exc_info:
        await service.update_call(
            db,
            "call-1",
            CallLogUpdate(contact_id=None),
            _user(),
        )

    assert exc_info.value.status_code == 422
    assert exc_info.value.code == "CONTACT_REQUIRED"
    repo.update.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("relationship", ["contact_id", "company_id", "deal_id"])
async def test_update_call_rejects_cross_organization_relationship(relationship):
    call = _make_call(lead_id="lead-1", contact_id=None)
    repo: Any = CallRepository()
    repo.get_by_id = AsyncMock(return_value=call)
    repo.update = AsyncMock()
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)
    db.scalar.side_effect = [Lead(id="lead-1", organization_id="org-1"), None]

    with pytest.raises(NotFoundError):
        await service.update_call(
            db,
            "call-1",
            CallLogUpdate(**{relationship: "foreign-record"}),
            _user(),
        )

    repo.update.assert_not_called()


@pytest.mark.asyncio
async def test_update_call_rejects_cross_organization_call_id():
    repo: Any = CallRepository()
    repo.get_by_id = AsyncMock(return_value=None)
    repo.update = AsyncMock()
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(NotFoundError):
        await service.update_call(db, "foreign-call", CallLogUpdate(notes="Changed"), _user())

    repo.get_by_id.assert_awaited_once_with(db, "foreign-call", "org-1")
    repo.update.assert_not_called()


@pytest.mark.asyncio
async def test_delete_call_rejects_cross_organization_call_id():
    repo: Any = CallRepository()
    repo.get_by_id = AsyncMock(return_value=None)
    repo.delete = AsyncMock()
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(NotFoundError):
        await service.delete_call(db, "foreign-call", _user())

    repo.get_by_id.assert_awaited_once_with(db, "foreign-call", "org-1")
    repo.delete.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("relationship", ["lead_id", "contact_id", "company_id", "deal_id"])
async def test_log_call_rejects_cross_organization_relationship(relationship):
    repo: Any = CallRepository()
    repo.create = AsyncMock()
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)
    db.scalar.return_value = None

    with pytest.raises(NotFoundError):
        await service.log_call(
            db,
            CallLogBase(**{relationship: "foreign-record"}, notes="Call back"),
            _user(),
        )

    repo.create.assert_not_called()


@pytest.mark.asyncio
async def test_trigger_outbound_rejects_when_provider_is_not_configured():
    service = _service_with(CallRepository())
    with pytest.raises(APIException) as exc_info:
        await service.trigger_outbound("+1234567890", "c-101")

    assert exc_info.value.status_code == 503
    assert exc_info.value.code == "CALL_PROVIDER_NOT_CONFIGURED"


@pytest.mark.asyncio
async def test_voicemail_rejects_when_provider_is_not_configured():
    service = _service_with(CallRepository())
    with pytest.raises(APIException) as exc_info:
        await service.log_voicemail_drop("c-101", "template-1")

    assert exc_info.value.status_code == 503
    assert exc_info.value.code == "VOICEMAIL_PROVIDER_NOT_CONFIGURED"


@pytest.mark.asyncio
async def test_get_sentiment_requires_existing_call():
    repo: Any = CallRepository()
    repo.get_by_id = AsyncMock(return_value=None)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(NotFoundError):
        await service.get_sentiment(db, "missing-call", _user())


@pytest.mark.asyncio
async def test_get_sentiment_uses_real_ai_analysis_of_tenant_scoped_call_notes():
    repo: Any = CallRepository()
    repo.get_by_id = AsyncMock(return_value=_make_call(notes="Customer is unhappy with delay"))
    ai_service = AsyncMock()
    ai_service.analyze_sentiment.return_value = {
        "sentiment": "Negative",
        "confidence": 0.91,
        "reasons": ["Customer expressed dissatisfaction"],
        "urgency": "High",
        "escalation_required": True,
        "run_id": "run-1",
    }
    service = _service_with(repo, ai_service)
    db = AsyncMock(spec=AsyncSession)
    actor = _user()

    result = await service.get_sentiment(db, "call-1", actor)

    ai_service.analyze_sentiment.assert_awaited_once_with(
        db, "Customer is unhappy with delay", actor
    )
    assert result["overall_sentiment"] == "Negative"
    assert result["run_id"] == "run-1"
