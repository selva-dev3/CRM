from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIException
from app.models import Email, EmailTemplate, User
from app.repositories.email_repository import EmailRepository
from app.schemas.crm_schemas import EmailSendRequest
from app.services.email_domain_service import (
    EmailDomainService,
    email_to_dict,
    template_to_dict,
)


def _make_email(**overrides) -> Email:
    defaults = {
        "id": "email-1",
        "organization_id": "org-1",
        "from_email": "rep@company.com",
        "to_email": "client@example.com",
        "subject": "Hello",
        "body_text": "Hi there",
        "status": "Sent",
        "sent_at": datetime(2026, 8, 5, 12, 0, tzinfo=UTC),
        "created_at": datetime(2026, 8, 5, 11, 59, tzinfo=UTC),
    }
    defaults.update(overrides)
    return Email(**defaults)


def _make_template(**overrides) -> EmailTemplate:
    defaults = {
        "id": "tmpl-1",
        "organization_id": "org-1",
        "name": "Cold Outreach",
        "subject": "Quick intro - {{company_name}}",
        "body_template": "Hi {{name}}",
        "category": "Sales Outreach",
    }
    defaults.update(overrides)
    return EmailTemplate(**defaults)


def _user() -> User:
    return User(id="user-1", email="user@crm.com", organization_id="org-1")


@pytest.fixture(autouse=True)
def _stub_organization_resolution(monkeypatch):
    monkeypatch.setattr(
        "app.services.email_domain_service.organization_service.resolve_valid_org_id",
        AsyncMock(return_value="org-1"),
    )


@pytest.mark.asyncio
async def test_get_inbox_maps_emails():
    repo: Any = EmailRepository()
    repo.list_emails = AsyncMock(return_value=[_make_email()])
    service = EmailDomainService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.get_inbox(
        db, page=1, limit=20, search="hi", current_user=_user()
    )

    assert result[0]["to"] == ["client@example.com"]
    assert result[0]["from_email"] == "rep@company.com"
    repo.list_emails.assert_awaited_once_with(
        db, page=1, limit=20, organization_id="org-1", search="hi"
    )


@pytest.mark.asyncio
async def test_send_email_queues_pending_row_when_provider_is_configured(monkeypatch):
    org_id = {"value": "org-1"}

    async def fake_resolve_valid_org_id(db, current_user):
        return org_id["value"]

    monkeypatch.setattr(
        "app.services.email_domain_service.organization_service.resolve_valid_org_id",
        fake_resolve_valid_org_id,
    )
    monkeypatch.setattr(
        "app.services.email_domain_service.settings.BREVO_API_KEY", "test-provider-key"
    )
    email = _make_email(status="Pending", sent_at=None)
    repo: Any = EmailRepository()
    repo.create_email = AsyncMock(return_value=email)
    service = EmailDomainService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.send_email(
        db,
        EmailSendRequest(to=["client@example.com"], subject="Hello", body="Hi"),
        _user(),
    )

    created = repo.create_email.await_args_list[-1].kwargs["data"]
    assert created["organization_id"] == "org-1"
    assert created["to_email"] == "client@example.com"
    assert created["status"] == "Pending"
    assert result["id"] == "email-1"
    assert result["status"] == "Pending"
    db.commit.assert_awaited_once()
    db.refresh.assert_awaited_once()


@pytest.mark.parametrize("field", ["subject", "body"])
def test_email_send_request_rejects_blank_content(field):
    payload = {"to": ["client@example.com"], "subject": "Hello", "body": "Hi there"}
    payload[field] = "   "

    with pytest.raises(ValidationError):
        EmailSendRequest(**payload)


@pytest.mark.asyncio
async def test_send_email_rejects_unconfigured_provider_without_creating_row(
    monkeypatch,
):
    monkeypatch.setattr("app.services.email_domain_service.settings.BREVO_API_KEY", None)
    repo: Any = EmailRepository()
    repo.create_email = AsyncMock()
    service = EmailDomainService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(APIException) as exc_info:
        await service.send_email(
            db,
            EmailSendRequest(to=["client@example.com"], subject="Hello", body="Hi"),
            _user(),
        )

    assert exc_info.value.status_code == 503
    assert exc_info.value.code == "EMAIL_PROVIDER_NOT_CONFIGURED"
    repo.create_email.assert_not_awaited()
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_list_templates_returns_empty_without_fabricated_defaults():
    repo: Any = EmailRepository()
    repo.list_templates = AsyncMock(return_value=[])
    service = EmailDomainService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    templates = await service.list_templates(db, _user())

    assert templates == []


@pytest.mark.asyncio
async def test_get_template_missing_raises_not_found():
    repo: Any = EmailRepository()
    repo.get_template = AsyncMock(return_value=None)
    service = EmailDomainService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(APIException) as exc_info:
        await service.get_template(db, "missing", _user())

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_update_template_persists_changes():
    template = _make_template()
    repo: Any = EmailRepository()
    repo.get_template = AsyncMock(return_value=template)
    service = EmailDomainService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.update_template(
        db,
        template_id="tmpl-1",
        name="New Name",
        subject="New Subject",
        body="New Body",
        current_user=_user(),
    )

    assert template.name == "New Name"
    assert template.subject == "New Subject"
    assert template.body_template == "New Body"
    assert result["status"] == "success"


@pytest.mark.asyncio
async def test_bulk_delete_returns_affected_count():
    repo: Any = EmailRepository()
    repo.list_by_ids = AsyncMock(return_value=[_make_email(), _make_email(id="email-2")])
    service = EmailDomainService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.bulk_delete(db, ["email-1", "email-2"], _user())

    assert result["affected_count"] == 2
    db.commit.assert_awaited_once()


def test_email_to_dict_uses_defaults():
    email = _make_email(to_email="x@y.com")
    result = email_to_dict(email)
    assert result["to"] == ["x@y.com"]
    assert result["body"] == "Hi there"


def test_template_to_dict_shape():
    result = template_to_dict(_make_template())
    assert result["category"] == "Sales Outreach"
    assert result["body"] == "Hi {{name}}"
