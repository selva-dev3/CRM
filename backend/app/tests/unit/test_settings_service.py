from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError
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
async def test_get_system_settings_uses_stored_currency_without_organization(monkeypatch):
    repo = SettingRepository()
    repo.get_by_key = AsyncMock(
        side_effect=lambda _db, key: SimpleNamespace(value="EUR")
        if key == "system_currency"
        else None
    )
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    from app.services.settings_service import organization_service

    monkeypatch.setattr(organization_service.repository, "get_first", AsyncMock(return_value=None))

    result = await service.get_system_settings(db, None)

    assert result["currency"] == "EUR"


@pytest.mark.asyncio
async def test_get_system_settings_uses_authenticated_organization_currency(monkeypatch):
    repo = SettingRepository()
    repo.get_by_key = AsyncMock(return_value=None)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)
    org = SimpleNamespace(name="Acme", currency="INR")
    current_user = SimpleNamespace(organization_id="org-1")

    from app.services.settings_service import organization_service

    monkeypatch.setattr(organization_service.repository, "get_by_id", AsyncMock(return_value=org))

    result = await service.get_system_settings(db, current_user)

    assert result["organization_name"] == "Acme"
    assert result["currency"] == "INR"


@pytest.mark.asyncio
async def test_get_system_settings_falls_back_for_invalid_organization_currency(monkeypatch):
    repo = SettingRepository()
    repo.get_by_key = AsyncMock(return_value=None)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)
    org = SimpleNamespace(name="Acme", currency="US Dollar")
    current_user = SimpleNamespace(organization_id="org-1")

    from app.services.settings_service import organization_service

    monkeypatch.setattr(organization_service.repository, "get_by_id", AsyncMock(return_value=org))

    result = await service.get_system_settings(db, current_user)

    assert result["currency"] == "INR"


@pytest.mark.asyncio
async def test_update_system_settings_persists_currency_on_organization(monkeypatch):
    repo = SettingRepository()
    repo.upsert = AsyncMock()
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)
    org = SimpleNamespace(name="Acme", currency="USD")
    current_user = SimpleNamespace(organization_id="org-1")

    from app.services.settings_service import organization_service

    monkeypatch.setattr(organization_service.repository, "get_by_id", AsyncMock(return_value=org))

    from app.schemas.crm_schemas import SystemSettings

    await service.update_system_settings(
        db,
        SystemSettings(
            organization_name="Acme CRM",
            currency="inr",
            timezone="UTC",
            smtp_enabled=True,
            ai_features_enabled=True,
        ),
        current_user,
    )

    assert org.name == "Acme CRM"
    assert org.currency == "INR"
    db.commit.assert_awaited()
    assert all(call.kwargs.get("key") != "system_currency" for call in repo.upsert.await_args_list)


@pytest.mark.asyncio
async def test_update_system_settings_persists_currency_without_organization(
    monkeypatch,
):
    repo = SettingRepository()
    repo.upsert = AsyncMock()
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    from app.schemas.crm_schemas import SystemSettings
    from app.services.settings_service import organization_service

    monkeypatch.setattr(organization_service.repository, "get_first", AsyncMock(return_value=None))

    await service.update_system_settings(
        db,
        SystemSettings(
            organization_name="Acme CRM",
            currency="INR",
            timezone="UTC",
            smtp_enabled=True,
            ai_features_enabled=True,
        ),
        None,
    )

    repo.upsert.assert_any_await(db, key="system_currency", value="INR")


@pytest.mark.parametrize("currency", ["$", "US Dollar", "   ", "USDX", "XYZ"])
def test_system_settings_rejects_invalid_currency(currency):
    from app.schemas.crm_schemas import OrganizationCreate, OrganizationUpdate, SystemSettings

    with pytest.raises(ValidationError):
        SystemSettings(organization_name="Acme", currency=currency)
    with pytest.raises(ValidationError):
        OrganizationCreate(name="Acme", currency=currency)
    with pytest.raises(ValidationError):
        OrganizationUpdate(currency=currency)


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
