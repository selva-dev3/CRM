"""Subscription recovery migration on historical rows in isolated PostgreSQL."""

import asyncio
import logging
import os
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy.ext.asyncio as async_sqlalchemy
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine


@pytest.mark.asyncio
async def test_subscription_restore_preserves_entitlements_and_archived_checkout(
    monkeypatch, caplog
):
    url = os.getenv("CRM_WORKFLOW_TEST_DATABASE_URL")
    if not url:
        pytest.skip("An isolated PostgreSQL workflow database is required")
    parsed = make_url(url)
    assert parsed.host in {"localhost", "127.0.0.1"}
    assert parsed.database == "crm_workflow_test"
    schema = f"subscription_migration_test_{uuid4().hex}"
    root_engine = create_async_engine(url)
    async with root_engine.begin() as db:
        await db.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_async_engine(url, connect_args={"server_settings": {"search_path": schema}})
    original_factory = async_sqlalchemy.async_engine_from_config

    def scoped_factory(configuration, **kwargs):
        kwargs["connect_args"] = {"server_settings": {"search_path": schema}}
        return original_factory(configuration, **kwargs)

    monkeypatch.setattr(async_sqlalchemy, "async_engine_from_config", scoped_factory)
    # Do not load the CLI logging configuration into pytest's shared process.
    config = Config()
    config.set_main_option("script_location", str(Path(__file__).resolve().parents[3] / "alembic"))
    logger = logging.getLogger(__name__)
    root_handlers = tuple(logging.getLogger().handlers)

    def assert_logging_preserved(phase):
        assert tuple(logging.getLogger().handlers) == root_handlers
        assert not logger.disabled
        message = f"Migration logging remains available: {phase}"
        logger.warning(message)
        assert message in caplog.messages

    try:
        await asyncio.to_thread(command.upgrade, config, "e8f1a2b3c4d5")
        assert_logging_preserved("historical upgrade")
        async with engine.begin() as db:
            await db.execute(text("""
                INSERT INTO organizations (id, name, plan, max_users, is_active)
                VALUES ('restore-org', 'Recovery tenant', 'Professional', 50, true)
            """))
            await db.execute(
                text("""
                INSERT INTO organization_subscriptions
                    (id, organization_id, status, billing_cycle, amount, currency,
                     payment_provider, customer_id, subscription_id, max_users,
                     storage_limit_gb, storage_used_gb, ai_credits, legacy_provider_data)
                VALUES ('restore-sub', 'restore-org', 'active', 'Monthly', 2999, 'INR',
                    'Stripe', 'cus_archived_test', 'sub_archived_test', 50, 100, 7, 5000,
                    CAST(:archive AS json))
            """),
                {"archive": '{"checkout_session_id":"cs_archived_test","legacy_archive":true}'},
            )
        await asyncio.to_thread(command.upgrade, config, "f9a2b3c4d5e6")
        assert_logging_preserved("subscription restore upgrade")
        # Exercise the forward path for databases where f9 has already run.
        async with engine.begin() as db:
            await db.execute(text("""
                UPDATE organization_subscriptions
                SET checkout_operation_id='operation-before-hash',
                    checkout_plan_slug='professional'
                WHERE id='restore-sub'
            """))
        await asyncio.to_thread(command.upgrade, config, "g0b3c4d5e6f7")
        assert_logging_preserved("checkout request hash upgrade")
        async with engine.connect() as db:
            assert (
                await db.scalar(text("SELECT version_num FROM alembic_version")) == "g0b3c4d5e6f7"
            )
            row = (
                (await db.execute(text("SELECT * FROM organization_subscriptions")))
                .mappings()
                .one()
            )
            assert row["id"] == "restore-sub"
            assert row["checkout_session_id"] == "cs_archived_test"
            assert row["checkout_operation_id"] == "operation-before-hash"
            assert row["checkout_plan_slug"] == "professional"
            assert row["checkout_request_hash"] is None
            assert row["checkout_expires_at"] is None
            assert row["subscription_id"] == "sub_archived_test"
            assert row["customer_id"] == "cus_archived_test"
            assert row["amount"] == 2999
            assert row["status"] == "active"
            assert row["max_users"] == 50
            assert row["storage_limit_gb"] == 100
            assert row["storage_used_gb"] == 7
            assert row["ai_credits"] == 5000
            assert row["legacy_provider_data"] == {
                "checkout_session_id": "cs_archived_test",
                "legacy_archive": True,
            }
            org = (
                await db.execute(
                    text("SELECT plan,max_users FROM organizations WHERE id='restore-org'")
                )
            ).one()
            assert tuple(org) == ("Professional", 50)
    finally:
        await engine.dispose()
        await root_engine.dispose()
