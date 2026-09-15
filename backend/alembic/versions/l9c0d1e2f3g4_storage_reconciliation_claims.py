"""Add recoverable storage reconciliation claims.

Revision ID: l9c0d1e2f3g4
Revises: k8b9c0d1e2f3
"""

import sqlalchemy as sa
from alembic import op

revision = "l9c0d1e2f3g4"
down_revision = "k8b9c0d1e2f3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "storage_reconciliations",
        sa.Column("claimed_until", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "storage_reconciliations",
        sa.Column("claim_token", sa.String(length=36), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("storage_reconciliations", "claim_token")
    op.drop_column("storage_reconciliations", "claimed_until")
