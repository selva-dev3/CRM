"""Enforce case-insensitive product category names within an organization.

Revision ID: i6e8a0b2c4d5
Revises: h5d7f9a1c3e4
"""

import sqlalchemy as sa
from alembic import op

revision = "i6e8a0b2c4d5"
down_revision = "h5d7f9a1c3e4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1
                    FROM product_categories
                    GROUP BY organization_id, lower(btrim(name))
                    HAVING count(*) > 1
                ) THEN
                    RAISE EXCEPTION 'Duplicate product category names require manual resolution before migration';
                END IF;
            END $$
            """
        )
    )
    op.create_index(
        "uq_product_categories_org_lower_name",
        "product_categories",
        ["organization_id", sa.text("lower(btrim(name))")],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_product_categories_org_lower_name", table_name="product_categories")
