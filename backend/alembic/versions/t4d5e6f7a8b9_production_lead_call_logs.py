"""Harden manual lead call logs without rewriting existing records."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "t4d5e6f7a8b9"
down_revision: str | Sequence[str] | None = "s2b3c4d5e6f7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("call_logs", sa.Column("subject", sa.String(length=255), nullable=True))
    op.add_column(
        "call_logs",
        sa.Column("follow_up_required", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.add_column(
        "call_logs", sa.Column("follow_up_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("call_logs", sa.Column("next_action", sa.String(length=1000), nullable=True))
    op.add_column(
        "call_logs",
        sa.Column(
            "created_by",
            sa.String(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column("call_logs", sa.Column("idempotency_key", sa.String(length=128)))
    op.add_column(
        "call_logs", sa.Column("idempotency_request_hash", sa.String(length=64))
    )
    op.add_column(
        "call_logs",
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.add_column(
        "call_logs",
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )

    op.create_index("ix_call_logs_created_by", "call_logs", ["created_by"])
    op.create_index("ix_call_logs_follow_up_at", "call_logs", ["follow_up_at"])
    op.create_index("ix_call_logs_timestamp", "call_logs", ["timestamp"])
    op.create_unique_constraint(
        "uq_call_logs_org_creator_idempotency",
        "call_logs",
        ["organization_id", "created_by", "idempotency_key"],
    )

    # NOT VALID preserves legacy rows while enforcing the rules for every new
    # or changed row. Existing outliers can be reviewed before later validation.
    op.execute(
        "ALTER TABLE call_logs ADD CONSTRAINT ck_call_logs_call_type "
        "CHECK (call_type IN ('Outbound','Inbound')) NOT VALID"
    )
    op.execute(
        "ALTER TABLE call_logs ADD CONSTRAINT ck_call_logs_disposition "
        "CHECK (disposition IS NULL OR disposition IN "
        "('Completed','No Answer','Busy','Failed','Other')) NOT VALID"
    )
    op.execute(
        "ALTER TABLE call_logs ADD CONSTRAINT ck_call_logs_duration "
        "CHECK (duration_seconds >= 0 AND duration_seconds <= 86400) NOT VALID"
    )


def downgrade() -> None:
    raise RuntimeError(
        "Lead call audit fields contain production data; recovery requires a reviewed backup restore"
    )
