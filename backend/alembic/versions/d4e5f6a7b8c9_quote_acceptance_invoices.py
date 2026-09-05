"""Separate approval and acceptance; protect automatic invoice identity and money."""

import sqlalchemy as sa
from alembic import op

revision = "d4e5f6a7b8c9"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for column in ("approved_at", "sent_at", "accepted_at", "expires_at"):
        op.add_column("quotes", sa.Column(column, sa.DateTime(timezone=True), nullable=True))
    op.add_column("quotes", sa.Column("approved_by", sa.String(), nullable=True))
    op.create_foreign_key("fk_quotes_approved_by", "quotes", "users", ["approved_by"], ["id"], ondelete="SET NULL")
    op.add_column("quotes", sa.Column("accepted_by", sa.String(255), nullable=True))
    op.add_column("quotes", sa.Column("public_token_hash", sa.String(64), nullable=True))
    op.create_unique_constraint("uq_quotes_public_token", "quotes", ["public_token_hash"])
    op.add_column("organizations", sa.Column("invoice_prefix", sa.String(20), server_default="INV", nullable=False))
    op.add_column("organizations", sa.Column("invoice_sequence", sa.BigInteger(), server_default="0", nullable=False))
    op.add_column("invoices", sa.Column("billing_snapshot", sa.JSON(), nullable=True))
    inspector = sa.inspect(op.get_bind())
    for constraint in inspector.get_unique_constraints("invoices"):
        if constraint["column_names"] == ["invoice_number"]:
            op.drop_constraint(constraint["name"], "invoices", type_="unique")
    for index in inspector.get_indexes("invoices"):
        if index["column_names"] == ["invoice_number"] and index["unique"] and not index.get("duplicates_constraint"):
            op.drop_index(index["name"], table_name="invoices")
    op.create_unique_constraint("uq_invoices_org_number", "invoices", ["organization_id", "invoice_number"])
    op.create_unique_constraint("uq_invoices_org_quote", "invoices", ["organization_id", "quote_id"])
    for column in ("amount", "subtotal", "discount_total", "tax_total", "paid_amount"):
        op.alter_column("invoices", column, type_=sa.Numeric(14, 2), existing_type=sa.Float(),
                        postgresql_using=f"{column}::numeric(14, 2)")
    for column in ("unit_price", "discount_percent", "tax_percent"):
        numeric = sa.Numeric(14, 2) if column == "unit_price" else sa.Numeric(5, 2)
        op.alter_column("invoice_items", column, type_=numeric, existing_type=sa.Float())
    for key in inspector.get_foreign_keys("invoice_items"):
        if key["constrained_columns"] == ["product_id"]:
            op.drop_constraint(key["name"], "invoice_items", type_="foreignkey")
    op.alter_column("invoice_items", "product_id", nullable=True, existing_type=sa.String())
    op.create_foreign_key("fk_invoice_items_product_id", "invoice_items", "products",
                          ["product_id"], ["id"], ondelete="SET NULL")


def downgrade() -> None:
    # Refuse if historical null references or overlapping tenant numbers cannot be represented.
    op.alter_column("invoice_items", "product_id", nullable=False, existing_type=sa.String())
    op.drop_constraint("fk_invoice_items_product_id", "invoice_items", type_="foreignkey")
    op.create_foreign_key("invoice_items_product_id_fkey", "invoice_items", "products",
                          ["product_id"], ["id"], ondelete="CASCADE")
    for column in ("unit_price", "discount_percent", "tax_percent"):
        op.alter_column("invoice_items", column, type_=sa.Float())
    for column in ("amount", "subtotal", "discount_total", "tax_total", "paid_amount"):
        op.alter_column("invoices", column, type_=sa.Float())
    op.create_unique_constraint("invoices_invoice_number_key", "invoices", ["invoice_number"])
    op.drop_constraint("uq_invoices_org_quote", "invoices", type_="unique")
    op.drop_constraint("uq_invoices_org_number", "invoices", type_="unique")
    op.drop_column("invoices", "billing_snapshot")
    op.drop_column("organizations", "invoice_sequence")
    op.drop_column("organizations", "invoice_prefix")
    op.drop_constraint("uq_quotes_public_token", "quotes", type_="unique")
    op.drop_constraint("fk_quotes_approved_by", "quotes", type_="foreignkey")
    for column in ("public_token_hash", "accepted_by", "approved_by", "expires_at",
                   "accepted_at", "sent_at", "approved_at"):
        op.drop_column("quotes", column)
