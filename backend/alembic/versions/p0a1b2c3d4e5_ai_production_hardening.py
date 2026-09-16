"""add AI production hardening state and audit metadata

Revision ID: p0a1b2c3d4e5
Revises: l9c0d1e2f3g4
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "p0a1b2c3d4e5"
down_revision: str | Sequence[str] | None = "l9c0d1e2f3g4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("ai_conversations", sa.Column("expires_at", sa.DateTime(timezone=True)))
    op.execute(
        "UPDATE ai_conversations "
        "SET expires_at = CURRENT_TIMESTAMP + INTERVAL '30 days' "
        "WHERE expires_at IS NULL"
    )
    op.create_index("ix_ai_conversations_expires_at", "ai_conversations", ["expires_at"])

    op.add_column("ai_runs", sa.Column("request_id", sa.String(length=100)))
    op.add_column(
        "ai_runs", sa.Column("reserved_cost_usd", sa.Float(), nullable=False, server_default="0")
    )
    op.add_column(
        "ai_runs",
        sa.Column("pricing_status", sa.String(length=30), nullable=False, server_default="unknown"),
    )
    op.add_column("ai_runs", sa.Column("pricing_version", sa.String(length=50)))
    op.add_column("ai_runs", sa.Column("pricing_currency", sa.String(length=3)))
    op.create_index("ix_ai_runs_request_id", "ai_runs", ["request_id"])

    op.add_column("ai_actions", sa.Column("executing_started_at", sa.DateTime(timezone=True)))
    op.add_column(
        "ai_actions", sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0")
    )

    op.add_column("tasks", sa.Column("ai_action_id", sa.String()))
    op.create_foreign_key(
        "fk_tasks_ai_action_id_ai_actions",
        "tasks",
        "ai_actions",
        ["ai_action_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_tasks_ai_action_id", "tasks", ["ai_action_id"])
    op.create_unique_constraint("uq_tasks_ai_action_id", "tasks", ["ai_action_id"])

    op.create_table(
        "ai_tool_audits",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("request_id", sa.String(length=100), nullable=False),
        sa.Column("run_id", sa.String(), nullable=True),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("tool_name", sa.String(length=100), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=True),
        sa.Column("model_name", sa.String(length=100), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("result_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("succeeded", sa.Boolean(), nullable=False),
        sa.Column("error_category", sa.String(length=100), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["run_id"], ["ai_runs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("request_id", "run_id", "organization_id", "user_id", "tool_name", "created_at"):
        op.create_index(f"ix_ai_tool_audits_{column}", "ai_tool_audits", [column])


def downgrade() -> None:
    op.drop_table("ai_tool_audits")
    op.drop_constraint("uq_tasks_ai_action_id", "tasks", type_="unique")
    op.drop_index("ix_tasks_ai_action_id", table_name="tasks")
    op.drop_constraint("fk_tasks_ai_action_id_ai_actions", "tasks", type_="foreignkey")
    op.drop_column("tasks", "ai_action_id")
    op.drop_column("ai_actions", "attempt_count")
    op.drop_column("ai_actions", "executing_started_at")
    op.drop_index("ix_ai_runs_request_id", table_name="ai_runs")
    op.drop_column("ai_runs", "pricing_currency")
    op.drop_column("ai_runs", "pricing_version")
    op.drop_column("ai_runs", "pricing_status")
    op.drop_column("ai_runs", "reserved_cost_usd")
    op.drop_column("ai_runs", "request_id")
    op.drop_index("ix_ai_conversations_expires_at", table_name="ai_conversations")
    op.drop_column("ai_conversations", "expires_at")
