"""Forward migration against populated history in a private disposable DB schema."""

import asyncio
import logging
import os
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy.ext.asyncio as async_sqlalchemy
from alembic import command
from alembic.config import Config
from sqlalchemy import insert, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

from app.models import Organization


@pytest.mark.asyncio
async def test_manual_billing_migration_preserves_populated_financial_history(monkeypatch, caplog):
    url = os.getenv("CRM_WORKFLOW_TEST_DATABASE_URL")
    if not url:
        pytest.skip("An isolated PostgreSQL workflow database is required")
    parsed = make_url(url)
    assert parsed.host in {"localhost", "127.0.0.1"}
    assert parsed.database == "crm_workflow_test"
    schema = f"invoice_migration_test_{uuid4().hex}"
    root_engine = create_async_engine(url)
    async with root_engine.begin() as db:
        await db.execute(text(f'CREATE SCHEMA "{schema}"'))
    # Keep historical rows for inspection; the enclosing Docker DB is disposable.
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
        await asyncio.to_thread(command.upgrade, config, "d7e8f9a0b1c2")
        assert_logging_preserved("historical upgrade")
        async with engine.begin() as db:
            await db.execute(
                insert(Organization).values(
                    id="history-org", name="Historical tenant", currency="INR"
                )
            )
            await db.execute(text("""
                INSERT INTO invoices
                    (id, organization_id, invoice_number, amount, paid_amount, currency,
                     status, due_date, stripe_checkout_url, stripe_checkout_session_id,
                     delivery_status, delivery_id)
                VALUES ('history-invoice', 'history-org', 'INV-HISTORY-000007', 200, 200,
                    'INR', 'Paid', now(), 'https://checkout.example.com/archived',
                    'historical-session', 'Pending', 'historical-delivery')
            """))
            await db.execute(text("""
                INSERT INTO payments
                    (id, organization_id, invoice_id, payment_number, provider,
                     provider_payment_id, checkout_session_id, amount, currency,
                     status, paid_at, payment_method)
                VALUES ('history-payment', 'history-org', 'history-invoice',
                    'PAY-HISTORY-000007', 'stripe', 'historical-provider-payment',
                    'historical-session', 200, 'INR', 'Succeeded',
                    '2026-08-01T12:00:00+00:00', 'card')
            """))
        async with engine.begin() as db:
            await db.execute(text("UPDATE invoices SET paid_amount=199 WHERE id='history-invoice'"))
        with pytest.raises(RuntimeError, match="reconciliation"):
            await asyncio.to_thread(command.upgrade, config, "e8f1a2b3c4d5")
        assert_logging_preserved("rejected upgrade")
        async with engine.begin() as db:
            assert (
                await db.scalar(text("SELECT version_num FROM alembic_version")) == "d7e8f9a0b1c2"
            )
            assert (
                await db.scalar(
                    text("SELECT provider_payment_id FROM payments WHERE id='history-payment'")
                )
                == "historical-provider-payment"
            )
            await db.execute(text("UPDATE invoices SET paid_amount=200 WHERE id='history-invoice'"))
        await asyncio.to_thread(command.upgrade, config, "e8f1a2b3c4d5")
        assert_logging_preserved("manual billing upgrade")
        async with engine.connect() as db:
            assert (
                await db.scalar(text("SELECT version_num FROM alembic_version")) == "e8f1a2b3c4d5"
            )
            invoice = (
                (await db.execute(text("SELECT * FROM invoices WHERE id='history-invoice'")))
                .mappings()
                .one()
            )
            payment = (
                (await db.execute(text("SELECT * FROM payments WHERE id='history-payment'")))
                .mappings()
                .one()
            )
            assert invoice["invoice_number"] == "INV-HISTORY-000007"
            assert invoice["amount"] == invoice["paid_amount"] == Decimal("200.00")
            assert invoice["status"] == "Draft"
            assert invoice["payment_status"] == "Paid"
            assert invoice["finalized_at"] is None
            assert invoice["accepted_at"] is None
            assert invoice["delivery_status"] is None
            assert (
                invoice["legacy_provider_data"]["stripe_checkout_session_id"]
                == "historical-session"
            )
            assert invoice["legacy_provider_data"]["status"] == "Paid"
            assert payment["payment_number"] == "PAY-HISTORY-000007"
            assert payment["amount"] == Decimal("200.00")
            assert payment["status"] == "Succeeded"
            assert payment["payment_type"] == "Legacy"
            assert payment["payment_date"].isoformat() == "2026-08-01"
            assert (
                payment["legacy_provider_data"]["provider_payment_id"]
                == "historical-provider-payment"
            )
            assert "provider_payment_id" not in payment
            assert "stripe_checkout_session_id" not in invoice
            assert await db.scalar(text("SELECT count(*) FROM payments")) == 1
    finally:
        await engine.dispose()
        await root_engine.dispose()
