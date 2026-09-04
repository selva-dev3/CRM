"""add deal custom field values

Revision ID: d6e7f8a9b0c1
Revises: c3d4e5f6a7b9
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d6e7f8a9b0c1"
down_revision: str | Sequence[str] | None = "c3d4e5f6a7b9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "custom_fields",
        sa.Column("options", sa.JSON(), server_default=sa.text("'[]'"), nullable=False),
    )
    op.add_column(
        "deals",
        sa.Column("custom_fields", sa.JSON(), server_default=sa.text("'{}'"), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("deals", "custom_fields")
    op.drop_column("custom_fields", "options")
