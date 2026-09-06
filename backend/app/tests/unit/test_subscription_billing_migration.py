"""Subscription restoration preserves history and transaction ownership."""

import importlib.util
from io import StringIO
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import OrganizationSubscription, ProcessedWebhookEvent
from app.repositories.organization_repository import OrganizationRepository

MIGRATION_PATH = (
    Path(__file__).resolve().parents[3]
    / "alembic/versions/f9a2b3c4d5e6_restore_subscription_checkout.py"
)


def _migration(path=MIGRATION_PATH):
    spec = importlib.util.spec_from_file_location("subscription_billing_migration", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_request_hash_migration_upgrades_existing_checkout_state():
    migration = _migration(
        MIGRATION_PATH.with_name("g0b3c4d5e6f7_subscription_checkout_request_hash.py")
    )
    assert migration.down_revision == "f9a2b3c4d5e6"
    engine = sa.create_engine("sqlite://")
    metadata = sa.MetaData()
    subscriptions = sa.Table(
        "organization_subscriptions",
        metadata,
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("checkout_session_id", sa.String(255)),
        sa.Column("checkout_operation_id", sa.String(64)),
        sa.Column("checkout_plan_slug", sa.String(100)),
    )
    try:
        with engine.begin() as connection:
            metadata.create_all(connection)
            connection.execute(
                subscriptions.insert().values(
                    id="sub-existing",
                    checkout_session_id="cs-existing",
                    checkout_operation_id="operation-existing",
                    checkout_plan_slug="professional",
                )
            )
            with Operations.context(MigrationContext.configure(connection)):
                migration.upgrade()
            restored = sa.Table(
                "organization_subscriptions", sa.MetaData(), autoload_with=connection
            )
            row = connection.execute(sa.select(restored)).mappings().one()
            assert dict(row) == {
                "id": "sub-existing",
                "checkout_session_id": "cs-existing",
                "checkout_operation_id": "operation-existing",
                "checkout_plan_slug": "professional",
                "checkout_request_hash": None,
            }
            column = restored.c.checkout_request_hash
            assert column.nullable and column.type.length == 64
            digest = "a" * 64
            connection.execute(restored.update().values(checkout_request_hash=digest))
            assert connection.scalar(sa.select(column)) == digest
    finally:
        engine.dispose()
    with pytest.raises(RuntimeError, match="forward-only"):
        migration.downgrade()


def test_forward_migration_restores_checkout_without_changing_history():
    migration = _migration()
    assert migration.down_revision == "e8f1a2b3c4d5"
    metadata = sa.MetaData()
    subscriptions = sa.Table(
        "organization_subscriptions",
        metadata,
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("legacy_provider_data", sa.JSON),
        sa.Column("customer_id", sa.String(255)),
        sa.Column("subscription_id", sa.String(255)),
        sa.Column("plan_id", sa.String),
        sa.Column("max_users", sa.Integer),
    )
    archives = [
        {"checkout_session_id": "cs_historical", "customer_id": "cus_archived"},
        {"checkout_session_id": None},
        {},
        None,
    ]
    engine = sa.create_engine("sqlite://")
    try:
        with engine.begin() as connection:
            metadata.create_all(connection)
            connection.execute(
                subscriptions.insert(),
                [
                    {
                        "id": str(i),
                        "legacy_provider_data": archive,
                        "customer_id": "cus_current",
                        "subscription_id": f"sub_{i}",
                        "plan_id": "existing-plan",
                        "max_users": 17,
                    }
                    for i, archive in enumerate(archives)
                ],
            )
            with Operations.context(MigrationContext.configure(connection)):
                migration.upgrade()
            restored = sa.Table(
                "organization_subscriptions", sa.MetaData(), autoload_with=connection
            )
            rows = connection.execute(sa.select(restored).order_by(restored.c.id)).mappings().all()
            for i, row in enumerate(rows):
                assert row["checkout_session_id"] == ("cs_historical" if i == 0 else None)
                assert row["legacy_provider_data"] == archives[i]
                assert row["customer_id"] == "cus_current"
                assert row["subscription_id"] == f"sub_{i}"
                assert row["plan_id"] == "existing-plan"
                assert row["max_users"] == 17
                for field in ("checkout_operation_id", "checkout_plan_slug", "checkout_expires_at"):
                    assert row[field] is None
                    assert restored.c[field].nullable
            assert {
                tuple(index["column_names"])
                for index in sa.inspect(connection).get_indexes("organization_subscriptions")
            } == {("checkout_session_id",), ("subscription_id",)}
    finally:
        engine.dispose()


def test_postgresql_migration_sql_is_subscription_only_and_timezone_aware():
    output = StringIO()
    context = MigrationContext.configure(
        dialect_name="postgresql",
        opts={"as_sql": True, "output_buffer": output, "literal_binds": True},
    )
    with Operations.context(context):
        _migration().upgrade()
    sql = output.getvalue()
    assert "TIMESTAMP WITH TIME ZONE" in sql
    assert "legacy_provider_data ->> 'checkout_session_id'" in sql
    assert "VARCHAR(64)" in sql
    assert "VARCHAR(100)" in sql
    assert "invoices" not in sql
    assert "payments" not in sql
    assert "DROP" not in sql
    assert "DELETE" not in sql
    assert "COMMIT" not in sql


def test_migration_refuses_to_discard_recovery_state():
    with pytest.raises(RuntimeError, match="forward-only"):
        _migration().downgrade()


def test_model_recovery_fields_and_event_uniqueness():
    columns = OrganizationSubscription.__table__.c
    for name, length in (
        ("checkout_session_id", 255),
        ("checkout_operation_id", 64),
        ("checkout_request_hash", 64),
        ("checkout_plan_slug", 100),
    ):
        assert columns[name].type.length == length
        assert columns[name].nullable
    assert columns.checkout_expires_at.type.timezone
    assert columns.checkout_expires_at.nullable
    assert any(
        index.unique and list(index.columns.keys()) == ["event_id"]
        for index in ProcessedWebhookEvent.__table__.indexes
    )


@pytest.mark.asyncio
async def test_org_lock_refreshes_identity_map_and_does_not_commit():
    db = AsyncMock(spec=AsyncSession)
    result = MagicMock()
    db.execute.return_value = result
    org = result.scalar_one_or_none.return_value
    assert await OrganizationRepository().get_by_id_for_update(db, "org-1") is org
    statement = db.execute.call_args.args[0]
    compiled = statement.compile(dialect=postgresql.dialect())
    assert str(compiled).endswith("FOR UPDATE")
    assert compiled.params == {"id_1": "org-1"}
    assert statement.get_execution_options()["populate_existing"] is True
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "method,column,value",
    [
        ("get_subscription_by_provider_id", "subscription_id", "sub-1"),
        ("get_subscription_by_checkout_session_id", "checkout_session_id", "cs-1"),
        ("get_processed_webhook_event", "event_id", "evt-1"),
    ],
)
@pytest.mark.parametrize("found", [True, False])
async def test_provider_lookups_filter_exact_identifier(method, column, value, found):
    db = AsyncMock(spec=AsyncSession)
    result = MagicMock()
    record = MagicMock() if found else None
    result.scalar_one_or_none.return_value = record
    db.execute.return_value = result
    assert await getattr(OrganizationRepository(), method)(db, value) is record
    statement = db.execute.call_args.args[0]
    compiled = statement.compile(dialect=postgresql.dialect())
    assert f".{column} = %({column}_1)s" in str(compiled)
    assert compiled.params == {f"{column}_1": value}
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_record_webhook_event_leaves_commit_to_caller():
    db = AsyncMock(spec=AsyncSession)
    event = await OrganizationRepository().record_processed_webhook_event(
        db, event_id="evt-1", event_type="checkout.session.completed"
    )
    assert event.event_id == "evt-1"
    assert event.event_type == "checkout.session.completed"
    db.add.assert_called_once_with(event)
    db.commit.assert_not_awaited()
    db.flush.assert_not_awaited()
