"""Preserve business history when users are removed and scope product SKUs.

Revision ID: e2a4c6d8f0b1
Revises: d0e1f2a3b4c5
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e2a4c6d8f0b1"
down_revision: str | None = "d0e1f2a3b4c5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PRESERVED_USER_REFERENCES = (
    ("deals", "assigned_to"),
    ("tasks", "assigned_to"),
    ("task_comments", "user_id"),
    ("documents", "uploaded_by"),
    ("lead_notes", "created_by"),
    ("notes", "created_by"),
    ("ticket_comments", "user_id"),
    ("report_exports", "requested_by"),
    ("activity_logs", "user_id"),
)


def _replace_user_fk(table: str, column: str, *, ondelete: str) -> None:
    constraint = f"{table}_{column}_fkey"
    op.drop_constraint(constraint, table, type_="foreignkey")
    op.create_foreign_key(constraint, table, "users", [column], ["id"], ondelete=ondelete)


def upgrade() -> None:
    op.drop_index("ix_products_sku", table_name="products")
    op.create_index("uq_products_org_sku", "products", ["organization_id", "sku"], unique=True)
    op.alter_column(
        "products",
        "price",
        existing_type=sa.Float(),
        type_=sa.Numeric(14, 2),
        existing_nullable=False,
        postgresql_using="round(price::numeric, 2)",
    )
    for table, column in _PRESERVED_USER_REFERENCES:
        op.alter_column(table, column, existing_type=sa.String(), nullable=True)
        _replace_user_fk(table, column, ondelete="SET NULL")


def downgrade() -> None:
    duplicate = op.get_bind().execute(
        sa.text("SELECT sku FROM products GROUP BY sku HAVING count(*) > 1 LIMIT 1")
    ).scalar_one_or_none()
    if duplicate is not None:
        raise RuntimeError(
            "Cannot restore global SKU uniqueness while multiple organizations "
            f"use SKU {duplicate!r}"
        )
    op.drop_index("uq_products_org_sku", table_name="products")
    op.create_index("ix_products_sku", "products", ["sku"], unique=True)
    op.alter_column(
        "products",
        "price",
        existing_type=sa.Numeric(14, 2),
        type_=sa.Float(),
        existing_nullable=False,
        postgresql_using="price::double precision",
    )
    for table, column in reversed(_PRESERVED_USER_REFERENCES):
        _replace_user_fk(table, column, ondelete="CASCADE")
