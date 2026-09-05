"""Persist invoice delivery, reminders, and verified payment receipts."""

import sqlalchemy as sa
from alembic import op

revision = "a7b8c9d1e2f3"
down_revision = "f6a7b8c9d1e2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("ix_quotes_quote_number", table_name="quotes")
    op.create_index("ix_quotes_quote_number", "quotes", ["quote_number"], unique=False)
    op.create_unique_constraint(
        "uq_quotes_org_number", "quotes", ["organization_id", "quote_number"]
    )
    op.add_column("quotes", sa.Column("rejection_reason", sa.String(500), nullable=True))
    op.add_column(
        "organizations",
        sa.Column("quote_prefix", sa.String(20), nullable=False, server_default="QUO"),
    )
    op.add_column(
        "organizations",
        sa.Column("quote_sequence", sa.BigInteger(), nullable=False, server_default="0"),
    )
    for name, length in (
        ("delivery_id", 36),
        ("delivery_status", 30),
        ("recipient_email", 255),
        ("provider_message_id", 255),
        ("pdf_s3_key", 500),
    ):
        op.add_column("invoices", sa.Column(name, sa.String(length), nullable=True))
    op.add_column(
        "invoices", sa.Column("delivery_attempts", sa.Integer(), nullable=False, server_default="0")
    )
    op.add_column(
        "invoices", sa.Column("delivery_claimed_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "invoices", sa.Column("reminder_count", sa.Integer(), nullable=False, server_default="0")
    )
    op.add_column(
        "invoices", sa.Column("last_reminded_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.create_index("ix_invoices_delivery_status", "invoices", ["delivery_status"])

    op.add_column(
        "invoice_items",
        sa.Column("product_name", sa.String(255), nullable=True, server_default="Line item"),
    )
    op.add_column("invoice_items", sa.Column("subtotal", sa.Numeric(14, 2), nullable=True))
    op.add_column("invoice_items", sa.Column("discount_total", sa.Numeric(14, 2), nullable=True))
    op.add_column("invoice_items", sa.Column("tax_total", sa.Numeric(14, 2), nullable=True))
    op.add_column("invoice_items", sa.Column("total", sa.Numeric(14, 2), nullable=True))
    op.execute("UPDATE invoice_items SET product_name = COALESCE(description, 'Line item')")
    for name in ("product_name", "subtotal", "discount_total", "tax_total", "total"):
        op.alter_column(
            "invoice_items",
            name,
            nullable=False,
            server_default="0" if name != "product_name" else "Line item",
        )
    for name in ("subtotal", "discount_total", "tax_total", "total"):
        op.alter_column("invoice_items", name, server_default=None)

    for name, length in (
        ("provider_event_id", 255),
        ("payment_method", 100),
        ("receipt_s3_key", 500),
        ("receipt_delivery_status", 30),
        ("receipt_provider_message_id", 255),
    ):
        op.add_column("payments", sa.Column(name, sa.String(length), nullable=True))
    op.add_column(
        "payments",
        sa.Column("receipt_delivery_attempts", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "payments",
        sa.Column("receipt_delivery_claimed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_unique_constraint("uq_payments_provider_event_id", "payments", ["provider_event_id"])
    op.create_index("ix_payments_receipt_delivery_status", "payments", ["receipt_delivery_status"])


def downgrade() -> None:
    op.drop_index("ix_payments_receipt_delivery_status", table_name="payments")
    op.drop_constraint("uq_payments_provider_event_id", "payments", type_="unique")
    for name in (
        "receipt_delivery_claimed_at",
        "receipt_delivery_attempts",
        "receipt_provider_message_id",
        "receipt_delivery_status",
        "receipt_s3_key",
        "payment_method",
        "provider_event_id",
    ):
        op.drop_column("payments", name)
    op.drop_index("ix_invoices_delivery_status", table_name="invoices")
    for name in (
        "last_reminded_at",
        "reminder_count",
        "delivery_claimed_at",
        "delivery_attempts",
        "pdf_s3_key",
        "provider_message_id",
        "recipient_email",
        "delivery_status",
        "delivery_id",
    ):
        op.drop_column("invoices", name)
    for name in ("total", "tax_total", "discount_total", "subtotal", "product_name"):
        op.drop_column("invoice_items", name)
    op.drop_column("quotes", "rejection_reason")
    op.drop_constraint("uq_quotes_org_number", "quotes", type_="unique")
    op.drop_index("ix_quotes_quote_number", table_name="quotes")
    op.create_index("ix_quotes_quote_number", "quotes", ["quote_number"], unique=True)
    op.drop_column("organizations", "quote_sequence")
    op.drop_column("organizations", "quote_prefix")
