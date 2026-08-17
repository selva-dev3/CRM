"""seed default admin role with all permissions

Revision ID: c9d4e5f6a7b8
Revises: b4c3a2d1e9f8
Create Date: 2026-08-17 00:00:00.000000

"""

import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "c9d4e5f6a7b8"
down_revision: Union[str, Sequence[str], None] = "b4c3a2d1e9f8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _uuid() -> str:
    return str(uuid.uuid4())


def upgrade() -> None:
    """Seed a default 'Admin' role holding every permission and assign it to all users.

    Idempotent data migration: creates the role only if no case-insensitive 'admin'
    role exists, attaches all permission keys (skipping already-attached mappings and
    the 'all' sentinel), and assigns the role to every user that has no user_roles row
    yet. This guarantees that RBAC permission enforcement does not lock existing users
    out once it is live.
    """
    connection = op.get_bind()

    existing = connection.execute(
        sa.text("SELECT id FROM roles WHERE LOWER(name) = 'admin' LIMIT 1")
    ).fetchone()
    if existing:
        role_id = existing[0]
    else:
        role_id = _uuid()
        connection.execute(
            sa.text(
                "INSERT INTO roles (id, organization_id, name, description, is_system_role, created_at) "
                "VALUES (:role_id, NULL, 'Admin', 'Default admin role with all permissions', FALSE, NOW())"
            ),
            {"role_id": role_id},
        )

    perm_ids = [
        row[0]
        for row in connection.execute(
            sa.text("SELECT id FROM permissions WHERE key IS NOT NULL AND key != 'all'")
        ).fetchall()
    ]
    if perm_ids:
        existing_rp = {
            row[0]
            for row in connection.execute(
                sa.text("SELECT permission_id FROM role_permissions WHERE role_id = :role_id"),
                {"role_id": role_id},
            ).fetchall()
        }
        for perm_id in perm_ids:
            if perm_id not in existing_rp:
                connection.execute(
                    sa.text(
                        "INSERT INTO role_permissions (id, role_id, permission_id) "
                        "VALUES (:rp_id, :role_id, :perm_id)"
                    ),
                    {"rp_id": _uuid(), "role_id": role_id, "perm_id": perm_id},
                )

    user_ids = [
        row[0]
        for row in connection.execute(sa.text("SELECT id FROM users")).fetchall()
    ]
    if user_ids:
        existing_ur = {
            row[0]
            for row in connection.execute(
                sa.text("SELECT user_id FROM user_roles WHERE role_id = :role_id"),
                {"role_id": role_id},
            ).fetchall()
        }
        for user_id in user_ids:
            if user_id not in existing_ur:
                connection.execute(
                    sa.text(
                        "INSERT INTO user_roles (id, user_id, role_id) VALUES (:ur_id, :user_id, :role_id)"
                    ),
                    {"ur_id": _uuid(), "user_id": user_id, "role_id": role_id},
                )


def downgrade() -> None:
    """Remove role_permissions / user_roles rows and the seeded 'Admin' role.

    Only touches the role created by this migration (case-insensitive 'admin' name).
    """
    connection = op.get_bind()
    role_row = connection.execute(
        sa.text("SELECT id FROM roles WHERE LOWER(name) = 'admin' LIMIT 1")
    ).fetchone()
    if role_row:
        role_id = role_row[0]
        connection.execute(
            sa.text("DELETE FROM role_permissions WHERE role_id = :role_id"),
            {"role_id": role_id},
        )
        connection.execute(
            sa.text("DELETE FROM user_roles WHERE role_id = :role_id"),
            {"role_id": role_id},
        )
        connection.execute(
            sa.text("DELETE FROM roles WHERE id = :role_id"),
            {"role_id": role_id},
        )
