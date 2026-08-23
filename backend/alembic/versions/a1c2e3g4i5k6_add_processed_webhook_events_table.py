"""add processed webhook events table

Revision ID: a1c2e3g4i5k6
Revises: f9a0b1c2d3e4
Create Date: 2026-08-23 20:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a1c2e3g4i5k6"
down_revision: Union[str, Sequence[str], None] = "f9a0b1c2d3e4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create processed_webhook_events table if missing (idempotent)
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if "processed_webhook_events" not in tables:
        op.create_table(
            "processed_webhook_events",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("event_id", sa.String(255), nullable=False),
            sa.Column("event_type", sa.String(100), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.create_index(
            "ix_processed_webhook_events_event_id",
            "processed_webhook_events",
            ["event_id"],
            unique=True,
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if "processed_webhook_events" in tables:
        op.drop_index("ix_processed_webhook_events_event_id", table_name="processed_webhook_events")
        op.drop_table("processed_webhook_events")
