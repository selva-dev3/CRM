"""add missing subscription columns

Revision ID: d48af9dea957
Revises: a99988776655
Create Date: 2026-08-06 08:07:02.311634
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers
revision: str = "d48af9dea957"
down_revision: Union[str, Sequence[str], None] = "a99988776655"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:

    bind = op.get_bind()
    try:
        inspector = inspect(bind)
        columns = {c["name"] for c in inspector.get_columns("organization_subscriptions")}
    except Exception:
        columns = set()

    if "created_at" not in columns:
        op.add_column(
            "organization_subscriptions",
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=True,
            ),
        )

    if "updated_at" not in columns:
        op.add_column(
            "organization_subscriptions",
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=True,
            ),
        )

    try:
        fk_names = {
            fk["name"]
            for fk in inspector.get_foreign_keys("organization_subscriptions")
            if fk["name"]
        }
    except Exception:
        fk_names = set()

    if "fk_org_subscription_plan" not in fk_names:
        op.create_foreign_key(
            "fk_org_subscription_plan",
            "organization_subscriptions",
            "subscription_plans",
            ["plan_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:

    op.drop_constraint(
        "fk_org_subscription_plan",
        "organization_subscriptions",
        type_="foreignkey",
    )

    op.drop_column("organization_subscriptions", "updated_at")
    op.drop_column("organization_subscriptions", "created_at")