import importlib.util
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

from app.models import Organization, OrganizationSubscription, SubscriptionPlan
from app.services.subscription_plan_service import (
    apply_plan_to_organization,
    build_free_subscription,
)


def _migration():
    path = (
        Path(__file__).resolve().parents[3]
        / "alembic/versions/k4f5a6b7c8d9_subscription_plan_catalog.py"
    )
    spec = importlib.util.spec_from_file_location("subscription_plan_catalog", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_catalog_migration_defines_ordered_database_plans():
    migration = _migration()

    assert migration.down_revision == "j3e4f5a6b7c8"
    assert [plan["slug"] for plan in migration.PLANS] == [
        "free",
        "starter",
        "professional",
        "business",
        "enterprise",
    ]
    assert [plan["sort_order"] for plan in migration.PLANS] == [1, 2, 3, 4, 5]
    assert sum(plan["is_popular"] for plan in migration.PLANS) == 1


def test_free_subscription_copies_entitlements_from_database_plan_without_provider_data():
    plan = SubscriptionPlan(
        id="custom-free",
        name="Community",
        slug="free",
        price_monthly=0,
        currency="USD",
        billing_cycle="month",
        max_users=7,
        max_storage_gb=12,
        ai_credits=34,
        is_active=True,
    )
    organization = Organization(id="org-1", name="Acme")

    apply_plan_to_organization(organization, plan)
    subscription = build_free_subscription(
        organization_id=organization.id, plan=plan, current_users=1
    )

    assert organization.plan == "Community"
    assert organization.max_users == 7
    assert subscription.plan_id == "custom-free"
    assert subscription.amount == 0
    assert subscription.currency == "USD"
    assert subscription.billing_cycle == "month"
    assert subscription.max_users == 7
    assert subscription.storage_limit_gb == 12
    assert subscription.ai_credits == 34
    assert subscription.payment_provider is None
    assert subscription.customer_id is None
    assert subscription.subscription_id is None
    assert subscription.auto_renew is False


def test_plan_catalog_fields_and_one_subscription_constraint_are_modeled():
    columns = SubscriptionPlan.__table__.c
    for field in (
        "description",
        "currency",
        "billing_cycle",
        "is_popular",
        "sort_order",
    ):
        assert field in columns
    assert OrganizationSubscription.__table__.c.organization_id.unique is True


def test_catalog_migration_preserves_existing_terms_and_backfills_only_free_organizations():
    engine = sa.create_engine("sqlite://")
    metadata = sa.MetaData()
    plans = sa.Table(
        "subscription_plans",
        metadata,
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False, unique=True),
        sa.Column("price_monthly", sa.Float, default=0),
        sa.Column("price_yearly", sa.Float, default=0),
        sa.Column("max_users", sa.Integer, default=3),
        sa.Column("max_storage_gb", sa.Integer, default=5),
        sa.Column("ai_credits", sa.Integer, default=0),
        sa.Column("features", sa.Text),
        sa.Column("is_active", sa.Boolean, default=True),
    )
    organizations = sa.Table(
        "organizations",
        metadata,
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("plan", sa.String(100), nullable=False),
    )
    subscriptions = sa.Table(
        "organization_subscriptions",
        metadata,
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("organization_id", sa.String, nullable=False, unique=True),
        sa.Column("plan_id", sa.String),
        sa.Column("status", sa.String(50)),
        sa.Column("billing_cycle", sa.String(20)),
        sa.Column("amount", sa.Float),
        sa.Column("currency", sa.String(10)),
        sa.Column("auto_renew", sa.Boolean),
        sa.Column("max_users", sa.Integer),
        sa.Column("current_users", sa.Integer),
        sa.Column("storage_limit_gb", sa.Integer),
        sa.Column("storage_used_gb", sa.Float),
        sa.Column("ai_credits", sa.Integer),
        sa.Column("started_at", sa.DateTime(timezone=True)),
    )
    try:
        with engine.begin() as connection:
            metadata.create_all(connection)
            connection.execute(
                plans.insert().values(
                    id="existing-starter",
                    name="Configured Starter",
                    slug="starter",
                    price_monthly=4321,
                    price_yearly=40000,
                    max_users=17,
                    max_storage_gb=23,
                    ai_credits=99,
                    features="Configured feature",
                    is_active=True,
                )
            )
            connection.execute(
                organizations.insert(),
                [{"id": "org-free", "plan": "Free"}, {"id": "org-paid", "plan": "Enterprise"}],
            )
            with Operations.context(MigrationContext.configure(connection)):
                _migration().upgrade()

            migrated_plans = sa.Table("subscription_plans", sa.MetaData(), autoload_with=connection)
            starter = (
                connection.execute(
                    sa.select(migrated_plans).where(migrated_plans.c.slug == "starter")
                )
                .mappings()
                .one()
            )
            assert starter["name"] == "Configured Starter"
            assert starter["price_monthly"] == 4321
            assert starter["max_users"] == 17
            assert starter["currency"] == "INR"
            assert starter["sort_order"] == 2
            assert connection.scalar(sa.select(sa.func.count()).select_from(migrated_plans)) == 5

            rows = connection.execute(sa.select(subscriptions)).mappings().all()
            assert [row["organization_id"] for row in rows] == ["org-free"]
            assert rows[0]["plan_id"] == connection.scalar(
                sa.select(migrated_plans.c.id).where(migrated_plans.c.slug == "free")
            )
    finally:
        engine.dispose()
