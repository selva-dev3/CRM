"""add role column to organizations

Revision ID: e7f8a9b0c1d2
Revises: b4c3a2d1e9f8
Create Date: 2026-08-22 16:35:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = "e7f8a9b0c1d2"
down_revision: Union[str, Sequence[str], None] = "b4c3a2d1e9f8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def add_column_if_not_exists(table_name: str, column: sa.Column):
    bind = op.get_bind()
    inspector = inspect(bind)

    existing_columns = {
        c["name"] for c in inspector.get_columns(table_name)
    }

    if column.name not in existing_columns:
        op.add_column(table_name, column)


def drop_column_if_exists(table_name: str, column_name: str):
    bind = op.get_bind()
    inspector = inspect(bind)

    existing_columns = {
        c["name"] for c in inspector.get_columns(table_name)
    }

    if column_name in existing_columns:
        op.drop_column(table_name, column_name)


def upgrade() -> None:
    """Upgrade schema."""
    add_column_if_not_exists("organizations", sa.Column("role", sa.String(length=100), server_default="Admin", nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    drop_column_if_exists("organizations", "role")
