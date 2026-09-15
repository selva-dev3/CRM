"""Add durable organization-scoped storage reconciliation findings."""

import sqlalchemy as sa
from alembic import op

revision = "k8b9c0d1e2f3"
down_revision = "j7f9b1d3e5a6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "storage_reconciliations",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("object_key", sa.String(length=1024), nullable=False),
        sa.Column("bucket", sa.String(length=255), nullable=False),
        sa.Column("endpoint", sa.String(length=500), nullable=False),
        sa.Column("finding", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id", "object_key", "finding", name="uq_storage_reconciliation"
        ),
    )
    op.create_index(
        "ix_storage_reconciliations_organization_id",
        "storage_reconciliations",
        ["organization_id"],
    )
    op.create_index(
        "ix_storage_reconciliations_org_status",
        "storage_reconciliations",
        ["organization_id", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_storage_reconciliations_org_status", table_name="storage_reconciliations")
    op.drop_index(
        "ix_storage_reconciliations_organization_id", table_name="storage_reconciliations"
    )
    op.drop_table("storage_reconciliations")
