"""Restore organization subscription checkout and persist recovery state.

The provider archive and existing entitlements remain unchanged.
"""

import sqlalchemy as sa
from alembic import op

revision = "f9a2b3c4d5e6"
down_revision = "e8f1a2b3c4d5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for column in (
        sa.Column("checkout_session_id", sa.String(255), nullable=True),
        sa.Column("checkout_operation_id", sa.String(64), nullable=True),
        sa.Column("checkout_plan_slug", sa.String(100), nullable=True),
        sa.Column("checkout_expires_at", sa.DateTime(timezone=True), nullable=True),
    ):
        op.add_column("organization_subscriptions", column)

    subscriptions = sa.table(
        "organization_subscriptions",
        sa.column("legacy_provider_data", sa.JSON()),
        sa.column("checkout_session_id", sa.String(255)),
    )
    op.execute(
        subscriptions.update().values(
            checkout_session_id=subscriptions.c.legacy_provider_data[
                "checkout_session_id"
            ].as_string()
        )
    )
    op.create_index(
        "ix_organization_subscriptions_checkout_session_id",
        "organization_subscriptions",
        ["checkout_session_id"],
    )
    op.create_index(
        "ix_organization_subscriptions_subscription_id",
        "organization_subscriptions",
        ["subscription_id"],
    )


def downgrade() -> None:
    raise RuntimeError(
        "Subscription checkout restoration is forward-only; preserve billing recovery state"
    )
