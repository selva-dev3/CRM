"""Allow tasks without a due date."""

import sqlalchemy as sa
from alembic import op


revision = "c9e0f1a2b3c4"
down_revision = "c9d8e7f6a5b4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "tasks",
        "due_date",
        existing_type=sa.DateTime(timezone=True),
        nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "tasks",
        "due_date",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
    )
