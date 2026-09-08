from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.models import User
from app.models.contact import Contact, ContactAddress
from app.models.deal import Deal
from app.repositories.contact_repository import ContactRepository
from app.schemas.crm_schemas import ContactAddressUpdate, ContactCreate, ContactUpdate
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
    if "lock_organization" not in repo.__dict__:
        repo.lock_organization = AsyncMock()
    if "find_duplicate" not in repo.__dict__:
        repo.find_duplicate = AsyncMock(return_value=None)
    return ContactService(repository=repo)


@pytest.mark.asyncio
async def test_count_contacts_is_scoped_to_current_organization(monkeypatch):
    repo: Any = ContactRepository()
    repo.count_by_org = AsyncMock(return_value=19)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    from app.services.contact_service import organization_service

    monkeypatch.setattr(
        organization_service, "resolve_valid_org_id", AsyncMock(return_value="org-1")
    )

    result = await service.count_contacts(db, search="Jane", current_user=_make_user())

    assert result == 19
    repo.count_by_org.assert_awaited_once_with(db, organization_id="org-1", search="Jane")


@pytest.mark.asyncio
async def test_get_contact_raises_not_found_when_missing():
    repo: Any = ContactRepository()
    repo.get_by_id_scoped = AsyncMock(return_value=None)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(NotFoundError):
        await service.get_contact(db, "missing-contact", organization_id="org-1")


@pytest.mark.asyncio
async def test_get_billing_address_is_scoped_to_contact_and_organization():
    repo: Any = ContactRepository()
    repo.get_by_id_scoped = AsyncMock(return_value=_make_contact())
    repo.get_address = AsyncMock(
        return_value=ContactAddress(
            contact_id="cnt-1", street="123 Main Street", country="IN"
        )
    )
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.get_billing_address(db, "cnt-1", organization_id="org-1")

    assert result.street == "123 Main Street"
    assert result.country == "IN"
    repo.get_address.assert_awaited_once_with(
        db, contact_id="cnt-1", organization_id="org-1"
    )


@pytest.mark.asyncio
async def test_update_billing_address_creates_missing_address():
    repo: Any = ContactRepository()
    repo.get_by_id_scoped = AsyncMock(return_value=_make_contact())
    repo.get_address = AsyncMock(return_value=None)
    address = ContactAddress(
        contact_id="cnt-1", street="123 Main Street", country="IN"
    )
    repo.create_address = AsyncMock(return_value=address)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.update_billing_address(
        db,
        "cnt-1",
        ContactAddressUpdate(street="123 Main Street", country="IN"),
        organization_id="org-1",
    )

    assert result.street == "123 Main Street"
    assert result.country == "IN"
    repo.create_address.assert_awaited_once_with(
        db,
        contact_id="cnt-1",
        data={
            "street": "123 Main Street",
            "city": None,
            "state": None,
            "country": "IN",
            "postal_code": None,
        },
    )


@pytest.mark.asyncio
async def test_list_contact_activities_combines_existing_related_records(monkeypatch):
    repo: Any = ContactRepository()
    repo.get_by_id_scoped = AsyncMock(return_value=_make_contact())
    service = _service_with(repo)
    service.note_repository.list_by_entity = AsyncMock(
        return_value=[SimpleNamespace(id="note-1", content="Followed up", created_at="2026-01-02")]
    )
    service.call_repository.list_by_contact = AsyncMock(return_value=[])
    service.deal_repository.list_activities_by_contact = AsyncMock(
        return_value=[SimpleNamespace(id="deal-activity-1", action="Deal won", timestamp="2026-01-01")]
    )
    db = AsyncMock(spec=AsyncSession)
    monkeypatch.setattr(
        "app.services.auth_service.auth_service.get_user_permissions",
        AsyncMock(return_value=["calls:read"]),
    )
    actor = _make_user()
    actor.__dict__["_api_key_scopes"] = {"calls:read"}

    result = await service.list_contact_activities(
        db,
        "cnt-1",
        organization_id="org-1",
        current_user=actor,
    )

    assert [item.type for item in result] == ["Note", "Deal Activity"]
    assert result[0].description == "Followed up"
    service.note_repository.list_by_entity.assert_awaited_once_with(
        db, entity_type="contact", entity_id="cnt-1", organization_id="org-1"
    )
    service.call_repository.list_by_contact.assert_awaited_once_with(
        db, contact_id="cnt-1", organization_id="org-1"
    )


