"""Add auditable lead lifecycle fields.

Revision ID: h1c2d3e4f5a6
Revises: h1c4d5e6f7a8
"""

import sqlalchemy as sa
from alembic import op

revision = "h1c2d3e4f5a6"
down_revision = "h1c4d5e6f7a8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("leads", sa.Column("qualification_reason", sa.Text(), nullable=True))
    op.add_column("leads", sa.Column("qualified_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("leads", sa.Column("qualified_by", sa.String(), nullable=True))
    op.add_column("leads", sa.Column("disqualified_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("leads", sa.Column("disqualified_by", sa.String(), nullable=True))
    op.add_column("leads", sa.Column("converted_by", sa.String(), nullable=True))
    op.add_column("leads", sa.Column("next_follow_up_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("leads", sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("lead_activities", sa.Column("details", sa.Text(), nullable=True))
    op.create_foreign_key(
        "fk_leads_qualified_by_users", "leads", "users", ["qualified_by"], ["id"], ondelete="SET NULL"
    )
    op.create_foreign_key(
        "fk_leads_disqualified_by_users", "leads", "users", ["disqualified_by"], ["id"], ondelete="SET NULL"
    )
    op.create_foreign_key(
        "fk_leads_converted_by_users", "leads", "users", ["converted_by"], ["id"], ondelete="SET NULL"
    )
    op.create_index("ix_leads_next_follow_up_at", "leads", ["next_follow_up_at"])
    op.create_index(
        "ix_leads_org_active_created",
        "leads",
        ["organization_id", "is_archived", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_leads_org_active_created", table_name="leads")
    op.drop_index("ix_leads_next_follow_up_at", table_name="leads")
    op.drop_constraint("fk_leads_converted_by_users", "leads", type_="foreignkey")
    op.drop_constraint("fk_leads_disqualified_by_users", "leads", type_="foreignkey")
    op.drop_constraint("fk_leads_qualified_by_users", "leads", type_="foreignkey")
    op.drop_column("lead_activities", "details")
    op.drop_column("leads", "archived_at")
    op.drop_column("leads", "next_follow_up_at")
    op.drop_column("leads", "converted_by")
    op.drop_column("leads", "disqualified_by")
    op.drop_column("leads", "disqualified_at")
    op.drop_column("leads", "qualified_by")
    op.drop_column("leads", "qualified_at")
    op.drop_column("leads", "qualification_reason")
