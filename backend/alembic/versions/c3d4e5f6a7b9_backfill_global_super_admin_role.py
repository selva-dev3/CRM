"""backfill the protected global super admin role

Revision ID: c3d4e5f6a7b9
Revises: a7b8c9d0e1f2
"""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c3d4e5f6a7b9"
down_revision: str | Sequence[str] | None = "a7b8c9d0e1f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

def upgrade() -> None:
    """Ensure legacy super_admin users resolve through the protected RBAC graph."""
    connection = op.get_bind()
    roles = connection.execute(
        sa.text(
            "SELECT id FROM roles "
            "WHERE organization_id IS NULL "
            "AND LOWER(TRIM(name)) IN ('super_admin', 'super admin') "
            "ORDER BY created_at ASC"
        )
    ).fetchall()

    if len(roles) > 1:
        raise RuntimeError(
            "Multiple global Super Admin roles exist; resolve the duplicate roles before migrating"
        )

    if roles:
        role_id = roles[0][0]
        connection.execute(
            sa.text("UPDATE roles SET is_system_role = TRUE WHERE id = :role_id"),
            {"role_id": role_id},
        )
    else:
        role_id = str(uuid.uuid4())
        connection.execute(
            sa.text(
                "INSERT INTO roles "
                "(id, organization_id, name, description, is_system_role, created_at) "
                "VALUES (:role_id, NULL, 'Super Admin', "
                "'Protected global platform administrator role', TRUE, CURRENT_TIMESTAMP)"
            ),
            {"role_id": role_id},
        )

    legacy_users = connection.execute(
        sa.text(
            "SELECT id FROM users "
            "WHERE LOWER(REPLACE(TRIM(role), ' ', '_')) = 'super_admin'"
        )
    ).fetchall()
    for user_row in legacy_users:
        user_id = user_row[0]
        existing_mapping = connection.execute(
            sa.text(
                "SELECT 1 FROM user_roles "
                "WHERE user_id = :user_id AND role_id = :role_id LIMIT 1"
            ),
            {"user_id": user_id, "role_id": role_id},
        ).fetchone()
        if not existing_mapping:
            connection.execute(
                sa.text(
                    "INSERT INTO user_roles (id, user_id, role_id) "
                    "VALUES (:mapping_id, :user_id, :role_id)"
                ),
                {
                    "mapping_id": str(uuid.uuid4()),
                    "user_id": user_id,
                    "role_id": role_id,
                },
            )


def downgrade() -> None:
    """Keep identity backfill data intact; manual recovery is safer than deleting role grants."""
