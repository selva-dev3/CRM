"""Add claimed_until to scheduled_reports for scheduler claim/finalize.

The delivery sweep previously held ``FOR UPDATE`` row locks across CSV
generation, S3 upload and the Brevo HTTP call; the first per-schedule
commit released the locks on every remaining due row so concurrent sweeps
could deliver the same schedule twice. This column is a persistent claim
marker: Phase A sets it in a short transaction, Phase B does all network
work lock-free, Phase C clears/advances guarded on the exact claim token.

Revision ID: d5e6f7a8b9c0
Revises: b1c2d3e4f5a6
Create Date: 2026-08-25
"""

import sqlalchemy as sa
from alembic import op

revision = "d5e6f7a8b9c0"
down_revision = "b1c2d3e4f5a6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "scheduled_reports",
        sa.Column("claimed_until", sa.DateTime(timezone=True), nullable=True),
    )
    # Plain index on next_run: the sweep's due scan filters next_run first.
    # NOTE: a PARTIAL index ("WHERE claimed_until IS NULL OR
    # claimed_until < now()") is not possible here — now() is volatile and
    # PostgreSQL rejects functions that are not IMMUTABLE in index
    # predicates, and SQLite has no now(). The claimability filter stays in
    # the sweep's WHERE clause; this index just keeps the next_run scan cheap.
    op.create_index(
        "ix_scheduled_reports_claimable",
        "scheduled_reports",
        ["next_run"],
    )


def downgrade() -> None:
    op.drop_index("ix_scheduled_reports_claimable", table_name="scheduled_reports")
    op.drop_column("scheduled_reports", "claimed_until")
