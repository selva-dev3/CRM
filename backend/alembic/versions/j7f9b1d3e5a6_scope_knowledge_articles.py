"""Add fail-closed record visibility for knowledge articles.

Revision ID: j7f9b1d3e5a6
Revises: i6e8a0b2c4d5
"""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "j7f9b1d3e5a6"
down_revision: str | None = "i6e8a0b2c4d5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ALL_ACCESS_ROLES = {"admin", "customer support", "support manager", "read only"}


def _stable_id(role_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"crm:record-scope:{role_id}:knowledge_base"))


def upgrade() -> None:
    connection = op.get_bind()
    roles = connection.execute(sa.text("SELECT id, lower(btrim(name)) FROM roles")).all()
    rows = [
        {
            "id": _stable_id(role_id),
            "role_id": role_id,
            "module": "knowledge_base",
            "scope": "all" if normalized_name in _ALL_ACCESS_ROLES else "none",
        }
        for role_id, normalized_name in roles
    ]
    if rows:
        connection.execute(
            sa.text(
                """
                INSERT INTO role_record_scopes (id, role_id, module, scope)
                VALUES (:id, :role_id, :module, :scope)
                ON CONFLICT (role_id, module) DO NOTHING
                """
            ),
            rows,
        )


def downgrade() -> None:
    connection = op.get_bind()
    role_ids = connection.execute(sa.text("SELECT id FROM roles")).scalars().all()
    migration_scope_ids = [_stable_id(role_id) for role_id in role_ids]
    if migration_scope_ids:
        connection.execute(
            sa.text(
                "DELETE FROM role_record_scopes "
                "WHERE module = 'knowledge_base' AND id = ANY(:ids)"
            ),
            {"ids": migration_scope_ids},
        )
