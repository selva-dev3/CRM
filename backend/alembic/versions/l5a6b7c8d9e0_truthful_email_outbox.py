"""Add a durable, truthful generic email outbox.

Revision ID: l5a6b7c8d9e0
Revises: k4f5a6b7c8d9
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "l5a6b7c8d9e0"
down_revision: str | Sequence[str] | None = "k4f5a6b7c8d9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("emails", sa.Column("lead_id", sa.String(), nullable=True))
    op.add_column("emails", sa.Column("idempotency_key", sa.String(length=128), nullable=True))
    op.add_column("emails", sa.Column("request_hash", sa.String(length=64), nullable=True))
    op.add_column("emails", sa.Column("provider_message_id", sa.String(length=255), nullable=True))
    op.add_column(
        "emails",
        sa.Column("delivery_attempts", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("emails", sa.Column("claimed_until", sa.DateTime(timezone=True), nullable=True))
    op.add_column("emails", sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("emails", sa.Column("failure_reason", sa.String(length=500), nullable=True))
    op.add_column(
        "emails",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.add_column(
        "emails",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.execute("UPDATE emails SET status = 'Sent' WHERE lower(status) = 'sent'")
    op.execute("UPDATE emails SET created_at = COALESCE(sent_at, CURRENT_TIMESTAMP)")
    op.alter_column(
        "emails",
        "status",
        existing_type=sa.String(length=50),
        nullable=False,
        server_default="Pending",
    )
    op.alter_column(
        "emails",
        "sent_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=True,
        server_default=None,
    )
    op.create_foreign_key(
        "fk_emails_lead_id_leads",
        "emails",
        "leads",
        ["lead_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_emails_lead_id", "emails", ["lead_id"])
    op.create_index("ix_emails_status", "emails", ["status"])
    op.create_index("ix_emails_claimed_until", "emails", ["claimed_until"])
    op.create_unique_constraint(
        "uq_emails_org_idempotency", "emails", ["organization_id", "idempotency_key"]
    )
    op.create_check_constraint(
        "ck_emails_delivery_status",
        "emails",
        "status IN ('Draft','Pending','Processing','Sent','Failed','Unknown')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_emails_delivery_status", "emails", type_="check")
    op.drop_constraint("uq_emails_org_idempotency", "emails", type_="unique")
    op.drop_index("ix_emails_claimed_until", table_name="emails")
    op.drop_index("ix_emails_status", table_name="emails")
    op.drop_index("ix_emails_lead_id", table_name="emails")
    op.drop_constraint("fk_emails_lead_id_leads", "emails", type_="foreignkey")
    op.execute("UPDATE emails SET status = lower(status) WHERE status = 'Sent'")
    op.execute("UPDATE emails SET sent_at = COALESCE(sent_at, created_at, CURRENT_TIMESTAMP)")
    op.alter_column(
        "emails",
        "sent_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
    )
    op.alter_column(
        "emails",
        "status",
        existing_type=sa.String(length=50),
        nullable=True,
        server_default="sent",
    )
    for column in (
        "updated_at",
        "created_at",
        "failure_reason",
        "last_attempt_at",
        "claimed_until",
        "delivery_attempts",
        "provider_message_id",
        "request_hash",
        "idempotency_key",
        "lead_id",
    ):
        op.drop_column("emails", column)
