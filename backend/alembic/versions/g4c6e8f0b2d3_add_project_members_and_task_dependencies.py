"""Add project membership and task dependency relationships.

Revision ID: g4c6e8f0b2d3
Revises: f3b5d7e9a1c2
"""

import sqlalchemy as sa
from alembic import op

revision = "g4c6e8f0b2d3"
down_revision = "f3b5d7e9a1c2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "project_members",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("project_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("role", sa.String(length=50), server_default="Member", nullable=False),
        sa.Column("added_by", sa.String(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["added_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "user_id", name="uq_project_members_user"),
    )
    op.create_index("ix_project_members_project_id", "project_members", ["project_id"])
    op.create_index("ix_project_members_user_id", "project_members", ["user_id"])
    op.execute(
        sa.text(
            """
            INSERT INTO project_members (id, project_id, user_id, role, added_by)
            SELECT md5('project-member:' || p.id || ':' || p.owner_id),
                   p.id, p.owner_id, 'Owner', p.created_by
            FROM projects p
            JOIN users u ON u.id = p.owner_id
            WHERE p.owner_id IS NOT NULL
              AND u.organization_id = p.organization_id
            ON CONFLICT (project_id, user_id) DO NOTHING
            """
        )
    )

    op.create_table(
        "task_dependencies",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("task_id", sa.String(), nullable=False),
        sa.Column("depends_on_task_id", sa.String(), nullable=False),
        sa.Column("created_by", sa.String(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("task_id <> depends_on_task_id", name="ck_task_dependency_not_self"),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["depends_on_task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("task_id", "depends_on_task_id", name="uq_task_dependencies_pair"),
    )
    op.create_index("ix_task_dependencies_task_id", "task_dependencies", ["task_id"])
    op.create_index(
        "ix_task_dependencies_depends_on_task_id", "task_dependencies", ["depends_on_task_id"]
    )


def downgrade() -> None:
    contains_business_data = op.get_bind().execute(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM project_members) "
            "OR EXISTS (SELECT 1 FROM task_dependencies)"
        )
    ).scalar_one()
    if contains_business_data:
        raise RuntimeError(
            "Cannot downgrade project membership/dependencies while business data exists"
        )
    op.drop_index("ix_task_dependencies_depends_on_task_id", table_name="task_dependencies")
    op.drop_index("ix_task_dependencies_task_id", table_name="task_dependencies")
    op.drop_table("task_dependencies")
    op.drop_index("ix_project_members_user_id", table_name="project_members")
    op.drop_index("ix_project_members_project_id", table_name="project_members")
    op.drop_table("project_members")
