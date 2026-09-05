"""Persist quote commercial terms for review and invoice creation."""

import sqlalchemy as sa
from alembic import op

revision = "f1a2b3c4d5e6"
down_revision = "b8c9d0e1f2a3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("quotes", sa.Column("payment_terms", sa.String(100), nullable=True))
    op.add_column("quotes", sa.Column("due_date", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("quotes", "due_date")
    op.drop_column("quotes", "payment_terms")
