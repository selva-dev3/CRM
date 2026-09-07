"""Use Free as the database default for new organizations.

Revision ID: o8d9e0f1a2b3
Revises: n7c8d9e0f1a2
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "o8d9e0f1a2b3"
down_revision: str | None = "n7c8d9e0f1a2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "organizations",
        "plan",
        existing_type=sa.String(length=100),
        server_default="Free",
        existing_nullable=False,
    )
    op.alter_column(
        "organizations",
        "max_users",
        existing_type=sa.Integer(),
        server_default="3",
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "organizations",
        "max_users",
        existing_type=sa.Integer(),
        server_default=None,
        existing_nullable=False,
    )
    op.alter_column(
        "organizations",
        "plan",
        existing_type=sa.String(length=100),
        server_default=None,
        existing_nullable=False,
    )
