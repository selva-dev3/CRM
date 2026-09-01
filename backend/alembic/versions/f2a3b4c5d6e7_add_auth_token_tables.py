"""add persisted magic-link and refresh-token tables

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f2a3b4c5d6e7"
down_revision: str | Sequence[str] | None = "e1f2a3b4c5d6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _create_token_table(
    table_name: str,
    token_index_name: str,
    token_constraint_name: str,
    used_column_name: str,
) -> None:
    inspector = sa.inspect(op.get_bind())
    if table_name in inspector.get_table_names():
        return

    op.create_table(
        table_name,
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("token", sa.String(length=64), nullable=False),
        sa.Column(used_column_name, sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token", name=token_constraint_name),
    )
    op.create_index(f"ix_{table_name}_user_id", table_name, ["user_id"])
    op.create_index(token_index_name, table_name, ["token"], unique=True)


def upgrade() -> None:
    _create_token_table(
        "refresh_tokens",
        "ix_refresh_tokens_token",
        "uq_refresh_tokens_token",
        "is_revoked",
    )
    _create_token_table(
        "magic_link_tokens",
        "ix_magic_link_tokens_token",
        "uq_magic_link_tokens_token",
        "is_used",
    )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "magic_link_tokens" in inspector.get_table_names():
        op.drop_table("magic_link_tokens")
    if "refresh_tokens" in inspector.get_table_names():
        op.drop_table("refresh_tokens")
