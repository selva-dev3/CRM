"""WhatsApp persistence and tenant boundaries against disposable PostgreSQL."""

import asyncio
import os
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import select, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.errors import APIException, ConflictError, NotFoundError
from app.models import Contact, Integration, Lead, Organization, User
from app.models.whatsapp import (
    WhatsAppContactIdentity,
    WhatsAppIntegration,
    WhatsAppMessage,
    WhatsAppTemplate,
    WhatsAppWebhookEvent,
)
from app.repositories.whatsapp_repository import WhatsAppRepository
from app.schemas.crm_schemas import ContactCreate, ContactUpdate, LeadConvertRequest, LeadUpdate
from app.schemas.whatsapp import InboundEvent, IntegrationWrite, StatusEvent
from app.services.contact_service import ContactService
from app.services.lead_service import LeadService
from app.services.whatsapp_service import WhatsAppService

UNUSED_PASSWORD_HASH = "unused-test-hash"  # noqa: S105 - no authentication occurs


@pytest.mark.asyncio
async def test_tenant_matching_idempotency_and_status_flow(monkeypatch):
    root_url = os.getenv("CRM_WORKFLOW_TEST_DATABASE_URL")
    if not root_url:
        pytest.skip("An isolated PostgreSQL workflow database is required")
    parsed = make_url(root_url)
    assert parsed.host in {"localhost", "127.0.0.1"}
    assert parsed.database == "crm_workflow_test"
    database = f"whatsapp_test_{uuid4().hex}"
    root = create_async_engine(root_url, isolation_level="AUTOCOMMIT")
    async with root.connect() as connection:
        await connection.execute(text(f'CREATE DATABASE "{database}"'))
    isolated_url = parsed.set(database=database).render_as_string(hide_password=False)
    engine = create_async_engine(isolated_url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(settings, "DATABASE_URL", isolated_url)
    config = Config()
    config.set_main_option("script_location", str(Path(__file__).resolve().parents[3] / "alembic"))
    repository = WhatsAppRepository()
    now = datetime.now(UTC)
    try:
        await asyncio.to_thread(command.upgrade, config, "head")
        async with sessions() as db:
            db.add_all(
                [
                    Organization(id="org-a", name="WhatsApp Tenant A"),
                    Organization(id="org-b", name="WhatsApp Tenant B"),
                ]
            )
            await db.flush()
            db.add_all(
                [
                    User(
                        id="user-a",
                        name="Agent A",
                        email="wa-agent-a@example.test",
                        hashed_password=UNUSED_PASSWORD_HASH,
                        organization_id="org-a",
                        is_active=True,
                    ),
                    User(
                        id="user-b",
                        name="Agent B",
                        email="wa-agent-b@example.test",
                        hashed_password=UNUSED_PASSWORD_HASH,
                        organization_id="org-b",
                        is_active=True,
                    ),
                ]
            )
            await db.flush()
            catalogs = [
                Integration(
                    id="catalog-a",
                    organization_id="org-a",
                    name="WhatsApp",
                    provider="whatsapp",
                ),
                Integration(
                    id="catalog-b",
                    organization_id="org-b",
                    name="WhatsApp",
                    provider="whatsapp",
                ),
            ]
            db.add_all(catalogs)
            await db.flush()
            configs = [
                WhatsAppIntegration(
                    id="wa-a",
                    organization_id="org-a",
                    catalog_integration_id="catalog-a",
                    business_account_id="1001",
                    phone_number_id="2001",
                    api_version="v23.0",
                    enabled=True,
                    phone_index_ready=True,
                    default_assignee_id="user-a",
                ),
                WhatsAppIntegration(
                    id="wa-b",
                    organization_id="org-b",
                    catalog_integration_id="catalog-b",
                    business_account_id="1002",
                    phone_number_id="2002",
                    api_version="v23.0",
                    enabled=True,
                    phone_index_ready=True,
                    default_assignee_id="user-b",
                ),
            ]
            db.add_all(configs)
            db.add(
                Contact(
                    id="contact-b",
                    organization_id="org-b",
                    name="Foreign Customer",
                    email="foreign-customer@example.test",
                    phone="+14155552671",
                    normalized_phone="+14155552671",
                    whatsapp_phone_verified_at=now,
                )
            )
            await db.flush()
            contact_b = await db.get(Contact, "contact-b")
            assert contact_b is not None
            await repository.prepare_crm_phone(db, "org-b", contact_b)
            contact_b.whatsapp_phone_verified_at = now
            await db.execute(
                text("UPDATE whatsapp_integrations SET phone_index_ready=true WHERE id='wa-b'")
            )
            await db.commit()

        monkeypatch.setattr(settings, "WHATSAPP_ENABLED", True)
        monkeypatch.setattr(settings, "WHATSAPP_API_VERSION", "v23.0")
        monkeypatch.setattr(settings, "WHATSAPP_APP_ID", "meta-app")
        monkeypatch.setattr("app.services.whatsapp_service.enforce_rate_limit", AsyncMock())
        monkeypatch.setattr(
            "app.services.whatsapp_service.IntegrationService._encrypt_secret",
            lambda value: "enc:v1:synthetic",
        )

        async def configure_for(
            organization_id: str, user_id: str, business_id: str, phone_id: str
        ):
            service = WhatsAppService()
            service.permissions = AsyncMock(return_value={"integrations:manage"})
            service.status = AsyncMock(return_value="configured")
            payload = IntegrationWrite(
                business_account_id=business_id,
                phone_number_id=phone_id,
                access_token="synthetic-integration-token",  # noqa: S106
                api_version="v23.0",
                default_phone_region="US",
                default_assignee_id=user_id,
            )
            async with sessions() as db:
                return await service.configure(
                    db,
                    type(
                        "IntegrationUser",
                        (),
                        {"id": user_id, "organization_id": organization_id},
                    )(),
                    payload,
                )

        async with sessions() as db:
            config_a = await repository.configuration(db, "org-a", lock=True)
            config_b = await repository.configuration(db, "org-b", lock=True)
            assert config_a is not None and config_b is not None
            config_a.enabled = False
            config_b.enabled = False
            await db.commit()

        with pytest.raises(ConflictError) as existing_collision:
            await configure_for("org-a", "user-a", "1001", "2002")
        assert existing_collision.value.code == "WHATSAPP_PHONE_ALREADY_CONNECTED"

        concurrent_results = await asyncio.gather(
            configure_for("org-a", "user-a", "1001", "3003"),
            configure_for("org-b", "user-b", "1002", "3003"),
            return_exceptions=True,
        )
        assert sum(result == "configured" for result in concurrent_results) == 1, (
            concurrent_results
        )
        conflicts = [result for result in concurrent_results if isinstance(result, ConflictError)]
        assert len(conflicts) == 1
        assert conflicts[0].code == "WHATSAPP_PHONE_ALREADY_CONNECTED"

        async with sessions() as db:
            config_a = await repository.configuration(db, "org-a", lock=True)
            config_b = await repository.configuration(db, "org-b", lock=True)
            assert config_a is not None and config_b is not None
            config_a.business_account_id = "1001"
            config_a.phone_number_id = "2001"
            config_a.enabled = True
            config_b.business_account_id = "1002"
            config_b.phone_number_id = "2002"
            config_b.enabled = True
            await db.commit()

        async def assert_stale_provider_result_rejected(operation: str) -> None:
            remote_complete = asyncio.Event()
            correction_complete = asyncio.Event()
            client = AsyncMock()

            async def provider_request(method, path, **kwargs):
                if operation == "verify" and path.endswith("/phone_numbers"):
                    return {
                        "data": [
                            {
                                "id": "2001",
                                "display_phone_number": "+1 415-555-2671",
                                "verified_name": "Old Account",
                            }
                        ]
                    }
                remote_complete.set()
                await correction_complete.wait()
                if operation == "verify":
                    return {"data": [{"id": "meta-app"}]}
                return {"data": [{"id": "old-account-template"}]}

            client.request = AsyncMock(side_effect=provider_request)
            service = WhatsAppService()
            service.permissions = AsyncMock(
                return_value={"integrations:manage", "whatsapp:read_assigned"}
            )
            service.provider = AsyncMock(return_value=client)
            user = type(
                "IntegrationUser",
                (),
                {"id": "user-a", "organization_id": "org-a", "is_active": True},
            )()
            async with sessions() as operation_db:
                operation_task = asyncio.create_task(
                    getattr(service, operation)(operation_db, user)
                )
                await asyncio.wait_for(remote_complete.wait(), timeout=5)
                async with sessions() as correction_db:
                    config = await repository.configuration(
                        correction_db, "org-a", lock=True
                    )
                    assert config is not None
                    config.business_account_id = "4004"
                    config.phone_number_id = "5005"
                    config.enabled = False
                    await correction_db.commit()
                correction_complete.set()
                with pytest.raises(ConflictError) as stale_result:
                    await asyncio.wait_for(operation_task, timeout=5)
                assert stale_result.value.code == "WHATSAPP_CONFIGURATION_CHANGED"

            async with sessions() as restore_db:
                config = await repository.configuration(restore_db, "org-a", lock=True)
                assert config is not None
                config.business_account_id = "1001"
                config.phone_number_id = "2001"
                config.enabled = True
                await restore_db.commit()

        await assert_stale_provider_result_rejected("verify")
        await assert_stale_provider_result_rejected("sync_templates")

        async with sessions() as db:
            config_a = await repository.configuration(db, "org-a", lock=True)
            config_b = await repository.configuration(db, "org-b", lock=True)
            assert not await repository.has_account_records(db, config_a)
            assert not await repository.has_account_records(db, config_b)
            db.add(
                WhatsAppWebhookEvent(
                    organization_id="org-b",
                    integration_id="wa-b",
                    event_key="completed-history-b",
                    correlation_id=str(uuid4()),
                    payload={},
                    status="DONE",
                )
            )
            await db.flush()
            assert await repository.has_account_records(db, config_b)
            assert not await repository.has_account_records(db, config_a)
            await db.rollback()

        async with sessions() as db:
            db.add_all(
                [
                    WhatsAppWebhookEvent(
                        id="pending-message-a",
                        organization_id="org-a",
                        integration_id="wa-a",
                        event_key="pending-message-a",
                        correlation_id=str(uuid4()),
                        payload={"kind": "message"},
                        status="PENDING",
                    ),
                    WhatsAppWebhookEvent(
                        id="pending-status-a",
                        organization_id="org-a",
                        integration_id="wa-a",
                        event_key="pending-status-a",
                        correlation_id=str(uuid4()),
                        payload={"kind": "status"},
                        status="PENDING",
                    ),
                    WhatsAppWebhookEvent(
                        id="pending-message-b",
                        organization_id="org-b",
                        integration_id="wa-b",
                        event_key="pending-message-b",
                        correlation_id=str(uuid4()),
                        payload={"kind": "message"},
                        status="PENDING",
                    ),
                ]
            )
            await db.flush()
            assert await repository.has_pending_inbound_events(db, "org-a", "wa-a")
            event = await db.get(WhatsAppWebhookEvent, "pending-message-a")
            assert event is not None
            event.status = "DONE"
            await db.flush()
            assert not await repository.has_pending_inbound_events(db, "org-a", "wa-a")
            await db.commit()

        async with sessions() as db:
            await db.execute(
                text(
                    "UPDATE organizations SET is_active=false, status='suspended' "
                    "WHERE id='org-a'"
                )
            )
            await db.execute(text("UPDATE whatsapp_integrations SET phone_index_ready=false"))
            await db.commit()

        async with sessions() as db:
            next_config = await repository.next_phone_backfill_configuration(db)
            assert next_config is not None and next_config.id == "wa-b"
            await db.rollback()

        async with sessions() as db:
            await db.execute(
                text("UPDATE organizations SET is_active=true, status='active' " "WHERE id='org-a'")
            )
            await db.execute(text("UPDATE whatsapp_integrations SET phone_index_ready=true"))
            await db.commit()

        async with sessions() as db:
            config_a = await repository.configuration(db, "org-a")
            assert config_a is not None
            assert await repository.match(db, config_a, "+14155552671") == (
                "UNKNOWN",
                None,
                None,
            )
            db.add(
                Lead(
                    id="lead-a",
                    organization_id="org-a",
                    title="Tenant A enquiry",
                    company="Tenant A",
                    contact_name="Tenant A Customer",
                    email="tenant-a-lead@example.test",
                    phone="+14155552671",
                    assigned_to="user-a",
                )
            )
            await db.flush()
            lead_a = await db.get(Lead, "lead-a")
            assert lead_a is not None
            await repository.prepare_crm_phone(db, "org-a", lead_a)
            lead_a.whatsapp_phone_verified_at = now
            await db.execute(
                text("UPDATE whatsapp_integrations SET phone_index_ready=true WHERE id='wa-a'")
            )
            await db.commit()

        async with sessions() as db:
            config_a = await repository.configuration(db, "org-a")
            assert config_a is not None
            lead_a = await db.get(Lead, "lead-a")
            assert config_a.phone_index_ready is True
            assert lead_a is not None
            assert lead_a.normalized_phone == "+14155552671"
            assert lead_a.whatsapp_phone_verified_at is not None
            assert await repository.match(db, config_a, "+14155552671") == (
                "MATCHED_LEAD",
                None,
                "lead-a",
            )
            db.add(
                Contact(
                    id="contact-a",
                    organization_id="org-a",
                    name="Tenant A Customer",
                    email="tenant-a-customer@example.test",
                    phone="+14155552671",
                )
            )
            await db.flush()
            contact_a = await db.get(Contact, "contact-a")
            assert contact_a is not None
            await repository.prepare_crm_phone(db, "org-a", contact_a)
            contact_a.whatsapp_phone_verified_at = now
            await db.execute(
                text("UPDATE whatsapp_integrations SET phone_index_ready=true WHERE id='wa-a'")
            )
            await db.commit()

        async with sessions() as db:
            config_a = await repository.configuration(db, "org-a")
            assert config_a is not None
            assert await repository.match(db, config_a, "+14155552671") == (
                "MATCHED_CONTACT",
                "contact-a",
                None,
            )
            unrelated = Lead(
                id="lead-unrelated",
                organization_id="org-a",
                title="Unrelated",
                company="Tenant A",
                contact_name="No Phone",
                email="no-phone@example.test",
                phone=None,
            )
            db.add(unrelated)
            await repository.prepare_crm_phone(db, "org-a", unrelated)
            db.add(
                Lead(
                    id="lead-imported",
                    organization_id="org-a",
                    title="Imported",
                    company="Tenant A",
                    contact_name="Imported Phone",
                    email="imported-phone@example.test",
                    phone="+1 (202) 555-0199",
                )
            )
            await db.commit()

        async with sessions() as db:
            assert await repository.repair_phone_batch(db) > 0
            await db.commit()
            imported = await db.get(Lead, "lead-imported")
            assert imported is not None
            assert imported.normalized_phone == "+12025550199"
            config_a = await repository.configuration(db, "org-a")
            assert config_a is not None and config_a.phone_index_ready is True
            assert await repository.match(db, config_a, "+14155552671") == (
                "MATCHED_CONTACT",
                "contact-a",
                None,
            )

        async with sessions() as db:
            contact_a = await db.get(Contact, "contact-a")
            assert contact_a is not None
            verified_at = contact_a.whatsapp_phone_verified_at
            contact_a.phone = "+1 (415) 555-2671"
            await repository.prepare_crm_phone(db, "org-a", contact_a)
            await db.commit()
            assert contact_a.normalized_phone == "+14155552671"
            assert contact_a.whatsapp_phone_verified_at == verified_at

        async with sessions() as db:
            base = Contact(
                id="contact-repair-base",
                organization_id="org-a",
                name="Repair Base",
                email="repair-base@example.test",
                phone="+12025550155",
            )
            db.add(base)
            await repository.prepare_crm_phone(db, "org-a", base)
            base.whatsapp_phone_verified_at = now
            await db.commit()

        async with sessions() as db:
            db.add_all(
                [
                    Contact(
                        id=f"pending-{index:03d}",
                        organization_id="org-a",
                        name=f"Pending {index}",
                        email=f"pending-{index}@example.test",
                        phone=f"+1302555{index:04d}",
                    )
                    for index in range(251)
                ]
                + [
                    Contact(
                        id="zz-repair-duplicate",
                        organization_id="org-a",
                        name="Pending Duplicate",
                        email="pending-duplicate@example.test",
                        phone="+1 (202) 555-0155",
                    )
                ]
            )
            await db.commit()

        async with sessions() as db:
            config_a = await repository.configuration(db, "org-a")
            assert config_a is not None
            assert await repository.match(db, config_a, "+12025550155") == (
                "AMBIGUOUS",
                None,
                None,
            )
            assert await repository.repair_phone_batch(db, limit=250) == 250
            await db.commit()

        async with sessions() as db:
            config_a = await repository.configuration(db, "org-a")
            assert config_a is not None
            assert await repository.match(db, config_a, "+12025550155") == (
                "AMBIGUOUS",
                None,
                None,
            )

        locked = asyncio.Event()
        release_update = asyncio.Event()

        async def update_phone_while_repair_waits() -> None:
            async with sessions() as update_db, update_db.begin():
                target = await update_db.scalar(
                    select(Contact).where(Contact.id == "zz-repair-duplicate").with_for_update()
                )
                assert target is not None
                target.phone = "+1 (202) 555-0156"
                locked.set()
                await release_update.wait()
                await update_db.flush()

        async def repair_after_contact_lock() -> None:
            await locked.wait()
            async with sessions() as repair_db:
                await repository.repair_phone_batch(repair_db, limit=250)
                await repair_db.commit()

        update_task = asyncio.create_task(update_phone_while_repair_waits())
        await locked.wait()
        repair_task = asyncio.create_task(repair_after_contact_lock())
        await asyncio.sleep(0.05)
        release_update.set()
        await asyncio.wait_for(asyncio.gather(update_task, repair_task), timeout=5)

        lock_phone = "+12025550177"
        monkeypatch.setattr(settings, "WHATSAPP_ENABLED", True)
        monkeypatch.setattr("app.services.contact_service.notification_service.notify", AsyncMock())
        async with sessions() as db:
            lock_lead = Lead(
                id="lead-lock-order",
                organization_id="org-a",
                title="Lock order lead",
                company="Tenant A",
                contact_name="Lock Order Lead",
                email="lock-order-lead@example.test",
                status="Qualified",
                phone=lock_phone,
            )
            db.add(lock_lead)
            await repository.prepare_crm_phone(db, "org-a", lock_lead)
            lock_lead.whatsapp_phone_verified_at = now
            db.add(
                WhatsAppContactIdentity(
                    id="identity-lock-order",
                    organization_id="org-a",
                    integration_id="wa-a",
                    normalized_phone_number=lock_phone,
                    lead_id=lock_lead.id,
                    state="MATCHED_LEAD",
                    consent="UNKNOWN",
                    provider_verified_at=now,
                )
            )
            await db.commit()

        concurrent_inbound = InboundEvent.model_validate(
            {
                "id": "wamid.lock-order",
                "from": lock_phone.removeprefix("+"),
                "timestamp": str(int(now.timestamp())),
                "type": "text",
                "text": {"body": "Concurrent hello"},
            }
        )

        async def persist_while_guarded() -> None:
            async with sessions() as inbound_db:
                config_a = await repository.configuration(inbound_db, "org-a")
                assert config_a is not None
                assert (
                    await repository.persist_inbound(inbound_db, config_a, concurrent_inbound)
                    is not None
                )
                await inbound_db.commit()

        async def convert_lead_while_guarded() -> None:
            async with sessions() as conversion_db:
                lead = await conversion_db.get(Lead, "lead-lock-order")
                user = await conversion_db.get(User, "user-a")
                assert lead is not None and user is not None
                await LeadService().convert_lead(
                    conversion_db,
                    lead.id,
                    LeadConvertRequest(create_deal=False),
                    user,
                )

        original_phone_guard = WhatsAppRepository.lock_phone_guard
        lead_guard_arrivals = 0
        lead_guards_reached = asyncio.Event()

        async def track_lead_guard(self, db, organization_id) -> None:
            nonlocal lead_guard_arrivals
            lead_guard_arrivals += 1
            if lead_guard_arrivals >= 2:
                lead_guards_reached.set()
            await original_phone_guard(self, db, organization_id)

        monkeypatch.setattr(WhatsAppRepository, "lock_phone_guard", track_lead_guard)
        # Hold the shared guard while both real paths start. Neither path may lock
        # Identity first; a NOWAIT probe must therefore remain available. Once the
        # guard is released, both operations must finish without a deadlock.
        async with sessions() as guard_db:
            await original_phone_guard(repository, guard_db, "org-a")
            inbound_task = asyncio.create_task(persist_while_guarded())
            conversion_task = asyncio.create_task(convert_lead_while_guarded())
            await asyncio.wait_for(lead_guards_reached.wait(), timeout=5)
            async with sessions() as probe_db:
                probe = await probe_db.scalar(
                    select(Organization)
                    .where(Organization.id == "org-a")
                    .with_for_update(nowait=True)
                )
                assert probe is not None
                await probe_db.rollback()
            await guard_db.commit()
        await asyncio.wait_for(asyncio.gather(inbound_task, conversion_task), timeout=5)

        contact_phone = "+12025550178"
        contact_inbound = InboundEvent.model_validate(
            {
                "id": "wamid.contact-lock-order",
                "from": contact_phone.removeprefix("+"),
                "timestamp": str(int(now.timestamp())),
                "type": "text",
                "text": {"body": "Concurrent contact create"},
            }
        )

        async def create_contact_while_guarded() -> None:
            async with sessions() as contact_db:
                user = await contact_db.get(User, "user-a")
                assert user is not None
                await ContactService().create_contact(
                    contact_db,
                    ContactCreate(
                        name="Concurrent Contact",
                        email="concurrent-contact@example.test",
                        phone=contact_phone,
                    ),
                    user,
                )

        async def persist_contact_inbound_while_guarded() -> None:
            async with sessions() as inbound_db:
                config_a = await repository.configuration(inbound_db, "org-a")
                assert config_a is not None
                assert (
                    await repository.persist_inbound(inbound_db, config_a, contact_inbound)
                    is not None
                )
                await inbound_db.commit()

        contact_guard_arrivals = 0
        contact_guards_reached = asyncio.Event()

        async def track_contact_guard(self, db, organization_id) -> None:
            nonlocal contact_guard_arrivals
            contact_guard_arrivals += 1
            if contact_guard_arrivals >= 2:
                contact_guards_reached.set()
            await original_phone_guard(self, db, organization_id)

        monkeypatch.setattr(WhatsAppRepository, "lock_phone_guard", track_contact_guard)
        async with sessions() as guard_db:
            await original_phone_guard(repository, guard_db, "org-a")
            contact_task = asyncio.create_task(create_contact_while_guarded())
            contact_inbound_task = asyncio.create_task(persist_contact_inbound_while_guarded())
            await asyncio.wait_for(contact_guards_reached.wait(), timeout=5)
            async with sessions() as probe_db:
                probe = await probe_db.scalar(
                    select(Organization)
                    .where(Organization.id == "org-a")
                    .with_for_update(nowait=True)
                )
                assert probe is not None
                await probe_db.rollback()
            await guard_db.commit()
        await asyncio.wait_for(asyncio.gather(contact_task, contact_inbound_task), timeout=5)

        update_phone = "+12025550179"
        async with sessions() as db:
            update_lead = Lead(
                id="lead-update-race",
                organization_id="org-a",
                title="Update race",
                company="Update Race Company",
                contact_name="Update Race Customer",
                email="update-race@example.test",
                status="Qualified",
                phone=update_phone,
            )
            db.add(update_lead)
            await repository.prepare_crm_phone(db, "org-a", update_lead)
            update_lead.whatsapp_phone_verified_at = now
            db.add(
                WhatsAppContactIdentity(
                    id="identity-update-race",
                    organization_id="org-a",
                    integration_id="wa-a",
                    normalized_phone_number=update_phone,
                    lead_id=update_lead.id,
                    state="MATCHED_LEAD",
                    consent="UNKNOWN",
                    provider_verified_at=now,
                )
            )
            await db.commit()

        async def update_lead_while_guarded() -> None:
            async with sessions() as update_db:
                user = await update_db.get(User, "user-a")
                assert user is not None
                try:
                    await LeadService().update_lead(
                        update_db,
                        "lead-update-race",
                        LeadUpdate(phone="+12025550180"),
                        user,
                    )
                except APIException as exc:
                    assert exc.status_code == 409

        async def convert_update_lead_while_guarded() -> None:
            async with sessions() as conversion_db:
                user = await conversion_db.get(User, "user-a")
                assert user is not None
                await LeadService().convert_lead(
                    conversion_db,
                    "lead-update-race",
                    LeadConvertRequest(create_deal=False),
                    user,
                )

        update_guard_arrivals = 0
        update_guards_reached = asyncio.Event()
        # Response serialization of a server-generated Lead timestamp is outside
        # this transaction-order test; keep the test focused on committed writes.
        monkeypatch.setattr("app.services.lead_service.lead_to_dict", lambda lead: {"id": lead.id})

        async def track_update_guard(self, db, organization_id) -> None:
            nonlocal update_guard_arrivals
            update_guard_arrivals += 1
            if update_guard_arrivals >= 2:
                update_guards_reached.set()
            await original_phone_guard(self, db, organization_id)

        monkeypatch.setattr(WhatsAppRepository, "lock_phone_guard", track_update_guard)
        async with sessions() as guard_db:
            await original_phone_guard(repository, guard_db, "org-a")
            update_task = asyncio.create_task(update_lead_while_guarded())
            update_conversion_task = asyncio.create_task(convert_update_lead_while_guarded())
            await asyncio.wait_for(update_guards_reached.wait(), timeout=5)
            async with sessions() as probe_db:
                probe = await probe_db.scalar(
                    select(Lead).where(Lead.id == "lead-update-race").with_for_update(nowait=True)
                )
                assert probe is not None
                await probe_db.rollback()
            await guard_db.commit()
        await asyncio.wait_for(asyncio.gather(update_task, update_conversion_task), timeout=5)

        delete_phone = "+12025550181"
        async with sessions() as db:
            delete_lead = Lead(
                id="lead-delete-race",
                organization_id="org-a",
                title="Delete race",
                company="Delete Race Company",
                contact_name="Delete Race Customer",
                email="delete-race@example.test",
                status="Qualified",
                phone=delete_phone,
            )
            db.add(delete_lead)
            await repository.prepare_crm_phone(db, "org-a", delete_lead)
            delete_lead.whatsapp_phone_verified_at = now
            db.add(
                WhatsAppContactIdentity(
                    id="identity-delete-race",
                    organization_id="org-a",
                    integration_id="wa-a",
                    normalized_phone_number=delete_phone,
                    lead_id=delete_lead.id,
                    state="MATCHED_LEAD",
                    consent="UNKNOWN",
                    provider_verified_at=now,
                )
            )
            await db.commit()

        async def delete_lead_while_guarded() -> None:
            async with sessions() as delete_db:
                await LeadService().delete_lead(
                    delete_db, "lead-delete-race", organization_id="org-a"
                )

        async def convert_deleted_lead_while_guarded() -> None:
            async with sessions() as conversion_db:
                user = await conversion_db.get(User, "user-a")
                assert user is not None
                with suppress(NotFoundError):
                    await LeadService().convert_lead(
                        conversion_db,
                        "lead-delete-race",
                        LeadConvertRequest(create_deal=False),
                        user,
                    )

        delete_guard_arrivals = 0
        delete_guards_reached = asyncio.Event()

        async def track_delete_guard(self, db, organization_id) -> None:
            nonlocal delete_guard_arrivals
            delete_guard_arrivals += 1
            if delete_guard_arrivals >= 2:
                delete_guards_reached.set()
            await original_phone_guard(self, db, organization_id)

        monkeypatch.setattr(WhatsAppRepository, "lock_phone_guard", track_delete_guard)
        async with sessions() as guard_db:
            await original_phone_guard(repository, guard_db, "org-a")
            delete_task = asyncio.create_task(delete_lead_while_guarded())
            delete_conversion_task = asyncio.create_task(convert_deleted_lead_while_guarded())
            await asyncio.wait_for(delete_guards_reached.wait(), timeout=5)
            async with sessions() as probe_db:
                probe = await probe_db.scalar(
                    select(Lead).where(Lead.id == "lead-delete-race").with_for_update(nowait=True)
                )
                assert probe is not None
                await probe_db.rollback()
            await guard_db.commit()
        await asyncio.wait_for(asyncio.gather(delete_task, delete_conversion_task), timeout=5)

        stale_phone = "+12025550182"
        async with sessions() as db:
            stale_contact = Contact(
                id="contact-stale-verification",
                organization_id="org-a",
                name="Stale Verification",
                email="stale-verification@example.test",
                phone=stale_phone,
            )
            db.add(stale_contact)
            await repository.prepare_crm_phone(db, "org-a", stale_contact)
            stale_contact.whatsapp_phone_verified_at = now
            await db.commit()

        async with sessions() as stale_db:
            stale_contact = await stale_db.get(Contact, "contact-stale-verification")
            assert stale_contact is not None
            async with sessions() as change_db:
                await ContactService().update_contact(
                    change_db,
                    stale_contact.id,
                    ContactUpdate(phone="+12025550183"),
                    organization_id="org-a",
                )
            await repository.lock_phone_guard(stale_db, "org-a")
            await repository.prepare_crm_phone(stale_db, "org-a", stale_contact)
            await stale_db.commit()

        async with sessions() as db:
            protected_contact = await db.get(Contact, "contact-stale-verification")
            assert protected_contact is not None
            assert protected_contact.phone == "+12025550183"
            assert protected_contact.normalized_phone == "+12025550183"
            assert protected_contact.whatsapp_phone_verified_at is None

        concurrent_phone = "+12025550184"
        async with sessions() as db:
            concurrent_contact = Contact(
                id="contact-update-race",
                organization_id="org-a",
                name="Concurrent Verification",
                email="concurrent-verification@example.test",
                phone=concurrent_phone,
            )
            db.add(concurrent_contact)
            await repository.prepare_crm_phone(db, "org-a", concurrent_contact)
            concurrent_contact.whatsapp_phone_verified_at = now
            await db.commit()

        async def update_contact_phone(phone: str) -> None:
            async with sessions() as update_db:
                await ContactService().update_contact(
                    update_db,
                    "contact-update-race",
                    ContactUpdate(phone=phone),
                    organization_id="org-a",
                )

        contact_update_arrivals = 0
        contact_updates_reached = asyncio.Event()

        async def track_contact_update_guard(self, db, organization_id) -> None:
            nonlocal contact_update_arrivals
            contact_update_arrivals += 1
            if contact_update_arrivals >= 2:
                contact_updates_reached.set()
            await original_phone_guard(self, db, organization_id)

        monkeypatch.setattr(WhatsAppRepository, "lock_phone_guard", track_contact_update_guard)
        async with sessions() as guard_db:
            await original_phone_guard(repository, guard_db, "org-a")
            unchanged_task = asyncio.create_task(update_contact_phone(concurrent_phone))
            changed_task = asyncio.create_task(update_contact_phone("+12025550185"))
            await asyncio.wait_for(contact_updates_reached.wait(), timeout=5)
            async with sessions() as probe_db:
                probe = await probe_db.scalar(
                    select(Contact)
                    .where(Contact.id == "contact-update-race")
                    .with_for_update(nowait=True)
                )
                assert probe is not None
                await probe_db.rollback()
            await guard_db.commit()
        await asyncio.wait_for(asyncio.gather(unchanged_task, changed_task), timeout=5)

        async with sessions() as db:
            protected_contact = await db.get(Contact, "contact-update-race")
            assert protected_contact is not None
            assert protected_contact.normalized_phone in {
                "+12025550184",
                "+12025550185",
            }
            assert protected_contact.whatsapp_phone_verified_at is None

        inbound = InboundEvent.model_validate(
            {
                "id": "wamid.inbound-a",
                "from": "14155552671",
                "timestamp": str(int(now.timestamp())),
                "type": "text",
                "text": {"body": "Hi"},
            }
        )
        async with sessions() as db:
            config_a = await repository.configuration(db, "org-a")
            assert config_a is not None
            result = await repository.persist_inbound(db, config_a, inbound)
            assert result is not None
            conversation, inbound_message = result
            assert conversation.organization_id == "org-a"
            assert conversation.assigned_user_id == "user-a"
            assert inbound_message.status == "RECEIVED"
            await db.commit()
            conversation_id = conversation.id

        async with sessions() as db:
            config_b = await repository.configuration(db, "org-b")
            user_b = await db.get(User, "user-b")
            conversation_a = await repository.conversation(
                db, "org-a", conversation_id, "user-a", {"whatsapp:read_all"}
            )
            identity_a = await repository.identity(db, conversation_a)
            assert config_b is not None and user_b is not None
            assert (
                await repository.customer_answer(
                    db,
                    config_b,
                    identity_a,
                    {"contacts:read", "invoices:read"},
                    "invoice",
                )
                is None
            )
            assert (
                await repository.timeline_messages(
                    db,
                    user_b,
                    {"whatsapp:read_all"},
                    contact_id="contact-a",
                )
                == []
            )

        async with sessions() as db:
            config_a = await repository.configuration(db, "org-a")
            assert config_a is not None
            assert await repository.persist_inbound(db, config_a, inbound) is None
            with pytest.raises(NotFoundError):
                await repository.conversation(
                    db,
                    "org-b",
                    conversation_id,
                    "user-b",
                    {"whatsapp:read_all"},
                )
            outbound = WhatsAppMessage(
                id="outbound-a",
                organization_id="org-a",
                integration_id="wa-a",
                conversation_id=conversation_id,
                provider_message_id="wamid.outbound-a",
                idempotency_key="manual-idempotency-a",
                direction="OUTBOUND",
                source="HUMAN",
                message_type="text",
                body="Hello",
                sender_phone="2001",
                recipient_phone="+14155552671",
                actor_user_id="user-a",
                status="ACCEPTED",
                work_status="DONE",
            )
            reconcile = WhatsAppMessage(
                id="outbound-reconcile",
                organization_id="org-a",
                integration_id="wa-a",
                conversation_id=conversation_id,
                provider_message_id=None,
                idempotency_key="manual-idempotency-reconcile",
                direction="OUTBOUND",
                source="HUMAN",
                message_type="text",
                body="Reconcile me",
                sender_phone="2001",
                recipient_phone="+14155552671",
                actor_user_id="user-a",
                status="UNKNOWN",
                work_status="FAILED",
            )
            db.add_all([outbound, reconcile])
            await db.commit()

        async with sessions() as db:
            config_a = await repository.configuration(db, "org-a")
            assert config_a is not None
            db.add(
                WhatsAppTemplate(
                    id="template-stale",
                    organization_id="org-a",
                    integration_id="wa-a",
                    provider_template_id="provider-template-stale",
                    name="stale_template",
                    language="en_US",
                    category="UTILITY",
                    status="APPROVED",
                    body_parameter_count=0,
                )
            )
            await db.flush()
            await repository.replace_templates(db, config_a, [])
            await db.commit()
            stale_template = await db.get(WhatsAppTemplate, "template-stale")
            assert stale_template is not None and stale_template.status == "UNAVAILABLE"

        async with sessions() as db:
            config_a = await repository.configuration(db, "org-a")
            assert config_a is not None
            delivered = StatusEvent.model_validate(
                {
                    "id": "wamid.outbound-a",
                    "status": "delivered",
                    "timestamp": str(int(now.timestamp()) + 1),
                    "recipient_id": "14155552671",
                }
            )
            sent = delivered.model_copy(
                update={"status": "sent", "timestamp": str(int(now.timestamp()) + 2)}
            )
            assert await repository.apply_status(db, config_a, delivered)
            assert await repository.apply_status(db, config_a, sent)
            await db.commit()
            message = await db.scalar(
                select(WhatsAppMessage).where(WhatsAppMessage.id == "outbound-a")
            )
            assert message is not None
            assert message.status == "DELIVERED"
            assert message.delivered_at is not None
            reconciled = StatusEvent.model_validate(
                {
                    "id": "wamid.reconciled-after-timeout",
                    "status": "delivered",
                    "timestamp": str(int(now.timestamp()) + 3),
                    "recipient_id": "14155552671",
                    "biz_opaque_callback_data": "outbound-reconcile",
                }
            )
            assert await repository.apply_status(db, config_a, reconciled)
            await db.commit()
            recovered = await db.get(WhatsAppMessage, "outbound-reconcile")
            assert recovered is not None
            assert recovered.provider_message_id == "wamid.reconciled-after-timeout"
            assert recovered.status == "DELIVERED"

        async with sessions() as db:
            await repository.detach_crm_identities(db, "org-a", contact_ids={"contact-a"})
            contact = await db.get(Contact, "contact-a")
            assert contact is not None
            await db.delete(contact)
            await db.commit()
            conversation = await repository.conversation(
                db, "org-a", conversation_id, "user-a", {"whatsapp:read_all"}
            )
            identity = await repository.identity(db, conversation)
            assert identity.contact_id is None
            assert identity.state == "UNKNOWN"
            assert conversation.ai_enabled is False
            assert conversation.status == "HUMAN_HANDOFF"
    finally:
        await engine.dispose()
        async with root.connect() as connection:
            await connection.execute(
                text(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname = :database AND pid <> pg_backend_pid()"
                ),
                {"database": database},
            )
            await connection.execute(text(f'DROP DATABASE "{database}"'))
        await root.dispose()
