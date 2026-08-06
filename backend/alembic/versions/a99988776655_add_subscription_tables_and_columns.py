"""add subscription tables and columns

Revision ID: a99988776655
Revises: cdbf23cfb64c
Create Date: 2026-08-06 13:15:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "a99988776655"
down_revision: Union[str, Sequence[str], None] = "cdbf23cfb64c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def add_column_if_not_exists(table_name: str, column: sa.Column):
    bind = op.get_bind()
    inspector = inspect(bind)

    existing_columns = {
        c["name"] for c in inspector.get_columns(table_name)
    }

    if column.name not in existing_columns:
        op.add_column(table_name, column)


def upgrade() -> None:

    bind = op.get_bind()
    inspector = inspect(bind)

    # ------------------------------------------------------------------
    # Subscription Plans
    # ------------------------------------------------------------------

    if "subscription_plans" not in inspector.get_table_names():

        op.create_table(
            "subscription_plans",

            sa.Column("id", sa.String(), primary_key=True),

            sa.Column(
                "name",
                sa.String(100),
                nullable=False
            ),

            sa.Column(
                "slug",
                sa.String(100),
                nullable=False,
                unique=True
            ),

            sa.Column(
                "price_monthly",
                sa.Float(),
                server_default="0"
            ),

            sa.Column(
                "price_yearly",
                sa.Float(),
                server_default="0"
            ),

            sa.Column(
                "max_users",
                sa.Integer(),
                server_default="3"
            ),

            sa.Column(
                "max_storage_gb",
                sa.Integer(),
                server_default="5"
            ),

            sa.Column(
                "ai_credits",
                sa.Integer(),
                server_default="0"
            ),

            sa.Column(
                "features",
                sa.Text(),
                nullable=True
            ),

            sa.Column(
                "is_active",
                sa.Boolean(),
                server_default="true"
            )
        )

    # ------------------------------------------------------------------
    # Organization Subscription
    # ------------------------------------------------------------------

    if "organization_subscriptions" in inspector.get_table_names():

        add_column_if_not_exists(
            "organization_subscriptions",
            sa.Column("plan_id", sa.String(), nullable=True)
        )

        add_column_if_not_exists(
            "organization_subscriptions",
            sa.Column(
                "billing_cycle",
                sa.String(20),
                server_default="Monthly",
                nullable=True
            )
        )

        add_column_if_not_exists(
            "organization_subscriptions",
            sa.Column(
                "amount",
                sa.Float(),
                server_default="0"
            )
        )

        add_column_if_not_exists(
            "organization_subscriptions",
            sa.Column(
                "currency",
                sa.String(10),
                server_default="INR"
            )
        )

        add_column_if_not_exists(
            "organization_subscriptions",
            sa.Column(
                "trial",
                sa.Boolean(),
                server_default="false"
            )
        )

        add_column_if_not_exists(
            "organization_subscriptions",
            sa.Column(
                "started_at",
                sa.DateTime(timezone=True)
            )
        )

        add_column_if_not_exists(
            "organization_subscriptions",
            sa.Column(
                "current_period_start",
                sa.DateTime(timezone=True)
            )
        )

        add_column_if_not_exists(
            "organization_subscriptions",
            sa.Column(
                "current_period_end",
                sa.DateTime(timezone=True)
            )
        )

        add_column_if_not_exists(
            "organization_subscriptions",
            sa.Column(
                "next_billing",
                sa.DateTime(timezone=True)
            )
        )

        add_column_if_not_exists(
            "organization_subscriptions",
            sa.Column(
                "expires_at",
                sa.DateTime(timezone=True)
            )
        )

        add_column_if_not_exists(
            "organization_subscriptions",
            sa.Column(
                "auto_renew",
                sa.Boolean(),
                server_default="true"
            )
        )

        add_column_if_not_exists(
            "organization_subscriptions",
            sa.Column(
                "payment_provider",
                sa.String(50),
                server_default="Stripe"
            )
        )

        add_column_if_not_exists(
            "organization_subscriptions",
            sa.Column(
                "payment_method",
                sa.String(100)
            )
        )

        add_column_if_not_exists(
            "organization_subscriptions",
            sa.Column(
                "customer_id",
                sa.String(255)
            )
        )

        add_column_if_not_exists(
            "organization_subscriptions",
            sa.Column(
                "subscription_id",
                sa.String(255)
            )
        )

        add_column_if_not_exists(
            "organization_subscriptions",
            sa.Column(
                "invoice_id",
                sa.String(100)
            )
        )

        add_column_if_not_exists(
            "organization_subscriptions",
            sa.Column(
                "max_users",
                sa.Integer(),
                server_default="100"
            )
        )

        add_column_if_not_exists(
            "organization_subscriptions",
            sa.Column(
                "current_users",
                sa.Integer(),
                server_default="1"
            )
        )

        add_column_if_not_exists(
            "organization_subscriptions",
            sa.Column(
                "storage_limit_gb",
                sa.Integer(),
                server_default="500"
            )
        )

        add_column_if_not_exists(
            "organization_subscriptions",
            sa.Column(
                "storage_used_gb",
                sa.Float(),
                server_default="0.5"
            )
        )

        add_column_if_not_exists(
            "organization_subscriptions",
            sa.Column(
                "ai_credits",
                sa.Integer(),
                server_default="-1"
            )
        )

        add_column_if_not_exists(
            "organization_subscriptions",
            sa.Column(
                "support_plan",
                sa.String(50),
                server_default="Standard"
            )
        )

        add_column_if_not_exists(
            "organization_subscriptions",
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()")
            )
        )

        add_column_if_not_exists(
            "organization_subscriptions",
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()")
            )
        )

        # ----------------------------------------------------------
        # Foreign Key
        # ----------------------------------------------------------

        fk_names = {
            fk["name"]
            for fk in inspector.get_foreign_keys(
                "organization_subscriptions"
            )
            if fk["name"]
        }

        if "fk_org_subscription_plan" not in fk_names:

            op.create_foreign_key(
                "fk_org_subscription_plan",
                "organization_subscriptions",
                "subscription_plans",
                ["plan_id"],
                ["id"],
                ondelete="SET NULL"
            )


def downgrade() -> None:
    pass