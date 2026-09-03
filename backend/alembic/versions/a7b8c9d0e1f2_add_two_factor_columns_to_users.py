"""add encrypted 2FA fields to users

Revision ID: a7b8c9d0e1f2
Revises: f2a3b4c5d6e7
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "a7b8c9d0e1f2"
down_revision: str | Sequence[str] | None = "f2a3b4c5d6e7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add the fields used by the User 2FA setup, verification, and disable flows."""
    inspector = inspect(op.get_bind())
    existing_columns = {column["name"] for column in inspector.get_columns("users")}

    if "two_factor_secret" not in existing_columns:
        op.add_column(
            "users",
            sa.Column("two_factor_secret", sa.String(length=512), nullable=True),
        )

    if "two_factor_enabled" not in existing_columns:
        op.add_column(
            "users",
            sa.Column(
                "two_factor_enabled",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
        )


def downgrade() -> None:
    """Remove the 2FA fields from users."""
    inspector = inspect(op.get_bind())
    existing_columns = {column["name"] for column in inspector.get_columns("users")}

    if "two_factor_enabled" in existing_columns:
        op.drop_column("users", "two_factor_enabled")
    if "two_factor_secret" in existing_columns:
        op.drop_column("users", "two_factor_secret")
