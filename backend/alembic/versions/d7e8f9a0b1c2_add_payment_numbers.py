"""Add human-readable organization-scoped payment numbers."""

import sqlalchemy as sa
from alembic import op

revision = "d7e8f9a0b1c2"
down_revision = "c7e8f9a0b1d2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "organizations",
        sa.Column("payment_prefix", sa.String(20), server_default="PAY", nullable=False),
    )
    op.add_column(
        "organizations",
        sa.Column("payment_sequence", sa.BigInteger(), server_default="0", nullable=False),
    )
    op.add_column("payments", sa.Column("payment_number", sa.String(100), nullable=True))

    op.execute(
        sa.text(
            """
            WITH numbered AS (
                SELECT
                    p.id,
                    COALESCE(o.payment_prefix, 'PAY') || '-' ||
                    EXTRACT(YEAR FROM p.paid_at)::text || '-' ||
                    LPAD(
                        ROW_NUMBER() OVER (
                            PARTITION BY p.organization_id
                            ORDER BY p.paid_at, p.id
                        )::text,
                        6,
                        '0'
                    ) AS payment_number
                FROM payments p
                JOIN organizations o ON o.id = p.organization_id
            )
            UPDATE payments AS p
            SET payment_number = numbered.payment_number
            FROM numbered
            WHERE p.id = numbered.id
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE organizations AS o
            SET payment_sequence = (
                SELECT COUNT(*)
                FROM payments AS p
                WHERE p.organization_id = o.id
            )
            """
        )
    )
    op.alter_column("payments", "payment_number", nullable=False)
    op.create_unique_constraint(
        "uq_payments_org_number", "payments", ["organization_id", "payment_number"]
    )


def downgrade() -> None:
    if op.get_bind().execute(sa.text("SELECT EXISTS (SELECT 1 FROM payments)")).scalar():
        raise RuntimeError("Cannot downgrade while verified payment records exist")
    op.drop_constraint("uq_payments_org_number", "payments", type_="unique")
    op.drop_column("payments", "payment_number")
    op.drop_column("organizations", "payment_sequence")
    op.drop_column("organizations", "payment_prefix")
