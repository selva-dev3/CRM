"""Persist quote delivery claims, provider receipts and PDF storage identity."""

import sqlalchemy as sa
from alembic import op

revision = "f6a7b8c9d1e2"
down_revision = "e5f6a7b8c9d1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for name, length in (("delivery_id", 36), ("delivery_status", 30), ("recipient_email", 255),
                          ("provider_message_id", 255), ("pdf_s3_key", 500)):
        op.add_column("quotes", sa.Column(name, sa.String(length), nullable=True))
    op.add_column("quotes", sa.Column("delivery_attempts", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("quotes", sa.Column("delivery_claimed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("quotes", sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_quotes_delivery_status", "quotes", ["delivery_status"])


def downgrade() -> None:
    op.drop_index("ix_quotes_delivery_status", table_name="quotes")
    for name in ("rejected_at", "delivery_claimed_at", "delivery_attempts", "pdf_s3_key", "provider_message_id",
                 "recipient_email", "delivery_status", "delivery_id"):
        op.drop_column("quotes", name)
