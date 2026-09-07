"""Add durable integration delivery outbox and truthful sync defaults.

Revision ID: q0f1a2b3c4d5
Revises: p9e0f1a2b3c4
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "q0f1a2b3c4d5"
down_revision: str | Sequence[str] | None = "p9e0f1a2b3c4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("integrations", "sync_enabled", server_default=sa.false())
    op.execute(
        "UPDATE integrations SET sync_enabled = false "
        "WHERE lower(provider) IN ('google', 'hubspot', 'mailchimp')"
    )
    op.create_table(
        "integration_deliveries",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("integration_id", sa.String(), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("event_name", sa.String(length=100), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="Pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True)),
        sa.Column("claimed_until", sa.DateTime(timezone=True)),
        sa.Column("delivered_at", sa.DateTime(timezone=True)),
        sa.Column("provider_status_code", sa.Integer()),
        sa.Column("last_error", sa.String(length=255)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["integration_id"], ["integrations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id", "integration_id", "idempotency_key",
            name="uq_integration_delivery_idempotency",
        ),
    )
    for column in ("organization_id", "integration_id", "provider", "event_name", "status", "next_attempt_at", "claimed_until"):
        op.create_index(f"ix_integration_deliveries_{column}", "integration_deliveries", [column])


def downgrade() -> None:
    op.drop_table("integration_deliveries")
    op.alter_column("integrations", "sync_enabled", server_default=sa.true())
