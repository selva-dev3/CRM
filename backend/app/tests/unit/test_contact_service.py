from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.models import User
from app.models.contact import Contact
from app.repositories.contact_repository import ContactRepository
from app.schemas.crm_schemas import ContactCreate, ContactUpdate
from app.services.contact_service import ContactService


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
    repo = ContactRepository()
    repo.get_by_id = AsyncMock(return_value=None)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(NotFoundError):
        await service.get_contact(db, "missing-contact")


@pytest.mark.asyncio
async def test_create_contact_resolves_org_and_serializes(monkeypatch):
    contact = _make_contact()
    repo = ContactRepository()
    repo.create = AsyncMock(return_value=contact)
    service = _service_with(repo)
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
async def test_create_contact_defaults_name_from_email(monkeypatch):
    contact = _make_contact(name="jane", email="jane@acme.com")
    repo = ContactRepository()
    repo.create = AsyncMock(return_value=contact)
    service = _service_with(repo)
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
    repo = ContactRepository()
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
    repo = ContactRepository()
    repo.get_by_id = AsyncMock(return_value=None)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(NotFoundError):
        await service.set_starred(db, "missing-contact", starred=True)