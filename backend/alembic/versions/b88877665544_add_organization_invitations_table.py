"""add organization invitations table

Revision ID: b88877665544
Revises: d48af9dea957
Create Date: 2026-08-06 16:00:00.000000
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "b88877665544"
down_revision: Union[str, Sequence[str], None] = "d48af9dea957"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if "organization_invitations" not in inspector.get_table_names():
        op.create_table(
            "organization_invitations",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column(
                "organization_id",
                sa.String(),
                sa.ForeignKey("organizations.id", ondelete="CASCADE"),
                nullable=False,
                index=True,
            ),
            sa.Column("email", sa.String(length=255), nullable=False, index=True),
            sa.Column("full_name", sa.String(length=255), nullable=True),
            sa.Column("role_id", sa.String(length=100), server_default="Admin", nullable=True),
            sa.Column("subscription_id", sa.String(), nullable=True),
            sa.Column("token", sa.String(length=255), nullable=False, unique=True, index=True),
            sa.Column("status", sa.String(length=50), server_default="Pending", nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=True,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=True,
            ),
        )

def downgrade() -> None:
    op.drop_table("organization_invitations")
