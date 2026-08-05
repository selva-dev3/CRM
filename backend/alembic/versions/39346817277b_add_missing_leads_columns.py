"""add missing leads columns

Revision ID: 39346817277b
Revises: f8a832876815
Create Date: 2026-08-03 23:31:36.941554
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "39346817277b"
down_revision: Union[str, Sequence[str], None] = "f8a832876815"
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
    add_column_if_not_exists(
        "lead_attachments",
        sa.Column("file_size", sa.Integer(), nullable=True),
    )

    add_column_if_not_exists(
        "lead_attachments",
        sa.Column("mime_type", sa.String(length=100), nullable=True),
    )


def downgrade() -> None:
    drop_column_if_exists("lead_attachments", "mime_type")
    drop_column_if_exists("lead_attachments", "file_size")