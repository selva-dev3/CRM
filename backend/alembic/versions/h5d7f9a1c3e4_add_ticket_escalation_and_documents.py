"""Add ticket escalation metadata and canonical ticket documents.

Revision ID: h5d7f9a1c3e4
Revises: g4c6e8f0b2d3
"""

import sqlalchemy as sa
from alembic import op

revision = "h5d7f9a1c3e4"
down_revision = "g4c6e8f0b2d3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tickets", sa.Column("escalated_at", sa.DateTime(timezone=True)))
    op.add_column("tickets", sa.Column("escalated_by", sa.String()))
    op.add_column("tickets", sa.Column("escalation_reason", sa.String(length=500)))
    op.create_foreign_key(
        "fk_tickets_escalated_by_users",
        "tickets",
        "users",
        ["escalated_by"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_tickets_escalated_at", "tickets", ["escalated_at"])

    op.add_column("documents", sa.Column("ticket_id", sa.String()))
    op.create_foreign_key(
        "fk_documents_ticket_id_tickets",
        "documents",
        "tickets",
        ["ticket_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_documents_ticket_id", "documents", ["ticket_id"])


def downgrade() -> None:
    contains_business_data = op.get_bind().execute(
        sa.text(
            "SELECT EXISTS ("
            "SELECT 1 FROM tickets "
            "WHERE escalated_at IS NOT NULL "
            "OR escalated_by IS NOT NULL "
            "OR escalation_reason IS NOT NULL"
            ") OR EXISTS (SELECT 1 FROM documents WHERE ticket_id IS NOT NULL)"
        )
    ).scalar_one()
    if contains_business_data:
        raise RuntimeError(
            "Cannot downgrade ticket escalation/documents while business data exists"
        )
    op.drop_index("ix_documents_ticket_id", table_name="documents")
    op.drop_constraint("fk_documents_ticket_id_tickets", "documents", type_="foreignkey")
    op.drop_column("documents", "ticket_id")
    op.drop_index("ix_tickets_escalated_at", table_name="tickets")
    op.drop_constraint("fk_tickets_escalated_by_users", "tickets", type_="foreignkey")
    op.drop_column("tickets", "escalation_reason")
    op.drop_column("tickets", "escalated_by")
    op.drop_column("tickets", "escalated_at")
