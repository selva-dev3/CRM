from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.models import User
from app.models.note import Note
from app.repositories.note_repository import NoteRepository
from app.services.note_service import NoteService, note_to_dict


def _make_note(**overrides) -> Note:
    defaults = {
        "id": "note-1",
        "organization_id": "org-1",
        "entity_type": "lead",
        "entity_id": "lead-1",
        "content": "Hello",
        "is_pinned": False,
        "created_by": "usr-1",
    }
    defaults.update(overrides)
    return Note(**defaults)


def _service_with(repo: NoteRepository) -> NoteService:
    return NoteService(repository=repo)


def _user() -> User:
    return User(id="usr-1", email="user@crm.com", organization_id="org-1")


@pytest.fixture(autouse=True)
def _stub_organization_resolution(monkeypatch):
    monkeypatch.setattr(
        "app.services.note_service.organization_service.resolve_valid_org_id",
        AsyncMock(return_value="org-1"),
    )


def test_note_to_dict_applies_defaults():
    note = _make_note(entity_type=None, entity_id=None, created_by=None)
    result = note_to_dict(note)
    assert result["entity_type"] == "General"
    assert result["entity_id"] == "General"
    assert result["created_by"] == "Sales Admin"
    assert result["is_pinned"] is False


@pytest.mark.asyncio
async def test_get_note_raises_not_found_when_missing():
    repo: Any = NoteRepository()
    repo.get_by_id = AsyncMock(return_value=None)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(NotFoundError):
        await service.get_note(db, "missing-note", _user())
    repo.get_by_id.assert_awaited_once_with(db, "missing-note", "org-1")


def _db_with_no_users() -> AsyncMock:
    result_mock = MagicMock()
    result_mock.scalars.return_value.first.return_value = None
    db = AsyncMock(spec=AsyncSession)
    db.execute = AsyncMock(return_value=result_mock)
    return db


@pytest.mark.asyncio
async def test_create_note_resolves_org_and_serializes(monkeypatch):
    note = _make_note()
    repo: Any = NoteRepository()
    repo.create = AsyncMock(return_value=note)
    service = _service_with(repo)
    db = _db_with_no_users()

    from app.services.note_service import organization_service

    monkeypatch.setattr(
        organization_service, "resolve_valid_org_id", AsyncMock(return_value="org-1")
    )

    result = await service.create_note(
        db,
        entity_type="lead",
        entity_id="lead-1",
        content="Hello",
        current_user=_user(),
    )

    assert result["id"] == "note-1"
    assert result["entity_type"] == "lead"
    repo.create.assert_awaited_once()


@pytest.mark.asyncio
async def test_add_for_entity_uses_current_user_as_created_by(monkeypatch):
    note = _make_note(entity_type="contact", entity_id="cnt-1", created_by="usr-7")
    repo: Any = NoteRepository()
    repo.create = AsyncMock(return_value=note)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    from app.services.note_service import organization_service

    monkeypatch.setattr(
        organization_service, "resolve_valid_org_id", AsyncMock(return_value="org-1")
    )

    user = User(id="usr-7", email="a@b.com")
    result = await service.add_for_entity(
        db,
        entity_type="contact",
        entity_id="cnt-1",
        content="Hi",
        current_user=user,
    )

    assert result["entity_type"] == "contact"
    assert result["created_by"] == "usr-7"
