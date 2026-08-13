from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIException
from app.repositories.setting_repository import SettingRepository
from app.services.settings_service import SettingsService


def _service_with(repo: SettingRepository) -> SettingsService:
    return SettingsService(repository=repo)


@pytest.mark.asyncio
async def test_get_system_settings_returns_defaults(monkeypatch):
    repo = SettingRepository()
    repo.get_by_key = AsyncMock(return_value=None)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    from app.services.settings_service import organization_service

    monkeypatch.setattr(organization_service.repository, "get_by_id", AsyncMock(return_value=None))
    monkeypatch.setattr(organization_service.repository, "get_first", AsyncMock(return_value=None))

    result = await service.get_system_settings(db, None)

    assert result["organization_name"] == "Enterprise Organization"
    assert result["currency"] == "USD"
    assert result["timezone"] == "UTC"
    assert result["smtp_enabled"] is True
    assert result["ai_features_enabled"] is True


@pytest.mark.asyncio
async def test_reset_database_requires_confirmation():
    service = _service_with(SettingRepository())
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(APIException):
        await service.reset_database(db, confirm=False)


@pytest.mark.asyncio
async def test_create_custom_field_resolves_org(monkeypatch):
    repo = SettingRepository()
    repo.create_custom_field = AsyncMock()
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    from app.services.settings_service import organization_service

    monkeypatch.setattr(
        organization_service, "resolve_valid_org_id", AsyncMock(return_value="org-1")
    )

    result = await service.create_custom_field(
        db, entity_type="Lead", field_name="priority", field_type="text", label="Priority"
    )

    assert result["status"] == "success"
    repo.create_custom_field.assert_awaited_once()


def test_resolve_username_prefers_existing_user():
    assert SettingsService._resolve_username("Admin User", None, None) == "Admin User"
    assert SettingsService._resolve_username(None, "a1@crm.com", "usr-1") == "a1@crm.com"
    assert SettingsService._resolve_username(None, None, "actual-user-id") == "actual-user-id"
    assert SettingsService._resolve_username(None, None, None) == "Admin User"