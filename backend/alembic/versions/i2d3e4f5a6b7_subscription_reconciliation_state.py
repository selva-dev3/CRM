"""Persist safe diagnostics for subscriptions that cannot be verified upstream."""

import sqlalchemy as sa
from alembic import op

revision = "i2d3e4f5a6b7"
down_revision = "h1c4d5e6f7a8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "organization_subscriptions",
        sa.Column("reconciliation_required", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "organization_subscriptions",
        sa.Column("last_provider_check_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "organization_subscriptions",
        sa.Column("last_provider_error_code", sa.String(length=80), nullable=True),
    )
    op.add_column(
        "organization_subscriptions",
        sa.Column("last_provider_request_id", sa.String(length=120), nullable=True),
    )
    op.alter_column("organization_subscriptions", "reconciliation_required", server_default=None)


def downgrade() -> None:
    raise RuntimeError(
        "Subscription reconciliation state is forward-only; preserve billing diagnostics"
    )
