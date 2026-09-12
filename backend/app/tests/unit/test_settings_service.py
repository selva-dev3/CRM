from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIException, ForbiddenError
from app.models import User
from app.repositories.setting_repository import SettingRepository
from app.services.settings_service import SettingsService

TEST_HASH = "test-hash"


def _service_with(repo: SettingRepository) -> SettingsService:
    return SettingsService(repository=repo)


def _current_user() -> User:
    return User(
        id="user-1",
        name="Admin",
        email="admin@crm.com",
        hashed_password=TEST_HASH,
        role="Admin",
        organization_id="org-1",
    )


@pytest.mark.asyncio
async def test_get_system_settings_requires_authenticated_organization(monkeypatch):
    repo: Any = SettingRepository()
    repo.get_by_key = AsyncMock(return_value=None)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    from app.services.settings_service import organization_service

    monkeypatch.setattr(organization_service.repository, "get_by_id", AsyncMock(return_value=None))
    monkeypatch.setattr(organization_service.repository, "get_first", AsyncMock(return_value=None))

    with pytest.raises(ForbiddenError):
        await service.get_system_settings(db, None)


@pytest.mark.asyncio
async def test_get_system_settings_never_uses_another_organization(monkeypatch):
    repo: Any = SettingRepository()
    repo.get_by_key = AsyncMock(
        side_effect=lambda _db, key: (
            SimpleNamespace(value="EUR") if key == "system_currency" else None
        )
    )
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    from app.services.settings_service import organization_service

    monkeypatch.setattr(organization_service.repository, "get_first", AsyncMock(return_value=None))

    with pytest.raises(ForbiddenError):
        await service.get_system_settings(db, None)


@pytest.mark.asyncio
async def test_get_system_settings_uses_authenticated_organization_currency(monkeypatch):
    repo: Any = SettingRepository()
    repo.get_by_key = AsyncMock(return_value=None)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)
    org = SimpleNamespace(id="org-1", name="Acme", currency="INR")
    current_user = _current_user()

    from app.services.settings_service import organization_service

    monkeypatch.setattr(organization_service.repository, "get_by_id", AsyncMock(return_value=org))

    result = await service.get_system_settings(db, current_user)

    assert result["organization_name"] == "Acme"
    assert result["currency"] == "INR"


@pytest.mark.asyncio
async def test_get_system_settings_falls_back_for_invalid_organization_currency(monkeypatch):
    repo: Any = SettingRepository()
    repo.get_by_key = AsyncMock(return_value=None)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)
    org = SimpleNamespace(id="org-1", name="Acme", currency="US Dollar")
    current_user = _current_user()

    from app.services.settings_service import organization_service

    monkeypatch.setattr(organization_service.repository, "get_by_id", AsyncMock(return_value=org))

    result = await service.get_system_settings(db, current_user)

    assert result["currency"] == "INR"
    requested_keys = [call.args[1] for call in repo.get_by_key.await_args_list]
    assert "system_currency" not in requested_keys


@pytest.mark.asyncio
async def test_get_system_settings_does_not_use_bootstrap_currency_for_organization(monkeypatch):
    repo: Any = SettingRepository()
    repo.get_by_key = AsyncMock(return_value=SimpleNamespace(value="EUR"))
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)
    org = SimpleNamespace(id="org-1", name="Acme", currency=None)
    current_user = _current_user()

    from app.services.settings_service import organization_service

    monkeypatch.setattr(organization_service.repository, "get_by_id", AsyncMock(return_value=org))

    result = await service.get_system_settings(db, current_user)

    assert result["currency"] == "INR"
    requested_keys = [call.args[1] for call in repo.get_by_key.await_args_list]
    assert "system_currency" not in requested_keys


@pytest.mark.asyncio
async def test_get_system_settings_reports_database_read_failure(monkeypatch):
    repo: Any = SettingRepository()
    repo.get_by_key = AsyncMock(side_effect=SQLAlchemyError("database unavailable"))
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    from app.services.settings_service import organization_service

    monkeypatch.setattr(
        organization_service.repository,
        "get_by_id",
        AsyncMock(return_value=SimpleNamespace(id="org-1", name="Acme", currency="INR")),
    )

    with pytest.raises(APIException) as exc_info:
        await service.get_system_settings(db, _current_user())

    assert exc_info.value.status_code == 500
    assert exc_info.value.code == "SETTINGS_READ_FAILED"


