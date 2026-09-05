"""Enforce uniqueness for RBAC relationship rows.

Revision ID: 20260905_rbac_unique
Revises: c9d4e5f6a7b8
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260905_rbac_unique"
down_revision: str | Sequence[str] | None = "c7e8f9a0b1d2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _remove_duplicates(table: str, columns: tuple[str, str]) -> None:
    connection = op.get_bind()
    rows = connection.execute(
        sa.text(
            f"SELECT id, {columns[0]}, {columns[1]} FROM {table} "  # noqa: S608
            f"ORDER BY {columns[0]}, {columns[1]}, id"  # noqa: S608
        )
    ).mappings()
    seen: set[tuple[object, object]] = set()
    duplicate_ids: list[str] = []
    for row in rows:
        key = (row[columns[0]], row[columns[1]])
        if key in seen:
            duplicate_ids.append(row["id"])
        else:
            seen.add(key)
    for duplicate_id in duplicate_ids:
        connection.execute(
            sa.text(f"DELETE FROM {table} WHERE id = :duplicate_id"),  # noqa: S608
            {"duplicate_id": duplicate_id},
        )


def upgrade() -> None:
    _remove_duplicates("user_roles", ("user_id", "role_id"))
    _remove_duplicates("role_permissions", ("role_id", "permission_id"))
    op.create_unique_constraint(
        "uq_user_roles_user_role", "user_roles", ["user_id", "role_id"]
    )
    op.create_unique_constraint(
        "uq_role_permissions_role_permission",
        "role_permissions",
        ["role_id", "permission_id"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_role_permissions_role_permission", "role_permissions", type_="unique")
    op.drop_constraint("uq_user_roles_user_role", "user_roles", type_="unique")
