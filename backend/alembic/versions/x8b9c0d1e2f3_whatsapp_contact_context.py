"""Persist bounded WhatsApp contact-context query plans."""

import sqlalchemy as sa
from alembic import op

revision = "x8b9c0d1e2f3"
down_revision = "w7a8b9c0d1e2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("whatsapp_messages", sa.Column("ai_query_plan", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("whatsapp_messages", "ai_query_plan")
