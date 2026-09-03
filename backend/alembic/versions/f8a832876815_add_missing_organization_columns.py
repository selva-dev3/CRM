"""add missing organization columns

Revision ID: f8a832876815
Revises: 7fcd8359c9f2
Create Date: 2026-08-03 21:43:19.408591
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = "f8a832876815"
down_revision: Union[str, Sequence[str], None] = "8a1b2c3d4e5f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def add_column_if_not_exists(table_name: str, column: sa.Column):
    bind = op.get_bind()
    try:
        inspector = inspect(bind)
        existing_columns = {c["name"] for c in inspector.get_columns(table_name)}
        if column.name not in existing_columns:
            op.add_column(table_name, column)
    except Exception:
        op.add_column(table_name, column)


def drop_column_if_exists(table_name: str, column_name: str):
    bind = op.get_bind()
    try:
        inspector = inspect(bind)
        existing_columns = {c["name"] for c in inspector.get_columns(table_name)}
        if column_name in existing_columns:
            op.drop_column(table_name, column_name)
    except Exception:
        op.drop_column(table_name, column_name)


def upgrade() -> None:
    """Upgrade schema."""

    # Leads
    add_column_if_not_exists("leads", sa.Column("website", sa.String(length=255), nullable=True))
    add_column_if_not_exists("leads", sa.Column("industry", sa.String(length=100), nullable=True))
    add_column_if_not_exists("leads", sa.Column("company_size", sa.String(length=50), nullable=True))
    add_column_if_not_exists("leads", sa.Column("country", sa.String(length=100), nullable=True))
    add_column_if_not_exists("leads", sa.Column("state", sa.String(length=100), nullable=True))
    add_column_if_not_exists("leads", sa.Column("city", sa.String(length=100), nullable=True))
    add_column_if_not_exists("leads", sa.Column("address", sa.String(length=255), nullable=True))
    add_column_if_not_exists("leads", sa.Column("postal_code", sa.String(length=20), nullable=True))

    # Organizations
    add_column_if_not_exists("organizations", sa.Column("slug", sa.String(length=255), nullable=True))
    add_column_if_not_exists("organizations", sa.Column("email", sa.String(length=255), nullable=True))
    add_column_if_not_exists("organizations", sa.Column("phone", sa.String(length=100), nullable=True))
    add_column_if_not_exists("organizations", sa.Column("website", sa.String(length=255), nullable=True))
    add_column_if_not_exists("organizations", sa.Column("industry", sa.String(length=100), nullable=True))
    add_column_if_not_exists("organizations", sa.Column("company_size", sa.String(length=100), nullable=True))
    add_column_if_not_exists("organizations", sa.Column("country", sa.String(length=100), nullable=True))
    add_column_if_not_exists("organizations", sa.Column("state", sa.String(length=100), nullable=True))
    add_column_if_not_exists("organizations", sa.Column("city", sa.String(length=100), nullable=True))
    add_column_if_not_exists("organizations", sa.Column("address", sa.String(length=500), nullable=True))
    add_column_if_not_exists("organizations", sa.Column("postal_code", sa.String(length=50), nullable=True))
    add_column_if_not_exists("organizations", sa.Column("timezone", sa.String(length=100), nullable=True))
    add_column_if_not_exists("organizations", sa.Column("currency", sa.String(length=10), nullable=True))
    add_column_if_not_exists("organizations", sa.Column("language", sa.String(length=10), nullable=True))
    add_column_if_not_exists("organizations", sa.Column("logo_url", sa.String(length=500), nullable=True))
    add_column_if_not_exists("organizations", sa.Column("tax_number", sa.String(length=100), nullable=True))
    add_column_if_not_exists("organizations", sa.Column("registration_number", sa.String(length=100), nullable=True))
    add_column_if_not_exists("organizations", sa.Column("status", sa.String(length=50), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""

    drop_column_if_exists("organizations", "status")
    drop_column_if_exists("organizations", "registration_number")
    drop_column_if_exists("organizations", "tax_number")
    drop_column_if_exists("organizations", "logo_url")
    drop_column_if_exists("organizations", "language")
    drop_column_if_exists("organizations", "currency")
    drop_column_if_exists("organizations", "timezone")
    drop_column_if_exists("organizations", "postal_code")
    drop_column_if_exists("organizations", "address")
    drop_column_if_exists("organizations", "city")
    drop_column_if_exists("organizations", "state")
    drop_column_if_exists("organizations", "country")
    drop_column_if_exists("organizations", "company_size")
    drop_column_if_exists("organizations", "industry")
    drop_column_if_exists("organizations", "website")
    drop_column_if_exists("organizations", "phone")
    drop_column_if_exists("organizations", "email")
    drop_column_if_exists("organizations", "slug")

    drop_column_if_exists("leads", "postal_code")
    drop_column_if_exists("leads", "address")
    drop_column_if_exists("leads", "city")
    drop_column_if_exists("leads", "state")
    drop_column_if_exists("leads", "country")
    drop_column_if_exists("leads", "company_size")
    drop_column_if_exists("leads", "industry")
    drop_column_if_exists("leads", "website")
