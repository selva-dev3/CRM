"""Make subscription plans the complete plan-catalog source of truth.

Revision ID: k4f5a6b7c8d9
Revises: j3e4f5a6b7c8
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "k4f5a6b7c8d9"
down_revision: str | Sequence[str] | None = "j3e4f5a6b7c8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


PLANS = (
    {
        "id": "plan-free",
        "name": "Free",
        "slug": "free",
        "description": "Core CRM tools for small teams getting started.",
        "price_monthly": 0,
        "price_yearly": 0,
        "currency": "INR",
        "billing_cycle": "month",
        "max_users": 3,
        "max_storage_gb": 5,
        "ai_credits": 50,
        "features": "Dashboard, Leads, Contacts",
        "is_popular": False,
        "sort_order": 1,
    },
    {
        "id": "plan-starter",
        "name": "Starter",
        "slug": "starter",
        "description": "Sales workflow essentials for growing teams.",
        "price_monthly": 999,
        "price_yearly": 9990,
        "currency": "INR",
        "billing_cycle": "month",
        "max_users": 10,
        "max_storage_gb": 20,
        "ai_credits": 500,
        "features": "Everything in Free, Deals, Tasks",
        "is_popular": False,
        "sort_order": 2,
    },
    {
        "id": "plan-professional",
        "name": "Professional",
        "slug": "professional",
        "description": "Advanced automation, reporting, and AI for established sales teams.",
        "price_monthly": 2999,
        "price_yearly": 29990,
        "currency": "INR",
        "billing_cycle": "month",
        "max_users": 50,
        "max_storage_gb": 100,
        "ai_credits": 5000,
        "features": "Everything in Starter, AI, Reports",
        "is_popular": True,
        "sort_order": 3,
    },
    {
        "id": "plan-business",
        "name": "Business",
        "slug": "business",
        "description": "Expanded capacity for large sales organizations.",
        "price_monthly": 6999,
        "price_yearly": 69990,
        "currency": "INR",
        "billing_cycle": "month",
        "max_users": 200,
        "max_storage_gb": 500,
        "ai_credits": 20000,
        "features": "Everything in Professional",
        "is_popular": False,
        "sort_order": 4,
    },
    {
        "id": "plan-enterprise",
        "name": "Enterprise",
        "slug": "enterprise",
        "description": "Enterprise capacity and priority support for complex organizations.",
        "price_monthly": 29990,
        "price_yearly": 299900,
        "currency": "INR",
        "billing_cycle": "month",
        "max_users": 100,
        "max_storage_gb": 500,
        "ai_credits": 100000,
        "features": "Unlimited Everything, Priority Support",
        "is_popular": False,
        "sort_order": 5,
    },
)


def upgrade() -> None:
    op.add_column(
        "subscription_plans",
        sa.Column("description", sa.String(length=500), nullable=False, server_default=""),
    )
    op.add_column(
        "subscription_plans",
        sa.Column("currency", sa.String(length=10), nullable=False, server_default="INR"),
    )
    op.add_column(
        "subscription_plans",
        sa.Column("billing_cycle", sa.String(length=20), nullable=False, server_default="month"),
    )
    op.add_column(
        "subscription_plans",
        sa.Column("is_popular", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "subscription_plans",
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
    )

    bind = op.get_bind()
    plan_table = sa.table(
        "subscription_plans",
        sa.column("id", sa.String()),
        sa.column("name", sa.String()),
        sa.column("slug", sa.String()),
        sa.column("description", sa.String()),
        sa.column("price_monthly", sa.Float()),
        sa.column("price_yearly", sa.Float()),
        sa.column("currency", sa.String()),
        sa.column("billing_cycle", sa.String()),
        sa.column("max_users", sa.Integer()),
        sa.column("max_storage_gb", sa.Integer()),
        sa.column("ai_credits", sa.Integer()),
        sa.column("features", sa.Text()),
        sa.column("is_active", sa.Boolean()),
        sa.column("is_popular", sa.Boolean()),
        sa.column("sort_order", sa.Integer()),
    )
    for plan in PLANS:
        existing = bind.execute(
            sa.select(plan_table.c.id).where(sa.func.lower(plan_table.c.slug) == plan["slug"])
        ).scalar_one_or_none()
        if existing:
            bind.execute(
                plan_table.update()
                .where(plan_table.c.id == existing)
                .values(
                    description=plan["description"],
                    currency=plan["currency"],
                    billing_cycle=plan["billing_cycle"],
                    is_popular=plan["is_popular"],
                    sort_order=plan["sort_order"],
                )
            )
        else:
            bind.execute(plan_table.insert().values(**plan, is_active=True))

    op.execute("""
        UPDATE organization_subscriptions AS subscription
        SET plan_id = plan.id
        FROM organizations AS organization, subscription_plans AS plan
        WHERE subscription.organization_id = organization.id
          AND subscription.plan_id IS NULL
          AND lower(plan.slug) = lower(organization.plan)
        """)
    op.execute("""
        INSERT INTO organization_subscriptions (
            id, organization_id, plan_id, status, billing_cycle, amount, currency,
            auto_renew, max_users, current_users, storage_limit_gb, storage_used_gb,
            ai_credits, started_at
        )
        SELECT
            'sub-free-' || organization.id,
            organization.id,
            plan.id,
            'active',
            plan.billing_cycle,
            plan.price_monthly,
            plan.currency,
            false,
            plan.max_users,
            0,
            plan.max_storage_gb,
            0,
            plan.ai_credits,
            CURRENT_TIMESTAMP
        FROM organizations AS organization
        JOIN subscription_plans AS plan ON lower(plan.slug) = 'free' AND plan.is_active = true
        WHERE lower(organization.plan) = 'free'
          AND NOT EXISTS (
              SELECT 1 FROM organization_subscriptions AS subscription
              WHERE subscription.organization_id = organization.id
          )
        """)


def downgrade() -> None:
    op.drop_column("subscription_plans", "sort_order")
    op.drop_column("subscription_plans", "is_popular")
    op.drop_column("subscription_plans", "billing_cycle")
    op.drop_column("subscription_plans", "currency")
    op.drop_column("subscription_plans", "description")
