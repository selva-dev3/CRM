"""add checkout_session_id to subscriptions

Revision ID: a2b3c4d5e6f7
Revises: a1c2e3g4i5k6
Create Date: 2026-08-23 21:26:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a2b3c4d5e6f7"
down_revision: Union[str, Sequence[str], None] = "a1c2e3g4i5k6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if "organization_subscriptions" in tables:
        columns = [c["name"] for c in inspector.get_columns("organization_subscriptions")]
        if "checkout_session_id" not in columns:
            op.add_column(
                "organization_subscriptions",
                sa.Column("checkout_session_id", sa.String(255), nullable=True),
            )
            op.create_index(
                "ix_organization_subscriptions_checkout_session_id",
                "organization_subscriptions",
                ["checkout_session_id"],
                unique=False,
            )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if "organization_subscriptions" in tables:
        columns = [c["name"] for c in inspector.get_columns("organization_subscriptions")]
        if "checkout_session_id" in columns:
            op.drop_index(
                "ix_organization_subscriptions_checkout_session_id",
                table_name="organization_subscriptions",
            )
            op.drop_column("organization_subscriptions", "checkout_session_id")
