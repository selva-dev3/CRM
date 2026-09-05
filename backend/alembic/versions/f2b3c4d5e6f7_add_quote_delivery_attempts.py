"""Track Quote delivery attempts and provider events."""

import sqlalchemy as sa
from alembic import op

revision = "f2b3c4d5e6f7"
down_revision = "f1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "quote_delivery_attempts",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("quote_id", sa.String(), nullable=False),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("delivery_id", sa.String(length=36), nullable=False),
        sa.Column("recipient_email", sa.String(length=255), nullable=False),
        sa.Column("delivery_status", sa.String(length=30), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False, server_default="brevo"),
        sa.Column("provider_message_id", sa.String(length=255), nullable=True),
        sa.Column("provider_event_id", sa.String(length=255), nullable=True),
        sa.Column("queued_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("processing_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["quote_id"], ["quotes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("delivery_id", name="uq_quote_delivery_attempts_delivery_id"),
        sa.UniqueConstraint("provider_event_id", name="uq_quote_delivery_attempts_provider_event_id"),
    )
    op.create_index("ix_quote_delivery_attempts_quote_id", "quote_delivery_attempts", ["quote_id"])
    op.create_index(
        "ix_quote_delivery_attempts_organization_id",
        "quote_delivery_attempts",
        ["organization_id"],
    )
    op.create_index(
        "ix_quote_delivery_attempts_delivery_status",
        "quote_delivery_attempts",
        ["delivery_status"],
    )
    op.create_index("ix_quote_delivery_attempts_delivery_id", "quote_delivery_attempts", ["delivery_id"])


def downgrade() -> None:
    op.drop_index("ix_quote_delivery_attempts_delivery_id", table_name="quote_delivery_attempts")
    op.drop_index("ix_quote_delivery_attempts_delivery_status", table_name="quote_delivery_attempts")
    op.drop_index("ix_quote_delivery_attempts_organization_id", table_name="quote_delivery_attempts")
    op.drop_index("ix_quote_delivery_attempts_quote_id", table_name="quote_delivery_attempts")
    op.drop_table("quote_delivery_attempts")
