"""Persist subscription checkout request hashes after checkout restoration."""

import sqlalchemy as sa
from alembic import op

revision = "g0b3c4d5e6f7"
down_revision = "f9a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "organization_subscriptions",
        sa.Column("checkout_request_hash", sa.String(64), nullable=True),
    )


def downgrade() -> None:
    raise RuntimeError(
        "Checkout request hash migration is forward-only; preserve billing recovery state"
    )