@pytest.mark.asyncio
async def test_list_contact_activities_omits_calls_without_effective_permission(monkeypatch):
    repo: Any = ContactRepository()
    repo.get_by_id_scoped = AsyncMock(return_value=_make_contact())
    service = _service_with(repo)
    service.note_repository.list_by_entity = AsyncMock(return_value=[])
    service.call_repository.list_by_contact = AsyncMock(
        return_value=[
            SimpleNamespace(
                id="call-1",
                call_type="Outbound",
                notes="Sensitive call notes",
                timestamp="2026-01-02",
            )
        ]
    )
    service.deal_repository.list_activities_by_contact = AsyncMock(return_value=[])
    monkeypatch.setattr(
        "app.services.auth_service.auth_service.get_user_permissions",
        AsyncMock(return_value=["contacts:read", "calls:read"]),
    )
    actor = _make_user()
    actor.__dict__["_api_key_scopes"] = {"contacts:read"}

    result = await service.list_contact_activities(
        AsyncMock(spec=AsyncSession),
        "cnt-1",
        organization_id="org-1",
        current_user=actor,
    )

    assert result == []
    service.call_repository.list_by_contact.assert_not_awaited()


@pytest.mark.asyncio
async def test_list_contact_emails_matches_contact_recipient():
    repo: Any = ContactRepository()
    repo.get_by_id_scoped = AsyncMock(return_value=_make_contact())
    service = _service_with(repo)
    service.email_repository.list_by_recipient = AsyncMock(
        return_value=[
            SimpleNamespace(
                id="email-1",
                from_email="rep@example.com",
                to_email="jane@acme.com",
                subject="Follow-up",
                body_text="Checking in",
                sent_at="2026-01-02",
            )
        ]
    )
    db = AsyncMock(spec=AsyncSession)

    result = await service.list_contact_emails(db, "cnt-1", organization_id="org-1")

    assert result[0].subject == "Follow-up"
    assert result[0].body == "Checking in"
    service.email_repository.list_by_recipient.assert_awaited_once_with(
        db, organization_id="org-1", recipient_email="jane@acme.com"
    )


@pytest.mark.asyncio
async def test_list_contact_deals_is_scoped_and_serialized():
    repo: Any = ContactRepository()
    repo.get_by_id_scoped = AsyncMock(return_value=_make_contact())
    service = _service_with(repo)
    service.deal_repository.list_by_contact = AsyncMock(
        return_value=[Deal(id="deal-1", organization_id="org-1", title="Renewal")]
    )
    db = AsyncMock(spec=AsyncSession)

    result = await service.list_contact_deals(db, "cnt-1", organization_id="org-1")

    assert result[0]["id"] == "deal-1"
    service.deal_repository.list_by_contact.assert_awaited_once_with(
        db, contact_id="cnt-1", organization_id="org-1"
    )


@pytest.mark.asyncio
async def test_create_contact_resolves_org_and_serializes(monkeypatch):
    contact = _make_contact()
    repo: Any = ContactRepository()
    repo.create = AsyncMock(return_value=contact)
    repo.lock_organization = AsyncMock()
    repo.find_duplicate = AsyncMock(return_value=None)
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
    repo.lock_organization = AsyncMock()
    repo.find_duplicate = AsyncMock(return_value=None)
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

    custom_fields.validate_values.assert_awaited_once_with(
        db,
        organization_id="org-1",
        entity_type="Contact",
        values={"preferred_channel": "Email"},
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
async def test_update_contact_fires_contact_updated_event(monkeypatch):
    contact = _make_contact()
    repo: Any = ContactRepository()
    repo.get_by_id_scoped = AsyncMock(return_value=contact)
    service = _service_with(repo)
    notify = AsyncMock()
    monkeypatch.setattr(integration_service, "notify_slack_event", notify)
    db = AsyncMock(spec=AsyncSession)

    await service.update_contact(
        db,
        "cnt-1",
        ContactUpdate(email="jane@acme.io"),
        organization_id="org-1",
    )

    assert contact.email == "jane@acme.io"
    notify.assert_awaited_once()
    kwargs = notify.await_args_list[-1].kwargs
    assert kwargs["event_name"] == "contact.updated"
    assert kwargs["org_id"] == "org-1"
    assert kwargs["data"]["email"] == "jane@acme.io"


@pytest.mark.asyncio
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
    repo.get_by_id_scoped = AsyncMock(return_value=contact)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.update_contact(
        db,
        "cnt-1",
        ContactUpdate(first_name="Jane", last_name="Smith"),
        organization_id="org-1",
    )

    assert contact.name == "Jane Smith"
    assert result["last_name"] == "Smith"


@pytest.mark.asyncio
async def test_set_starred_requires_existing_contact():
    repo: Any = ContactRepository()
    repo.get_by_id_scoped = AsyncMock(return_value=None)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(NotFoundError):
        await service.set_starred(
            db,
            "missing-contact",
            starred=True,
            organization_id="org-1",
        )
