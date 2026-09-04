"""add tenant-scoped AI runtime governance

Revision ID: d4e5f6a7b8c0
Revises: c3d4e5f6a7b9
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d4e5f6a7b8c0"
down_revision: str | Sequence[str] | None = "c3d4e5f6a7b9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "ai_generated_contents",
        "content_type",
        existing_type=sa.String(length=50),
        type_=sa.String(length=150),
        existing_nullable=False,
    )
    op.add_column(
        "ai_conversations",
        sa.Column("organization_id", sa.String(), nullable=True),
    )
    op.create_foreign_key(
        "fk_ai_conversations_organization_id",
        "ai_conversations",
        "organizations",
        ["organization_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_ai_conversations_organization_id",
        "ai_conversations",
        ["organization_id"],
    )

    op.add_column(
        "ai_generated_contents",
        sa.Column("organization_id", sa.String(), nullable=True),
    )
    op.create_foreign_key(
        "fk_ai_generated_contents_organization_id",
        "ai_generated_contents",
        "organizations",
        ["organization_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_ai_generated_contents_organization_id",
        "ai_generated_contents",
        ["organization_id"],
    )

    op.execute("""
        UPDATE ai_conversations AS conversation
        SET organization_id = users.organization_id
        FROM users
        WHERE conversation.user_id = users.id
          AND conversation.organization_id IS NULL
        """)
    op.execute("""
        UPDATE ai_generated_contents AS content
        SET organization_id = users.organization_id
        FROM users
        WHERE content.user_id = users.id
          AND content.organization_id IS NULL
        """)
    op.alter_column("ai_conversations", "organization_id", nullable=False)
    op.alter_column("ai_generated_contents", "organization_id", nullable=False)

    op.create_table(
        "ai_organization_configs",
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("provider", sa.String(length=50), nullable=True),
        sa.Column("model_name", sa.String(length=100), nullable=True),
        sa.Column("monthly_cost_limit_usd", sa.Float(), nullable=True),
        sa.Column("icp_profile_json", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("organization_id"),
    )

    op.create_table(
        "ai_runs",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("feature", sa.String(length=100), nullable=False),
        sa.Column("entity_type", sa.String(length=50), nullable=True),
        sa.Column("entity_id", sa.String(), nullable=True),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("model_name", sa.String(length=100), nullable=False),
        sa.Column("prompt_version", sa.String(length=50), nullable=False, server_default="v1"),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="started"),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("estimated_cost_usd", sa.Float(), nullable=False, server_default="0"),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in (
        "organization_id",
        "user_id",
        "feature",
        "entity_type",
        "entity_id",
        "status",
        "created_at",
    ):
        op.create_index(f"ix_ai_runs_{column}", "ai_runs", [column])

    op.create_table(
        "ai_actions",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("run_id", sa.String(), nullable=False),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("action_type", sa.String(length=50), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="pending"),
        sa.Column("result_json", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["run_id"], ["ai_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("run_id", "organization_id", "user_id", "status"):
        op.create_index(f"ix_ai_actions_{column}", "ai_actions", [column])

    op.create_table(
        "ai_transcripts",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("run_id", sa.String(), nullable=False),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("source_type", sa.String(length=30), nullable=True),
        sa.Column("source_id", sa.String(), nullable=True),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("language", sa.String(length=30), nullable=True),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("transcript_text", sa.Text(), nullable=False),
        sa.Column("segments_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["run_id"], ["ai_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id"),
    )
    for column in ("organization_id", "user_id", "source_type", "source_id", "created_at"):
        op.create_index(f"ix_ai_transcripts_{column}", "ai_transcripts", [column])


def downgrade() -> None:
    op.drop_table("ai_transcripts")
    op.drop_table("ai_actions")
    op.drop_table("ai_runs")
    op.drop_table("ai_organization_configs")
    op.drop_index("ix_ai_generated_contents_organization_id", table_name="ai_generated_contents")
    op.drop_constraint(
        "fk_ai_generated_contents_organization_id",
        "ai_generated_contents",
        type_="foreignkey",
    )
    op.drop_column("ai_generated_contents", "organization_id")
    op.drop_index("ix_ai_conversations_organization_id", table_name="ai_conversations")
    op.drop_constraint(
        "fk_ai_conversations_organization_id",
        "ai_conversations",
        type_="foreignkey",
    )
    op.drop_column("ai_conversations", "organization_id")
    op.alter_column(
        "ai_generated_contents",
        "content_type",
        existing_type=sa.String(length=150),
        type_=sa.String(length=50),
        existing_nullable=False,
    )
