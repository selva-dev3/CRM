"""Add explicit quote and invoice internal review metadata.

Revision ID: m6b7c8d9e0f1
Revises: l5a6b7c8d9e0
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "m6b7c8d9e0f1"
down_revision: str | Sequence[str] | None = "l5a6b7c8d9e0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("quotes", sa.Column("review_submitted_at", sa.DateTime(timezone=True)))
    op.add_column("quotes", sa.Column("review_submitted_by", sa.String()))
    op.add_column("quotes", sa.Column("review_rejection_reason", sa.String(length=500)))
    op.create_foreign_key(
        "fk_quotes_review_submitted_by_users",
        "quotes",
        "users",
        ["review_submitted_by"],
        ["id"],
        ondelete="SET NULL",
    )

    op.add_column("invoices", sa.Column("review_submitted_at", sa.DateTime(timezone=True)))
    op.add_column("invoices", sa.Column("review_submitted_by", sa.String()))
    op.add_column("invoices", sa.Column("review_rejection_reason", sa.String(length=500)))
    op.create_foreign_key(
        "fk_invoices_review_submitted_by_users",
        "invoices",
        "users",
        ["review_submitted_by"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_invoices_review_submitted_by", "invoices", ["review_submitted_by"])
    op.drop_constraint("ck_invoices_lifecycle", "invoices", type_="check")
    op.create_check_constraint(
        "ck_invoices_lifecycle",
        "invoices",
        "status IN ('Draft','In Review','Finalized','Accepted','Cancelled')",
    )


def downgrade() -> None:
    op.execute("UPDATE invoices SET status = 'Draft' WHERE status = 'In Review'")
    op.drop_constraint("ck_invoices_lifecycle", "invoices", type_="check")
    op.create_check_constraint(
        "ck_invoices_lifecycle",
        "invoices",
        "status IN ('Draft','Finalized','Accepted','Cancelled')",
    )
    op.drop_index("ix_invoices_review_submitted_by", table_name="invoices")
    op.drop_constraint(
        "fk_invoices_review_submitted_by_users", "invoices", type_="foreignkey"
    )
    op.drop_column("invoices", "review_rejection_reason")
    op.drop_column("invoices", "review_submitted_by")
    op.drop_column("invoices", "review_submitted_at")

    op.drop_constraint("fk_quotes_review_submitted_by_users", "quotes", type_="foreignkey")
    op.drop_column("quotes", "review_rejection_reason")
    op.drop_column("quotes", "review_submitted_by")
    op.drop_column("quotes", "review_submitted_at")
