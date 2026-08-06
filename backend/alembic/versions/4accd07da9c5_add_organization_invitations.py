"""add organization invitations

Revision ID: 4accd07da9c5
Revises: b88877665544
Create Date: 2026-08-06 10:43:45.391438
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "4accd07da9c5"
down_revision: Union[str, Sequence[str], None] = "b88877665544"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Upgrade schema.

    This migration only finalizes the organization_invitations table.
    No changes should be made to organization_subscriptions here.
    """

    op.alter_column(
        "organization_invitations",
        "created_at",
        existing_type=postgresql.TIMESTAMP(timezone=True),
        nullable=False,
        existing_server_default=sa.text("now()"),
    )

    op.alter_column(
        "organization_invitations",
        "updated_at",
        existing_type=postgresql.TIMESTAMP(timezone=True),
        nullable=False,
        existing_server_default=sa.text("now()"),
    )


def downgrade() -> None:
    """
    Downgrade schema.
    """

    op.alter_column(
        "organization_invitations",
        "updated_at",
        existing_type=postgresql.TIMESTAMP(timezone=True),
        nullable=True,
        existing_server_default=sa.text("now()"),
    )

    op.alter_column(
        "organization_invitations",
        "created_at",
        existing_type=postgresql.TIMESTAMP(timezone=True),
        nullable=True,
        existing_server_default=sa.text("now()"),
    )