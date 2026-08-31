"""add password resets table

Revision ID: e1f2a3b4c5d6
Revises: c6d7e8f9a0b1
Create Date: 2026-08-31 00:00:00.000000

Adoption-safe for development databases where ``Base.metadata.create_all``
already created the table.
"""

from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "e1f2a3b4c5d6"
down_revision: str | Sequence[str] | None = "c6d7e8f9a0b1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "password_resets" in inspector.get_table_names():
        return

    op.create_table(
        "password_resets",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("token", sa.String(length=255), nullable=False),
        sa.Column("is_used", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token", name="uq_password_resets_token"),
    )
    op.create_index("ix_password_resets_user_id", "password_resets", ["user_id"])
    op.create_index("ix_password_resets_token", "password_resets", ["token"], unique=True)


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "password_resets" in inspector.get_table_names():
        op.drop_table("password_resets")
