"""add custom field values to core CRM entities

Revision ID: f0a1b2c3d4e5
Revises: e8f9a0b1c2d3
Create Date: 2026-09-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f0a1b2c3d4e5"
down_revision: str | Sequence[str] | None = "e8f9a0b1c2d3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for table_name in ("leads", "contacts", "companies"):
        op.add_column(
            table_name,
            sa.Column(
                "custom_fields",
                sa.JSON(),
                nullable=False,
                server_default=sa.text("'{}'"),
            ),
        )

    op.execute("""
        UPDATE custom_fields
        SET entity_type = CASE LOWER(TRIM(entity_type))
            WHEN 'lead' THEN 'Lead'
            WHEN 'contact' THEN 'Contact'
            WHEN 'company' THEN 'Company'
            WHEN 'deal' THEN 'Deal'
            ELSE entity_type
        END
        """)


def downgrade() -> None:
    for table_name in ("companies", "contacts", "leads"):
        op.drop_column(table_name, "custom_fields")