@pytest.mark.asyncio
async def test_update_system_settings_persists_currency_on_organization(monkeypatch):
    repo: Any = SettingRepository()
    repo.upsert = AsyncMock()
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)
    org = SimpleNamespace(id="org-1", name="Acme", currency="USD")
    current_user = _current_user()

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
    db.commit.assert_awaited_once()
    assert all(call.kwargs.get("key") != "system_currency" for call in repo.upsert.await_args_list)


@pytest.mark.asyncio
async def test_update_system_settings_rejects_missing_organization_context(
    monkeypatch,
):
    repo: Any = SettingRepository()
    repo.upsert = AsyncMock()
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    from app.schemas.crm_schemas import SystemSettings
    from app.services.settings_service import organization_service

    monkeypatch.setattr(organization_service.repository, "get_first", AsyncMock(return_value=None))

    with pytest.raises(ForbiddenError):
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
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_system_settings_rolls_back_when_setting_upsert_fails(monkeypatch):
    repo: Any = SettingRepository()
    repo.upsert = AsyncMock(side_effect=RuntimeError("database unavailable"))
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    from app.schemas.crm_schemas import SystemSettings
    from app.services.settings_service import organization_service

    monkeypatch.setattr(
        organization_service.repository,
        "get_by_id",
        AsyncMock(return_value=SimpleNamespace(id="org-1", name="Acme", currency="INR")),
    )

    with pytest.raises(APIException) as exc_info:
        await service.update_system_settings(
            db,
            SystemSettings(organization_name="Acme CRM", currency="INR"),
            _current_user(),
        )

    assert exc_info.value.status_code == 500
    assert exc_info.value.code == "SETTINGS_UPDATE_FAILED"
    db.rollback.assert_awaited_once()
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_system_settings_rolls_back_when_commit_fails(monkeypatch):
    repo: Any = SettingRepository()
    repo.upsert = AsyncMock()
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)
    db.commit.side_effect = RuntimeError("commit failed")
    org = SimpleNamespace(id="org-1", name="Acme", currency="USD")
    current_user = _current_user()

    from app.schemas.crm_schemas import SystemSettings
    from app.services.settings_service import organization_service

    monkeypatch.setattr(organization_service.repository, "get_by_id", AsyncMock(return_value=org))

    with pytest.raises(APIException) as exc_info:
        await service.update_system_settings(
            db,
            SystemSettings(organization_name="Acme CRM", currency="INR"),
            current_user,
        )

    assert exc_info.value.status_code == 500
    assert exc_info.value.code == "SETTINGS_UPDATE_FAILED"
    db.rollback.assert_awaited_once()
    db.commit.assert_awaited_once()


@pytest.mark.parametrize("currency", ["$", "US Dollar", "   ", "USDX", "XYZ"])
def test_system_settings_rejects_invalid_currency(currency):
    from app.schemas.crm_schemas import OrganizationCreate, OrganizationUpdate, SystemSettings

    with pytest.raises(ValidationError):
        SystemSettings(organization_name="Acme", currency=currency)
    with pytest.raises(ValidationError):
        OrganizationCreate(name="Acme", currency=currency)
    with pytest.raises(ValidationError):
        OrganizationUpdate(currency=currency)


@pytest.mark.parametrize("currency", ["XCG", "USD", "INR"])
def test_system_settings_accepts_supported_currency(currency):
    from app.schemas.crm_schemas import SystemSettings

    result = SystemSettings(organization_name="Acme", currency=currency.lower())

    assert result.currency == currency


@pytest.mark.asyncio
async def test_reset_database_requires_confirmation():
    service = _service_with(SettingRepository())
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(APIException):
        await service.reset_database(db, confirm=False)


@pytest.mark.asyncio
async def test_reset_database_cannot_recreate_platform_identity():
    service = _service_with(SettingRepository())
    db = AsyncMock(spec=AsyncSession)
    with pytest.raises(APIException) as exc:
        await service.reset_database(db, confirm=True)
    assert exc.value.status_code == 501
    db.execute.assert_not_awaited()
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_custom_field_resolves_org(monkeypatch):
    repo: Any = SettingRepository()
    repo.create_custom_field = AsyncMock()
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    from app.services.settings_service import organization_service

    monkeypatch.setattr(
        organization_service, "resolve_valid_org_id", AsyncMock(return_value="org-1")
    )

    result = await service.create_custom_field(
        db,
        entity_type="Lead",
        field_name="priority",
        field_type="text",
        label="Priority",
        options=[],
        current_user=_current_user(),
    )

    assert result["status"] == "success"
    repo.create_custom_field.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_custom_field_normalizes_entity_type(monkeypatch):
    repo: Any = SettingRepository()
    repo.create_custom_field = AsyncMock()
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    from app.services.settings_service import organization_service

    monkeypatch.setattr(
        organization_service, "resolve_valid_org_id", AsyncMock(return_value="org-1")
    )

    await service.create_custom_field(
        db,
        entity_type=" lead ",
        field_name="priority",
        field_type="text",
        label="Priority",
        options=[],
        current_user=_current_user(),
    )

    assert repo.create_custom_field.await_args.kwargs["data"]["entity_type"] == "Lead"


