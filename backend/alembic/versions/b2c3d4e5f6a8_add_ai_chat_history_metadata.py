"""add persisted AI chat response and fallback metadata"""

import sqlalchemy as sa
from alembic import op

revision = "b2c3d4e5f6a8"
down_revision = "a1b2c3d4e5f7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table_name in ("tasks", "deals"):
        op.add_column(table_name, sa.Column("project_id", sa.String(), nullable=True))
        op.create_foreign_key(
            f"fk_{table_name}_project_id_projects",
            table_name,
            "projects",
            ["project_id"],
            ["id"],
            ondelete="SET NULL",
        )
        op.create_index(f"ix_{table_name}_project_id", table_name, ["project_id"])
    op.add_column("ai_prompts", sa.Column("run_id", sa.String(), nullable=True))
    op.add_column(
        "ai_prompts",
        sa.Column("result_blocks_json", sa.Text(), nullable=False, server_default="[]"),
    )
    op.add_column(
        "ai_prompts", sa.Column("evidence_json", sa.Text(), nullable=False, server_default="[]")
    )
    op.add_column(
        "ai_prompts",
        sa.Column("follow_up_questions_json", sa.Text(), nullable=False, server_default="[]"),
    )
    op.create_foreign_key(
        "fk_ai_prompts_run_id_ai_runs",
        "ai_prompts",
        "ai_runs",
        ["run_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_ai_prompts_run_id", "ai_prompts", ["run_id"])
    op.add_column(
        "ai_runs",
        sa.Column("fallback_used", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "ai_runs",
        sa.Column("attempted_models_json", sa.Text(), nullable=False, server_default="[]"),
    )


def downgrade() -> None:
    op.drop_column("ai_runs", "attempted_models_json")
    op.drop_column("ai_runs", "fallback_used")
    op.drop_index("ix_ai_prompts_run_id", table_name="ai_prompts")
    op.drop_constraint("fk_ai_prompts_run_id_ai_runs", "ai_prompts", type_="foreignkey")
    op.drop_column("ai_prompts", "follow_up_questions_json")
    op.drop_column("ai_prompts", "evidence_json")
    op.drop_column("ai_prompts", "result_blocks_json")
    op.drop_column("ai_prompts", "run_id")
    for table_name in ("deals", "tasks"):
        op.drop_index(f"ix_{table_name}_project_id", table_name=table_name)
        op.drop_constraint(f"fk_{table_name}_project_id_projects", table_name, type_="foreignkey")
        op.drop_column(table_name, "project_id")
