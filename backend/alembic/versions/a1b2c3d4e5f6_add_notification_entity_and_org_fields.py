"""add notification entity and org fields

Revision ID: a1b2c3d4e5f6
Revises: 783722adecd6
Create Date: 2026-08-17 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "783722adecd6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add organization, event, and entity fields to notifications."""
    op.add_column(
        "notifications",
        sa.Column(
            "organization_id",
            sa.String(),
            nullable=True,
        ),
    )
    op.add_column(
        "notifications",
        sa.Column("event_name", sa.String(100), nullable=True),
    )
    op.add_column(
        "notifications",
        sa.Column("entity_type", sa.String(50), nullable=True),
    )
    op.add_column(
        "notifications",
        sa.Column("entity_id", sa.String(), nullable=True),
    )
    op.add_column(
        "notifications",
        sa.Column("payload", sa.Text(), nullable=True),
    )
    op.add_column(
        "notifications",
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "notifications",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=True,
        ),
    )

    op.create_index("ix_notifications_organization_id", "notifications", ["organization_id"])
    op.create_index("ix_notifications_event_name", "notifications", ["event_name"])
    op.create_index("ix_notifications_entity_type", "notifications", ["entity_type"])
    op.create_index("ix_notifications_entity_id", "notifications", ["entity_id"])

    op.create_foreign_key(
        "fk_notifications_organization_id",
        "notifications",
        "organizations",
        ["organization_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    """Remove notification entity and org fields."""
    op.drop_constraint("fk_notifications_organization_id", "notifications", type_="foreignkey")
    op.drop_index("ix_notifications_entity_id", table_name="notifications")
    op.drop_index("ix_notifications_entity_type", table_name="notifications")
    op.drop_index("ix_notifications_event_name", table_name="notifications")
    op.drop_index("ix_notifications_organization_id", table_name="notifications")
    op.drop_column("notifications", "updated_at")
    op.drop_column("notifications", "read_at")
    op.drop_column("notifications", "payload")
    op.drop_column("notifications", "entity_id")
    op.drop_column("notifications", "entity_type")
    op.drop_column("notifications", "event_name")
    op.drop_column("notifications", "organization_id")
