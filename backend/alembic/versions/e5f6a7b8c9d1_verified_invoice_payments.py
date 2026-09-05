"""Persist verified full invoice payments and Stripe checkout identity."""

import sqlalchemy as sa
from alembic import op

revision = "e5f6a7b8c9d1"
down_revision = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("invoices", sa.Column("stripe_checkout_generation", sa.Integer(), server_default="0", nullable=False))
    op.add_column("invoices", sa.Column("stripe_checkout_session_id", sa.String(255), nullable=True))
    op.create_unique_constraint("uq_invoice_checkout_session", "invoices", ["stripe_checkout_session_id"])
    op.create_table("payments",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("organization_id", sa.String(), sa.ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("invoice_id", sa.String(), sa.ForeignKey("invoices.id", ondelete="RESTRICT"), nullable=False, unique=True),
        sa.Column("provider", sa.String(30), nullable=False),
        sa.Column("provider_payment_id", sa.String(255), nullable=False),
        sa.Column("checkout_session_id", sa.String(255), nullable=False, unique=True),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.String(10), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("provider", "provider_payment_id", name="uq_payment_provider_id"),
    )
    op.create_index("ix_payments_organization_id", "payments", ["organization_id"])


def downgrade() -> None:
    # Do not discard payment evidence during a rollback of deployed software.
    if op.get_bind().execute(sa.text("SELECT EXISTS (SELECT 1 FROM payments)")).scalar():
        raise RuntimeError("Cannot downgrade while verified payment records exist")
    op.drop_table("payments")
    op.drop_constraint("uq_invoice_checkout_session", "invoices", type_="unique")
    op.drop_column("invoices", "stripe_checkout_session_id")
    op.drop_column("invoices", "stripe_checkout_generation")
