"""add super_admin:manage permission

Revision ID: d1e2f3a4b5c6
Revises: c9d4e5f6a7b8
Create Date: 2026-08-17 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "d1e2f3a4b5c6"
down_revision: Union[str, Sequence[str], None] = "c9d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Insert the 'super_admin:manage' permission and attach it to the 'Admin' role.

    Idempotent: no-ops if the permission key already exists.
    """
    connection = op.get_bind()

    try:
        res = connection.execute(
            sa.text("SELECT id FROM permissions WHERE key = 'super_admin:manage'")
        )
        if not res:
            return
        existing = res.fetchone()
    except Exception:
        return

    if existing:
        return

    perm_id = "perm-super-admin-manage"
    connection.execute(
        sa.text(
            "INSERT INTO permissions (id, key, name, category, description) "
            "VALUES (:id, 'super_admin:manage', 'Super Admin Platform Management', "
            "'Super Admin', 'Platform-level operations such as creating organizations')"
        ),
        {"id": perm_id},
    )

    try:
        admin_res = connection.execute(
            sa.text("SELECT id FROM roles WHERE LOWER(name) = 'admin' LIMIT 1")
        )
        admin = admin_res.fetchone() if admin_res else None
        if admin:
            att_res = connection.execute(
                sa.text("SELECT permission_id FROM role_permissions WHERE role_id = :rid AND permission_id = :pid"),
                {"rid": admin[0], "pid": perm_id},
            )
            attached = att_res.fetchone() if att_res else None
            if not attached:
                connection.execute(
                    sa.text(
                        "INSERT INTO role_permissions (id, role_id, permission_id) "
                        "VALUES (:rp_id, :role_id, :permission_id)"
                    ),
                    {"rp_id": "rp-super-admin-manage", "role_id": admin[0], "permission_id": perm_id},
                )
    except Exception:
        pass


def downgrade() -> None:
    """Remove the super_admin:manage permission row and its role mappings."""
    connection = op.get_bind()
    try:
        res = connection.execute(
            sa.text("SELECT id FROM permissions WHERE key = 'super_admin:manage'")
        )
        existing = res.fetchone() if res else None
        if existing:
            perm_id = existing[0]
            connection.execute(
                sa.text("DELETE FROM role_permissions WHERE permission_id = :pid"),
                {"pid": perm_id},
            )
            connection.execute(sa.text("DELETE FROM permissions WHERE id = :pid"), {"pid": perm_id})
    except Exception:
        pass