@pytest.mark.asyncio
async def test_list_custom_fields_is_scoped_to_current_organization(monkeypatch):
    repo: Any = SettingRepository()
    repo.list_custom_fields = AsyncMock(return_value=[])
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    from app.services.settings_service import organization_service

    monkeypatch.setattr(
        organization_service, "resolve_valid_org_id", AsyncMock(return_value="org-1")
    )

    await service.list_custom_fields(db, "Deal", _current_user())

    repo.list_custom_fields.assert_awaited_once_with(
        db, organization_id="org-1", entity_type="Deal"
    )


@pytest.mark.asyncio
async def test_create_select_custom_field_requires_options(monkeypatch):
    repo: Any = SettingRepository()
    repo.create_custom_field = AsyncMock()
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    from app.services.settings_service import organization_service

    monkeypatch.setattr(
        organization_service, "resolve_valid_org_id", AsyncMock(return_value="org-1")
    )

    with pytest.raises(APIException) as exc_info:
        await service.create_custom_field(
            db,
            entity_type="Deal",
            field_name="segment",
            field_type="select",
            label="Segment",
            options=[],
            current_user=_current_user(),
        )

    assert exc_info.value.code == "CUSTOM_FIELD_OPTIONS_REQUIRED"
    repo.create_custom_field.assert_not_awaited()


def test_resolve_username_prefers_existing_user():
    assert SettingsService._resolve_username("Admin User", None, None) == "Admin User"
    assert SettingsService._resolve_username(None, "a1@crm.com", "usr-1") == "a1@crm.com"
    assert SettingsService._resolve_username(None, None, "actual-user-id") == "actual-user-id"
    assert SettingsService._resolve_username(None, None, None) == "Admin User"


@pytest.mark.asyncio
async def test_webhook_registration_persists_for_delivery_engine():
    repo: Any = SettingRepository()
    repo.create_webhook = AsyncMock()
    service = _service_with(repo)
    service._resolve_org_id = AsyncMock(return_value="org-1")
    db = AsyncMock(spec=AsyncSession)

    result = await service.create_webhook(
        db,
        target_url="https://example.test/events",
        events=["record.created"],
        current_user=_current_user(),
    )

    assert result["status"] == "success"
    repo.create_webhook.assert_awaited_once()
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_existing_webhook_reports_persisted_active_state():
    repo: Any = SettingRepository()
    repo.list_webhooks = AsyncMock(
        return_value=[
            SimpleNamespace(
                id="webhook-1",
                target_url="https://example.test/events",
                events="lead.created",
                is_active=True,
            )
        ]
    )
    service = _service_with(repo)
    service._resolve_org_id = AsyncMock(return_value="org-1")

    result = await service.list_webhooks(
        AsyncMock(spec=AsyncSession), _current_user()
    )

    assert result[0]["is_active"] is True


@pytest.mark.asyncio
async def test_webhook_test_connects_to_validated_ip_with_original_sni(monkeypatch):
    import asyncio
    import socket

    import httpx

    webhook = SimpleNamespace(
        id="webhook-1",
        target_url="https://hooks.example.test/events",
        timeout_seconds=5,
        secret=TEST_HASH,
        last_status_code=None,
        last_response=None,
        last_triggered_at=None,
        failure_count=0,
    )
    repo: Any = SettingRepository()
    repo.get_webhook = AsyncMock(return_value=webhook)
    service = _service_with(repo)
    service._resolve_org_id = AsyncMock(return_value="org-1")
    captured = {}

    monkeypatch.setattr(
        asyncio,
        "to_thread",
        AsyncMock(
            return_value=[
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443))
            ]
        ),
    )

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def post(self, url, **kwargs):
            captured["url"] = url
            captured.update(kwargs)
            return SimpleNamespace(status_code=204, text="", is_error=False)

    monkeypatch.setattr(httpx, "AsyncClient", lambda **_kwargs: FakeClient())
    result = await service.test_webhook(
        AsyncMock(spec=AsyncSession), "webhook-1", _current_user()
    )

    assert result["status"] == "success"
    assert captured["url"].host == "8.8.8.8"
    assert captured["headers"]["Host"] == "hooks.example.test"
    assert captured["extensions"]["sni_hostname"] == "hooks.example.test"
