"""Archive gateway evidence and introduce explicit manual invoice lifecycle.

Historical financial rows are never synthesized, renumbered, or deleted.
"""

import sqlalchemy as sa
from alembic import op

revision = "e8f1a2b3c4d5"
down_revision = "d7e8f9a0b1c2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    invalid = connection.execute(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM invoices WHERE status IS NULL OR status NOT IN ('Draft','Pending','Overdue','Paid'))"
        )
    ).scalar()
    if invalid:
        raise RuntimeError("Unknown legacy invoice status: review historical data before migration")
    invalid_payments = connection.execute(
        sa.text("SELECT EXISTS (SELECT 1 FROM payments WHERE amount <= 0 OR amount::text = 'NaN')")
    ).scalar()
    if invalid_payments:
        raise RuntimeError("Non-positive or invalid legacy payment amount: review before migration")
    inconsistent = connection.execute(sa.text("""
        SELECT EXISTS (
            SELECT 1 FROM payments p LEFT JOIN invoices i ON i.id = p.invoice_id
            WHERE i.id IS NULL OR p.organization_id <> i.organization_id OR p.currency <> i.currency
        ) OR EXISTS (
            SELECT 1 FROM invoices i WHERE i.paid_amount IS NULL OR i.amount IS NULL
            OR i.amount::text = 'NaN' OR i.paid_amount::text = 'NaN'
            OR i.amount < 0 OR i.paid_amount < 0 OR i.paid_amount > i.amount
            OR i.paid_amount <> COALESCE((SELECT SUM(p.amount) FROM payments p
                WHERE p.invoice_id = i.id AND p.organization_id = i.organization_id
                AND p.status = 'Succeeded'), 0)
        )
    """)).scalar()
    if inconsistent:
        raise RuntimeError(
            "Historical payment balances, organization or currency mismatch: operator reconciliation required"
        )
    for column in (
        sa.Column("legacy_provider_data", sa.JSON()),
        sa.Column("payment_status", sa.String(30), nullable=False, server_default="Pending"),
        sa.Column("finalized_at", sa.DateTime(timezone=True)),
        sa.Column("finalized_by", sa.String(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("accepted_at", sa.DateTime(timezone=True)),
        sa.Column("public_token_hash", sa.String(64)),
        sa.Column("public_token_expires_at", sa.DateTime(timezone=True)),
    ):
        op.add_column("invoices", column)
    op.create_index("ix_invoices_finalized_by", "invoices", ["finalized_by"])
    op.create_unique_constraint("uq_invoices_public_token_hash", "invoices", ["public_token_hash"])
    op.execute(sa.text("""
        UPDATE invoices SET legacy_provider_data = json_build_object(
            'legacy_archive', true, 'status', status, 'paid_amount', paid_amount,
            'stripe_checkout_url', stripe_checkout_url,
            'stripe_checkout_session_id', stripe_checkout_session_id,
            'stripe_checkout_generation', stripe_checkout_generation,
            'delivery_status', delivery_status, 'delivery_id', delivery_id,
            'delivery_claimed_at', delivery_claimed_at
        ), payment_status = CASE WHEN paid_amount >= amount AND paid_amount > 0 THEN 'Paid'
            WHEN paid_amount > 0 THEN 'Partially Paid' ELSE 'Pending' END,
        status = 'Draft', delivery_status = CASE WHEN delivery_status IN ('Pending','Processing')
            THEN NULL ELSE delivery_status END, delivery_claimed_at = NULL
    """))
    for column in (
        "stripe_checkout_url",
        "stripe_checkout_session_id",
        "stripe_checkout_generation",
    ):
        op.drop_column("invoices", column)
    for column in (
        sa.Column("legacy_provider_data", sa.JSON()),
        sa.Column("payment_type", sa.String(30)),
        sa.Column("payment_date", sa.Date()),
        sa.Column("notes", sa.Text()),
        sa.Column("idempotency_key", sa.String(128)),
        sa.Column("request_hash", sa.String(64)),
        sa.Column("recorded_by", sa.String(), sa.ForeignKey("users.id", ondelete="SET NULL")),
    ):
        op.add_column("payments", column)
    op.execute(sa.text("""
        UPDATE payments SET legacy_provider_data = json_build_object(
            'legacy_archive', true, 'provider', provider, 'provider_payment_id', provider_payment_id,
            'checkout_session_id', checkout_session_id, 'provider_event_id', provider_event_id,
            'payment_method', payment_method
        ), payment_type = 'Legacy', payment_date = (paid_at AT TIME ZONE 'UTC')::date
    """))
    # Constraint names on historical installs may be database-generated.
    for constraint in sa.inspect(connection).get_unique_constraints("payments"):
        if set(constraint["column_names"]) in (
            {"invoice_id"},
            {"provider", "provider_payment_id"},
            {"checkout_session_id"},
            {"provider_event_id"},
        ):
            op.drop_constraint(constraint["name"], "payments", type_="unique")
    for column in ("provider", "provider_payment_id", "checkout_session_id", "provider_event_id"):
        op.drop_column("payments", column)
    op.alter_column("payments", "payment_type", nullable=False)
    op.alter_column("payments", "payment_date", nullable=False)
    op.create_index("ix_payments_invoice_id", "payments", ["invoice_id"])
    op.create_index("ix_payments_recorded_by", "payments", ["recorded_by"])
    op.create_unique_constraint(
        "uq_payment_invoice_idempotency",
        "payments",
        ["organization_id", "invoice_id", "idempotency_key"],
    )
    op.create_check_constraint(
        "ck_payments_positive_amount", "payments", "amount > 0 AND amount <= 999999999999.99"
    )
    op.create_check_constraint(
        "ck_payments_type",
        "payments",
        "payment_type IN ('Cash','Bank Transfer','UPI','Cheque','Card','Other','Legacy')",
    )
    op.create_check_constraint(
        "ck_invoices_lifecycle",
        "invoices",
        "status IN ('Draft','Finalized','Accepted','Cancelled')",
    )
    op.create_check_constraint(
        "ck_invoices_payment_status",
        "invoices",
        "payment_status IN ('Pending','Partially Paid','Paid')",
    )
    op.add_column("organization_subscriptions", sa.Column("legacy_provider_data", sa.JSON()))
    op.execute(sa.text("""
        UPDATE organization_subscriptions SET legacy_provider_data = json_build_object(
            'checkout_session_id', checkout_session_id, 'payment_provider', payment_provider,
            'payment_method', payment_method, 'customer_id', customer_id,
            'subscription_id', subscription_id, 'invoice_id', invoice_id
        )
    """))
    op.drop_column("organization_subscriptions", "checkout_session_id")
    op.alter_column("organization_subscriptions", "payment_provider", server_default=None)


def downgrade() -> None:
    raise RuntimeError(
        "Manual billing migration is forward-only; archived financial evidence must be preserved"
    )
