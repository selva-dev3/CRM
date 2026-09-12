"""Add project delivery and sales order entities."""

import sqlalchemy as sa
from alembic import op

revision = "p1r2o3j4s5f6"
down_revision = "z0d1e2f3g4h5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "organizations",
        sa.Column("order_prefix", sa.String(20), nullable=False, server_default="ORD"),
    )
    op.add_column(
        "organizations",
        sa.Column("order_sequence", sa.BigInteger(), nullable=False, server_default="0"),
    )

    op.create_table(
        "project_milestones",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("project_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("status", sa.String(30), nullable=False, server_default="Pending"),
        sa.Column("due_date", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint(
            "status IN ('Pending','In Progress','Completed','Cancelled')",
            name="ck_project_milestones_status",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_project_milestones_organization_id", "project_milestones", ["organization_id"]
    )
    op.create_index("ix_project_milestones_project_id", "project_milestones", ["project_id"])
    op.create_index("ix_project_milestones_due_date", "project_milestones", ["due_date"])

    op.create_table(
        "price_books",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "name", name="uq_price_books_org_name"),
    )
    op.create_index("ix_price_books_organization_id", "price_books", ["organization_id"])
    op.create_index(
        "uq_price_books_org_default",
        "price_books",
        ["organization_id"],
        unique=True,
        postgresql_where=sa.text("is_default"),
    )
    op.create_table(
        "price_book_entries",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("price_book_id", sa.String(), nullable=False),
        sa.Column("product_id", sa.String(), nullable=False),
        sa.Column("unit_price", sa.Numeric(14, 2), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["price_book_id"], ["price_books.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("price_book_id", "product_id", name="uq_price_book_entries_product"),
    )
    op.create_index("ix_price_book_entries_price_book_id", "price_book_entries", ["price_book_id"])
    op.create_index("ix_price_book_entries_product_id", "price_book_entries", ["product_id"])

    op.create_table(
        "sales_orders",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("quote_id", sa.String(), nullable=False),
        sa.Column("deal_id", sa.String()),
        sa.Column("company_id", sa.String()),
        sa.Column("contact_id", sa.String()),
        sa.Column("order_number", sa.String(100), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="Confirmed"),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("subtotal", sa.Numeric(14, 2), nullable=False),
        sa.Column("discount_total", sa.Numeric(14, 2), nullable=False),
        sa.Column("tax_total", sa.Numeric(14, 2), nullable=False),
        sa.Column("total", sa.Numeric(14, 2), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fulfilled_at", sa.DateTime(timezone=True)),
        sa.Column("cancelled_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint(
            "status IN ('Confirmed','Fulfilled','Cancelled')", name="ck_sales_orders_status"
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["quote_id"], ["quotes.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["deal_id"], ["deals.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["contact_id"], ["contacts.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "quote_id", name="uq_sales_orders_org_quote"),
        sa.UniqueConstraint("organization_id", "order_number", name="uq_sales_orders_org_number"),
    )
    for column in (
        "organization_id",
        "quote_id",
        "deal_id",
        "company_id",
        "contact_id",
        "order_number",
    ):
        op.create_index(f"ix_sales_orders_{column}", "sales_orders", [column])
    op.create_index(
        "ix_sales_orders_org_status_created",
        "sales_orders",
        ["organization_id", "status", "created_at"],
    )
    op.create_table(
        "sales_order_items",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("order_id", sa.String(), nullable=False),
        sa.Column("product_id", sa.String()),
        sa.Column("product_name", sa.String(255), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.Numeric(14, 2), nullable=False),
        sa.Column("discount_percent", sa.Numeric(5, 2), nullable=False),
        sa.Column("tax_percent", sa.Numeric(5, 2), nullable=False),
        sa.Column("subtotal", sa.Numeric(14, 2), nullable=False),
        sa.Column("discount_total", sa.Numeric(14, 2), nullable=False),
        sa.Column("tax_total", sa.Numeric(14, 2), nullable=False),
        sa.Column("total", sa.Numeric(14, 2), nullable=False),
        sa.ForeignKeyConstraint(["order_id"], ["sales_orders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sales_order_items_order_id", "sales_order_items", ["order_id"])
    op.create_index("ix_sales_order_items_product_id", "sales_order_items", ["product_id"])

    op.add_column("documents", sa.Column("project_id", sa.String(), nullable=True))
    op.create_foreign_key(
        "fk_documents_project_id",
        "documents",
        "projects",
        ["project_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_documents_project_id", "documents", ["project_id"])
    op.add_column("invoices", sa.Column("order_id", sa.String(), nullable=True))
    op.create_foreign_key(
        "fk_invoices_order_id",
        "invoices",
        "sales_orders",
        ["order_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_invoices_order_id", "invoices", ["order_id"], unique=True)

    op.execute("""
        INSERT INTO permissions (id, key, name, category)
        VALUES
          (md5('rbac-permission:orders:read'), 'orders:read', 'orders:read', 'orders'),
          (md5('rbac-permission:orders:create'), 'orders:create', 'orders:create', 'orders'),
          (md5('rbac-permission:orders:update'), 'orders:update', 'orders:update', 'orders')
        ON CONFLICT DO NOTHING
    """)
    op.execute("""
        INSERT INTO role_permissions (id, role_id, permission_id)
        SELECT md5('rbac-role-permission:' || role.id || ':' || permission.id), role.id, permission.id
        FROM roles role CROSS JOIN permissions permission
        WHERE permission.key IN ('orders:read', 'orders:create', 'orders:update')
          AND lower(btrim(role.name)) IN ('admin', 'sales manager', 'sales executive')
        ON CONFLICT DO NOTHING
    """)
    op.execute("""
        INSERT INTO role_permissions (id, role_id, permission_id)
        SELECT md5('rbac-role-permission:' || role.id || ':' || permission.id), role.id, permission.id
        FROM roles role CROSS JOIN permissions permission
        WHERE permission.key = 'orders:read'
          AND lower(btrim(role.name)) IN ('customer support', 'read only')
        ON CONFLICT DO NOTHING
    """)


def downgrade() -> None:
    op.execute(
        "DELETE FROM role_permissions USING permissions WHERE role_permissions.permission_id = permissions.id AND permissions.key LIKE 'orders:%'"
    )
    op.execute("DELETE FROM permissions WHERE key LIKE 'orders:%'")
    op.drop_index("ix_invoices_order_id", table_name="invoices")
    op.drop_constraint("fk_invoices_order_id", "invoices", type_="foreignkey")
    op.drop_column("invoices", "order_id")
    op.drop_index("ix_documents_project_id", table_name="documents")
    op.drop_constraint("fk_documents_project_id", "documents", type_="foreignkey")
    op.drop_column("documents", "project_id")
    op.drop_table("sales_order_items")
    op.drop_table("sales_orders")
    op.drop_table("price_book_entries")
    op.drop_table("price_books")
    op.drop_table("project_milestones")
    op.drop_column("organizations", "order_sequence")
    op.drop_column("organizations", "order_prefix")
