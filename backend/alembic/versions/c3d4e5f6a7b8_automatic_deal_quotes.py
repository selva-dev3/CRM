"""Track automatic quotes and immutable financial line snapshots."""

import sqlalchemy as sa
from alembic import op

revision = "c3d4e5f6a7b8"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Fail instead of deleting or inventing product references for legacy orphan lines.
    op.create_foreign_key("fk_deal_products_product_id", "deal_products", "products",
                          ["product_id"], ["id"], ondelete="RESTRICT")
    for table, column in (("quotes", "total_amount"), ("quote_items", "unit_price"),
                          ("deal_products", "unit_price")):
        op.alter_column(table, column, type_=sa.Numeric(14, 2), existing_type=sa.Float(),
                        postgresql_using=f"{column}::numeric(14, 2)")
    for foreign_key in sa.inspect(op.get_bind()).get_foreign_keys("quote_items"):
        if foreign_key["constrained_columns"] == ["product_id"]:
            op.drop_constraint(foreign_key["name"], "quote_items", type_="foreignkey")
    op.alter_column("quote_items", "product_id", nullable=True, existing_type=sa.String())
    op.create_foreign_key("fk_quote_items_product_id", "quote_items", "products",
                          ["product_id"], ["id"], ondelete="SET NULL")
    for column, target in (("automatic_deal_id", "deals"), ("company_id", "companies"),
                           ("contact_id", "contacts")):
        op.add_column("quotes", sa.Column(column, sa.String(), nullable=True))
        op.create_foreign_key(f"fk_quotes_{column}", "quotes", target,
                              [column], ["id"], ondelete="RESTRICT")
    op.create_unique_constraint("uq_quotes_automatic_deal_id", "quotes", ["automatic_deal_id"])
    op.add_column("quotes", sa.Column("currency", sa.String(10), nullable=True))
    for table in ("deal_products", "quote_items"):
        op.add_column(table, sa.Column("product_name", sa.String(255), nullable=True))
        for column in ("discount_percent", "tax_percent"):
            op.add_column(table, sa.Column(column, sa.Numeric(5, 2), nullable=False, server_default="0"))
    for column in ("subtotal", "discount_total", "tax_total", "total"):
        op.add_column("quote_items", sa.Column(column, sa.Numeric(14, 2), nullable=True))


def downgrade() -> None:
    # A downgrade cannot restore deleted product references; refuse rather than lose history.
    op.alter_column("quote_items", "product_id", nullable=False, existing_type=sa.String())
    op.drop_constraint("fk_quote_items_product_id", "quote_items", type_="foreignkey")
    op.create_foreign_key("quote_items_product_id_fkey", "quote_items", "products",
                          ["product_id"], ["id"], ondelete="CASCADE")
    op.drop_constraint("fk_deal_products_product_id", "deal_products", type_="foreignkey")
    for table, column in (("quotes", "total_amount"), ("quote_items", "unit_price"),
                          ("deal_products", "unit_price")):
        op.alter_column(table, column, type_=sa.Float(), existing_type=sa.Numeric(14, 2))
    for column in ("total", "tax_total", "discount_total", "subtotal"):
        op.drop_column("quote_items", column)
    for table in ("quote_items", "deal_products"):
        for column in ("tax_percent", "discount_percent", "product_name"):
            op.drop_column(table, column)
    op.drop_column("quotes", "currency")
    op.drop_constraint("uq_quotes_automatic_deal_id", "quotes", type_="unique")
    for column in ("contact_id", "company_id", "automatic_deal_id"):
        op.drop_constraint(f"fk_quotes_{column}", "quotes", type_="foreignkey")
        op.drop_column("quotes", column)
