from typing import Any
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.models import User
from app.models.contact import Contact
from app.repositories.contact_repository import ContactRepository
from app.schemas.crm_schemas import ContactCreate, ContactUpdate
from app.services.contact_service import ContactService
from app.services.integration_service import integration_service


def _make_contact(**overrides) -> Contact:
    defaults = {
        "id": "cnt-1",
        "organization_id": "org-1",
        "name": "Jane Doe",
        "email": "jane@acme.com",
        "phone": "555-1234",
        "position": "Sales Rep",
        "company_id": None,
        "is_starred": False,
    }
    defaults.update(overrides)
    return Contact(**defaults)


def _make_user(**overrides) -> User:
    defaults = {
        "id": "usr-1",
        "name": "User One",
        "email": "user@crm.com",
        "organization_id": "org-1",
        "hashed_password": "x",
        "role": "Admin",
        "is_active": True,
    }
    defaults.update(overrides)
    return User(**defaults)


def _service_with(repo: ContactRepository) -> ContactService:
    return ContactService(repository=repo)


@pytest.mark.asyncio
async def test_get_contact_raises_not_found_when_missing():
    repo: Any = ContactRepository()
    repo.get_by_id = AsyncMock(return_value=None)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(NotFoundError):
        await service.get_contact(db, "missing-contact")


@pytest.mark.asyncio
async def test_create_contact_resolves_org_and_serializes(monkeypatch):
    contact = _make_contact()
    repo: Any = ContactRepository()
    repo.create = AsyncMock(return_value=contact)
    service = _service_with(repo)
    monkeypatch.setattr(integration_service, "notify_slack_event", AsyncMock())
    db = AsyncMock(spec=AsyncSession)

    from app.services.contact_service import organization_service

    monkeypatch.setattr(
        organization_service, "resolve_valid_org_id", AsyncMock(return_value="org-1")
    )

    payload = ContactCreate(name="Jane Doe", email="jane@acme.com")
    result = await service.create_contact(db, payload, _make_user())

    assert result["id"] == "cnt-1"
    assert result["first_name"] == "Jane"
    assert result["last_name"] == "Doe"
    assert result["email"] == "jane@acme.com"
    repo.create.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_contact_validates_and_persists_custom_fields(monkeypatch):
    contact = _make_contact(custom_fields={"preferred_channel": "Email"})
    repo: Any = ContactRepository()
    repo.create = AsyncMock(return_value=contact)
    custom_fields = AsyncMock()
    custom_fields.validate_values.return_value = {"preferred_channel": "Email"}
    service = ContactService(repository=repo, custom_field_service_instance=custom_fields)
    monkeypatch.setattr(integration_service, "notify_slack_event", AsyncMock())
    db = AsyncMock(spec=AsyncSession)

    from app.services.contact_service import organization_service

    monkeypatch.setattr(
        organization_service, "resolve_valid_org_id", AsyncMock(return_value="org-1")
    )

    result = await service.create_contact(
        db,
        ContactCreate(
            name="Jane Doe",
            email="jane@acme.com",
            custom_fields={"preferred_channel": "Email"},
        ),
        _make_user(),
    )

    assert repo.create.await_args.kwargs["data"]["custom_fields"] == {"preferred_channel": "Email"}
    assert result["custom_fields"] == {"preferred_channel": "Email"}


@pytest.mark.asyncio
async def test_create_contact_fires_contact_created_event(monkeypatch):
    contact = _make_contact()
    repo: Any = ContactRepository()
    repo.create = AsyncMock(return_value=contact)
    service = _service_with(repo)
    notify = AsyncMock()
    monkeypatch.setattr(integration_service, "notify_slack_event", notify)
    db = AsyncMock(spec=AsyncSession)

    from app.services.contact_service import organization_service

    monkeypatch.setattr(
        organization_service, "resolve_valid_org_id", AsyncMock(return_value="org-1")
    )

    await service.create_contact(
        db, ContactCreate(name="Jane Doe", email="jane@acme.com"), _make_user()
    )

    notify.assert_awaited_once()
    kwargs = notify.await_args_list[-1].kwargs
    assert kwargs["event_name"] == "contact.created"
    assert kwargs["org_id"] == "org-1"
    assert kwargs["data"]["email"] == "jane@acme.com"


@pytest.mark.asyncio
@pytest.mark.asyncio
async def test_update_contact_fires_contact_updated_event(monkeypatch):
    contact = _make_contact()
    repo: Any = ContactRepository()
    repo.get_by_id = AsyncMock(return_value=contact)
    service = _service_with(repo)
    notify = AsyncMock()
    monkeypatch.setattr(integration_service, "notify_slack_event", notify)
    db = AsyncMock(spec=AsyncSession)

    await service.update_contact(db, "cnt-1", ContactUpdate(email="jane@acme.io"))

    assert contact.email == "jane@acme.io"
    notify.assert_awaited_once()
    kwargs = notify.await_args_list[-1].kwargs
    assert kwargs["event_name"] == "contact.updated"
    assert kwargs["org_id"] == "org-1"
    assert kwargs["data"]["email"] == "jane@acme.io"


async def test_create_contact_defaults_name_from_email(monkeypatch):
    contact = _make_contact(name="jane", email="jane@acme.com")
    repo: Any = ContactRepository()
    repo.create = AsyncMock(return_value=contact)
    service = _service_with(repo)
    monkeypatch.setattr(integration_service, "notify_slack_event", AsyncMock())
    db = AsyncMock(spec=AsyncSession)

    from app.services.contact_service import organization_service

    monkeypatch.setattr(
        organization_service, "resolve_valid_org_id", AsyncMock(return_value="org-1")
    )

    result = await service.create_contact(db, ContactCreate(email="jane@acme.com"), _make_user())

    assert result["email"] == "jane@acme.com"
    repo.create.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_contact_merges_first_and_last_name():
    contact = _make_contact(name="Jane Doe")
    repo: Any = ContactRepository()
    repo.get_by_id = AsyncMock(return_value=contact)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.update_contact(
        db, "cnt-1", ContactUpdate(first_name="Jane", last_name="Smith")
    )

    assert contact.name == "Jane Smith"
    assert result["last_name"] == "Smith"


@pytest.mark.asyncio
async def test_set_starred_requires_existing_contact():
    repo: Any = ContactRepository()
    repo.get_by_id = AsyncMock(return_value=None)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(NotFoundError):
        await service.set_starred(db, "missing-contact", starred=True)
