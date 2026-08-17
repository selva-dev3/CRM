"""ensure super_admin is flagged as a system role

Revision ID: b4c3a2d1e9f8
Revises: a1b2c3d4e5f6
Create Date: 2026-08-17 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b4c3a2d1e9f8"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Flag the global super_admin role as a system role.

    Idempotent data migration: it never inserts or deletes rows, and only
    updates existing roles whose (case-insensitive) name is 'super_admin'.
    Leaves user_roles / role_permissions untouched.
    """
    op.execute(
        "UPDATE roles SET is_system_role = TRUE WHERE LOWER(name) = 'super_admin'"
    )


def downgrade() -> None:
    """Revert the system-role flag for super_admin.

    Safe to run: it only touches rows previously flagged by this migration.
    """
    op.execute(
        "UPDATE roles SET is_system_role = FALSE WHERE LOWER(name) = 'super_admin'"
    )