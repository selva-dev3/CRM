from typing import Any
from unittest.mock import ANY, AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.models import User
from app.models.note import Note
from app.repositories.note_repository import NoteRepository
from app.services.note_service import NoteService, note_to_dict
from app.tests.mock_helpers import as_async_mock, as_mock, replace_attr, require_await


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
    replace_attr(repo, "get_display_context", AsyncMock(return_value={}))
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
    assert result["entity_type"] == "general"
    assert result["entity_id"] is None
    assert result["entity_label"] is None
    assert result["created_by"] is None
    assert result["created_by_name"] is None
    assert result["is_pinned"] is False


def test_note_to_dict_resolves_entity_and_author_names_without_exposing_them_as_ids():
    note = _make_note(
        entity_type="Company",
        entity_id="company-1",
    )

    result = note_to_dict(
        note,
        {
            "company_name": "Acme Corp",
            "creator_name": "Ada Lovelace",
        },
    )

    assert result["entity_type"] == "company"
    assert result["entity_label"] == "Acme Corp"
    assert result["created_by"] == "usr-1"
    assert result["created_by_name"] == "Ada Lovelace"


@pytest.mark.asyncio
async def test_display_context_query_scopes_related_names_to_the_note_organization():
    result_mock = MagicMock()
    as_mock(result_mock.mappings.return_value.all).return_value = [
        {
            "id": "note-1",
            "lead_name": "Alex Morgan",
            "lead_title": "Renewal",
            "contact_name": None,
            "company_name": None,
            "deal_title": None,
            "creator_name": "Ada Lovelace",
            "creator_email": "ada@example.test",
        }
    ]
    db = AsyncMock(spec=AsyncSession)
    db.execute = AsyncMock(return_value=result_mock)

    context = await NoteRepository().get_display_context(db, [_make_note()], "org-1")

    assert context["note-1"]["lead_name"] == "Alex Morgan"
    assert context["note-1"]["creator_name"] == "Ada Lovelace"
    statement = str(require_await(db.execute).args[0])
    assert "leads.organization_id" in statement
    assert "contacts.organization_id" in statement
    assert "companies.organization_id" in statement
    assert "deals.organization_id" in statement
    assert "users.organization_id" in statement
    assert "users.is_platform_admin IS true" in statement


@pytest.mark.asyncio
async def test_repository_entity_queries_match_mixed_case_and_whitespace():
    result = MagicMock()
    as_mock(result.scalars.return_value.all).return_value = []
    as_mock(result.scalar_one).return_value = 0
    db = AsyncMock(spec=AsyncSession)
    db.execute = AsyncMock(return_value=result)
    repository = NoteRepository()

    await repository.list(
        db,
        page=1,
        limit=20,
        organization_id="org-1",
        entity_type=" cOnTaCt ",
    )
    await repository.count(
        db,
        organization_id="org-1",
        entity_type=" cOnTaCt ",
    )
    await repository.list_by_entity(
        db,
        organization_id="org-1",
        entity_type=" cOnTaCt ",
        entity_id="contact-1",
    )
    await repository.count_by_entity(
        db,
        organization_id="org-1",
        entity_type=" cOnTaCt ",
        entity_id="contact-1",
    )

    assert as_async_mock(db.execute).await_count == 4
    for call in as_async_mock(db.execute).await_args_list:
        statement = str(call.args[0].compile(compile_kwargs={"literal_binds": True})).lower()
        assert "lower(trim(notes.entity_type)) = 'contact'" in statement


@pytest.mark.asyncio
async def test_get_note_raises_not_found_when_missing():
    repo: Any = NoteRepository()
    repo.get_by_id = AsyncMock(return_value=None)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(NotFoundError):
        await service.get_note(db, "missing-note", _user())
    as_async_mock(repo.get_by_id).assert_awaited_once_with(
        db, "missing-note", "org-1", access=ANY, target_access=ANY
    )


@pytest.mark.asyncio
async def test_list_for_entity_normalizes_legacy_title_case():
    repo: Any = NoteRepository()
    repo.list_by_entity = AsyncMock(return_value=[])
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    await service.list_for_entity(
        db,
        entity_type="Company",
        entity_id="company-1",
        current_user=_user(),
    )

    as_async_mock(repo.list_by_entity).assert_awaited_once_with(
        db,
        entity_type="company",
        entity_id="company-1",
        organization_id="org-1",
        page=None,
        limit=None,
        access=ANY,
        target_access=ANY,
    )


def _db_with_no_users() -> AsyncMock:
    result_mock = MagicMock()
    as_mock(result_mock.scalars.return_value.first).return_value = None
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
    as_async_mock(repo.create).assert_awaited_once()


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

    user = User(id="usr-7", name="User Seven", email="a@b.com")
    result = await service.add_for_entity(
        db,
        entity_type="Contact",
        entity_id="cnt-1",
        content="Hi",
        current_user=user,
    )

    assert result["entity_type"] == "contact"
    assert result["created_by"] == "usr-7"
    as_async_mock(repo.create).assert_awaited_once_with(
        db,
        organization_id="org-1",
        entity_type="contact",
        entity_id="cnt-1",
        content="Hi",
        created_by="usr-7",
        relationships=ANY,
    )
