"""Persist real lead conversion links without fabricating legacy conversions."""

import sqlalchemy as sa
from alembic import op

revision = "b2c3d4e5f6a7"
down_revision = "b2c3d4e5f6a8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for entity in ("company", "contact", "deal"):
        table = "companies" if entity == "company" else f"{entity}s"
        column = f"converted_{entity}_id"
        op.add_column("leads", sa.Column(column, sa.String(), nullable=True))
        op.create_foreign_key(f"fk_leads_{column}", "leads", table,
                              [column], ["id"], ondelete="RESTRICT")
    op.add_column("leads", sa.Column("converted_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("leads", "converted_at")
    for entity in ("deal", "contact", "company"):
        column = f"converted_{entity}_id"
        op.drop_constraint(f"fk_leads_{column}", "leads", type_="foreignkey")
        op.drop_column("leads", column)
