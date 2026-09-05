"""persist refresh-session preference

Revision ID: c7e8f9a0b1d2
Revises: f2b3c4d5e6f7
"""

import sqlalchemy as sa
from alembic import op

revision = "c7e8f9a0b1d2"
down_revision = "f2b3c4d5e6f7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "refresh_tokens",
        sa.Column("is_persistent", sa.Boolean(), nullable=False, server_default=sa.true()),
    )


def downgrade() -> None:
    op.drop_column("refresh_tokens", "is_persistent")
