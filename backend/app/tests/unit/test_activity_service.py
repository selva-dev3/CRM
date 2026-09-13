from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.core.record_access import RecordAccessContext
from app.repositories.activity_repository import ActivityRepository
from app.services.activity_service import ActivityService
from app.services.auth_service import auth_service
from app.services.record_access_service import record_access_service


def _access(scope: str) -> RecordAccessContext:
    return RecordAccessContext(
        scope=scope,
        user_id="user-1",
        team_ids=frozenset({"team-1"}),
        team_user_ids=frozenset({"user-1", "user-2"}),
    )


@pytest.mark.asyncio
async def test_activity_service_filters_sources_by_existing_permissions(monkeypatch):
    repository = SimpleNamespace(list=AsyncMock(return_value=[]), count=AsyncMock(return_value=0))
    service = ActivityService(repository=repository)
    user = SimpleNamespace(id="user-1")
    monkeypatch.setattr(
        auth_service,
        "get_user_permissions",
        AsyncMock(
            return_value={
                "activities:read",
                "leads:read",
                "tasks:read",
                "whatsapp:read_assigned",
            }
        ),
    )
    monkeypatch.setattr(
        record_access_service, "resolve", AsyncMock(return_value=_access("assigned"))
    )
    db = AsyncMock()

    await service.list_activities(
        db,
        user,
        organization_id="org-selected",
        page=2,
        limit=25,
        module=None,
        search="follow up",
    )

    repository.list.assert_awaited_once_with(
        db,
        organization_id="org-selected",
        modules={"leads", "tasks", "whatsapp"},
        user_id="user-1",
        whatsapp_permissions={"whatsapp:read_assigned"},
        access=_access("assigned"),
        module_access={"leads": _access("assigned"), "tasks": _access("assigned")},
        search="follow up",
        page=2,
        limit=25,
    )


@pytest.mark.asyncio
async def test_activity_service_honors_api_key_scope(monkeypatch):
    repository = SimpleNamespace(list=AsyncMock(return_value=[]), count=AsyncMock(return_value=0))
    service = ActivityService(repository=repository)
    user = SimpleNamespace(id="user-1", _api_key_scopes={"leads:read"})
    monkeypatch.setattr(
        auth_service,
        "get_user_permissions",
        AsyncMock(return_value={"leads:read", "deals:read", "whatsapp:read_all"}),
    )

    modules, whatsapp_permissions = await service.allowed_modules(AsyncMock(), user)

    assert modules == {"leads"}
    assert whatsapp_permissions == set()


def test_activity_service_serializes_related_record_links():
    row = {
        "source_id": "note-1",
        "module": "notes",
        "action": "Note added",
        "description": "Decision maker confirmed",
        "entity_type": "company",
        "entity_id": "company-1",
        "actor_id": "user-1",
        "occurred_at": datetime(2026, 9, 12, tzinfo=UTC),
    }

    item = ActivityService.serialize(row)

    assert item["id"] == "notes:note-1"
    assert item["href"] == "/companies/company-1"


def test_activity_repository_only_builds_requested_sources():
    sources = ActivityRepository._sources(
        "org-1",
        {"leads", "calls"},
        user_id="user-1",
        whatsapp_permissions=set(),
        access=_access("all"),
        module_access={"leads": _access("all")},
    )

    assert len(sources) == 2
    sql = " ".join(str(source) for source in sources)
    assert "leads.organization_id" in sql
    assert "call_logs.organization_id" in sql


def test_activity_repository_applies_assigned_record_scope():
    sources = ActivityRepository._sources(
        "org-1",
        {"leads", "calls", "calendar"},
        user_id="user-1",
        whatsapp_permissions=set(),
        access=_access("assigned"),
        module_access={"leads": _access("assigned")},
    )

    sql = " ".join(str(source) for source in sources)
    assert "leads.assigned_to" in sql
    assert "call_logs.created_by" in sql
    assert "calendar_events.user_id" in sql


def test_activity_repository_authorizes_email_and_meeting_through_linked_records():
    sources = ActivityRepository._sources(
        "org-1",
        {"emails", "meetings"},
        user_id="user-1",
        whatsapp_permissions=set(),
        access=_access("assigned"),
        module_access={
            "leads": _access("assigned"),
            "contacts": _access("assigned"),
            "companies": _access("assigned"),
            "deals": _access("assigned"),
        },
    )

    sql = " ".join(str(source) for source in sources)
    assert "emails.lead_id" in sql
    assert "meetings.contact_id" in sql
    assert "leads.assigned_to" in sql
    assert "contacts.owner_id" in sql
    assert "companies.owner_id" in sql
    assert "deals.assigned_to" in sql
    assert " IS NULL" in sql
    assert " AND " in sql


def test_activity_scope_cannot_bypass_underlying_module_scope():
    sources = ActivityRepository._sources(
        "org-1",
        {"leads", "deals", "tasks"},
        user_id="user-1",
        whatsapp_permissions=set(),
        access=_access("all"),
        module_access={
            "leads": _access("none"),
            "deals": _access("none"),
            "tasks": _access("none"),
        },
    )

    sql = " ".join(str(source) for source in sources).lower()
    assert sql.count("false") >= 3


def test_linked_channel_scope_cannot_bypass_underlying_crm_scopes():
    sources = ActivityRepository._sources(
        "org-1",
        {"emails", "meetings"},
        user_id="user-1",
        whatsapp_permissions=set(),
        access=_access("all"),
        module_access={
            "leads": _access("none"),
            "contacts": _access("none"),
            "companies": _access("none"),
            "deals": _access("none"),
        },
    )

    sql = " ".join(str(source) for source in sources).lower()
    assert "false" in sql


def test_restricted_activity_scope_hides_unlinked_email_and_meeting_rows():
    restricted = ActivityRepository._sources(
        "org-1",
        {"emails", "meetings"},
        user_id="user-1",
        whatsapp_permissions=set(),
        access=_access("assigned"),
        module_access={
            "leads": _access("all"),
            "contacts": _access("all"),
            "companies": _access("all"),
            "deals": _access("all"),
        },
    )
    unrestricted = ActivityRepository._sources(
        "org-1",
        {"emails", "meetings"},
        user_id="user-1",
        whatsapp_permissions=set(),
        access=_access("all"),
        module_access={
            "leads": _access("all"),
            "contacts": _access("all"),
            "companies": _access("all"),
            "deals": _access("all"),
        },
    )

    restricted_sql = " ".join(str(source) for source in restricted).upper()
    unrestricted_sql = " ".join(str(source) for source in unrestricted).upper()
    assert "IS NOT NULL" in restricted_sql
    assert "IS NOT NULL" not in unrestricted_sql
