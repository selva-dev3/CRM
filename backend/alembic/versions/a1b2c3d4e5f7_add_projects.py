"""add organization-scoped projects for project-aware CRM AI search"""

import sqlalchemy as sa
from alembic import op

revision = "a1b2c3d4e5f7"
down_revision = "f0a1b2c3d4e5"
branch_labels = None
depends_on = None


PROJECT_PERMISSIONS = (
    ("projects:read", "View Projects", "View organization projects"),
    ("projects:create", "Create Projects", "Create organization projects"),
    ("projects:update", "Update Projects", "Edit organization projects"),
    ("projects:delete", "Delete Projects", "Delete organization projects"),
    ("projects:assign", "Assign Projects", "Assign projects to team members"),
)


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="Planning"),
        sa.Column("priority", sa.String(length=50), nullable=False, server_default="Medium"),
        sa.Column("owner_id", sa.String(), nullable=True),
        sa.Column("start_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("due_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("budget", sa.Numeric(14, 2), nullable=True),
        sa.Column("completion_percentage", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_projects_organization_id", "projects", ["organization_id"])
    op.create_index("ix_projects_name", "projects", ["name"])
    op.create_index("ix_projects_status", "projects", ["status"])
    op.create_index("ix_projects_priority", "projects", ["priority"])
    op.create_index("ix_projects_owner_id", "projects", ["owner_id"])
    op.create_index("ix_projects_due_date", "projects", ["due_date"])
    permission_table = sa.table(
        "permissions",
        sa.column("id", sa.String),
        sa.column("key", sa.String),
        sa.column("name", sa.String),
        sa.column("category", sa.String),
        sa.column("description", sa.String),
    )
    connection = op.get_bind()
    for key, name, description in PROJECT_PERMISSIONS:
        exists = connection.execute(
            sa.select(permission_table.c.id).where(permission_table.c.key == key)
        ).first()
        if not exists:
            connection.execute(
                permission_table.insert().values(
                    id=key.replace(":", "-") + "-permission",
                    key=key,
                    name=name,
                    category="Projects",
                    description=description,
                )
            )


def downgrade() -> None:
    op.drop_index("ix_projects_due_date", table_name="projects")
    op.drop_index("ix_projects_owner_id", table_name="projects")
    op.drop_index("ix_projects_priority", table_name="projects")
    op.drop_index("ix_projects_status", table_name="projects")
    op.drop_index("ix_projects_name", table_name="projects")
    op.drop_index("ix_projects_organization_id", table_name="projects")
    op.drop_table("projects")
    op.execute(sa.text("DELETE FROM permissions WHERE key LIKE 'projects:%'"))
