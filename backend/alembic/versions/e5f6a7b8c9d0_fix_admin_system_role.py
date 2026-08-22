from typing import Sequence, Union
"""protect admin as system role and attach super_admin:manage to super_admin role

Revision ID: e5f6a7b8c9d0
Revises: d1e2f3a4b5c6
Create Date: 2026-08-17 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, Sequence[str], None] = "d1e2f3a4b5c6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Corrective security migration.

    The original seed migration (c9d4e5f6a7b8) created the default 'Admin' role with
    ``is_system_role = FALSE``, leaving it modifiable/deletable like a custom role.
    Since that migration already shipped to production, we flag Admin as a system
    role here so it is protected from mutation (``_ensure_mutable_role``) without
    rewriting history.

    We also attach the ``super_admin:manage`` permission to any 'super_admin' role so
    the permission-based unrestricted-access detection works regardless of role names.
    Both statements are idempotent.
    """
    op.execute(
        "UPDATE roles SET is_system_role = TRUE WHERE LOWER(name) = 'admin' AND is_system_role = FALSE"
    )

    connection = op.get_bind()
    try:
        perm_res = connection.execute(
            sa.text("SELECT id FROM permissions WHERE key = 'super_admin:manage'")
        )
        perm = perm_res.fetchone() if perm_res else None
        if perm:
            perm_id = perm[0]
            sa_res = connection.execute(
                sa.text("SELECT id FROM roles WHERE LOWER(name) = 'super_admin' LIMIT 1")
            )
            super_admin = sa_res.fetchone() if sa_res else None
            if super_admin:
                att_res = connection.execute(
                    sa.text(
                        "SELECT permission_id FROM role_permissions "
                        "WHERE role_id = :rid AND permission_id = :pid"
                    ),
                    {"rid": super_admin[0], "pid": perm_id},
                )
                attached = att_res.fetchone() if att_res else None
                if not attached:
                    connection.execute(
                        sa.text(
                            "INSERT INTO role_permissions (id, role_id, permission_id) "
                            "VALUES (:rp_id, :role_id, :permission_id)"
                        ),
                        {
                            "rp_id": "rp-super-admin-manage-sys",
                            "role_id": super_admin[0],
                            "permission_id": perm_id,
                        },
                    )
    except Exception:
        pass


def downgrade() -> None:
    """Revert the system-role flag for Admin and detach super_admin:manage."""
    op.execute(
        "UPDATE roles SET is_system_role = FALSE WHERE LOWER(name) = 'admin' AND is_system_role = TRUE"
    )

    connection = op.get_bind()
    try:
        perm_res = connection.execute(
            sa.text("SELECT id FROM permissions WHERE key = 'super_admin:manage'")
        )
        perm = perm_res.fetchone() if perm_res else None
        if perm:
            perm_id = perm[0]
            sa_res = connection.execute(
                sa.text("SELECT id FROM roles WHERE LOWER(name) = 'super_admin' LIMIT 1")
            )
            super_admin = sa_res.fetchone() if sa_res else None
            if super_admin:
                connection.execute(
                    sa.text(
                        "DELETE FROM role_permissions WHERE role_id = :rid AND permission_id = :pid"
                    ),
                    {"rid": super_admin[0], "pid": perm_id},
                )
    except Exception:
        pass
