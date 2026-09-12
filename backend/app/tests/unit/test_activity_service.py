from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.repositories.activity_repository import ActivityRepository
from app.services.activity_service import ActivityService
from app.services.auth_service import auth_service


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
    )

    assert len(sources) == 2
    sql = " ".join(str(source) for source in sources)
    assert "leads.organization_id" in sql
    assert "call_logs.organization_id" in sql
