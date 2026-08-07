"""update integration api key webhook models

Revision ID: 9de65214d93a
Revises: f82b2e1191f0
Create Date: 2026-08-07 06:44:54.241894
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "9de65214d93a"
down_revision: Union[str, Sequence[str], None] = "f82b2e1191f0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    # ==========================================================
    # API KEYS
    # ==========================================================

    op.add_column(
        "api_keys",
        sa.Column("description", sa.Text(), nullable=True)
    )

    op.add_column(
        "api_keys",
        sa.Column("created_by", sa.String(), nullable=True)
    )

    op.add_column(
        "api_keys",
        sa.Column(
            "usage_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        )
    )

    op.create_foreign_key(
        "fk_api_keys_created_by",
        "api_keys",
        "users",
        ["created_by"],
        ["id"],
        ondelete="SET NULL",
    )

    # ==========================================================
    # INTEGRATIONS
    # ==========================================================

    op.add_column(
        "integrations",
        sa.Column("external_id", sa.String(255), nullable=True)
    )

    op.add_column(
        "integrations",
        sa.Column("enabled_events", sa.Text(), nullable=True)
    )

    op.add_column(
        "integrations",
        sa.Column(
            "sync_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        )
    )

    # ==========================================================
    # WEBHOOKS
    # ==========================================================

    op.add_column(
        "webhooks",
        sa.Column(
            "method",
            sa.String(10),
            nullable=False,
            server_default="POST",
        )
    )

    op.add_column(
        "webhooks",
        sa.Column(
            "content_type",
            sa.String(100),
            nullable=False,
            server_default="application/json",
        )
    )

    op.add_column(
        "webhooks",
        sa.Column("headers", sa.Text(), nullable=True)
    )

    op.add_column(
        "webhooks",
        sa.Column(
            "timeout_seconds",
            sa.Integer(),
            nullable=False,
            server_default="30",
        )
    )

    op.add_column(
        "webhooks",
        sa.Column(
            "retry_count",
            sa.Integer(),
            nullable=False,
            server_default="3",
        )
    )

    op.add_column(
        "webhooks",
        sa.Column("last_status_code", sa.Integer(), nullable=True)
    )

    op.add_column(
        "webhooks",
        sa.Column("last_response", sa.Text(), nullable=True)
    )


def downgrade() -> None:
    """Downgrade schema."""

    op.drop_column("webhooks", "last_response")
    op.drop_column("webhooks", "last_status_code")
    op.drop_column("webhooks", "retry_count")
    op.drop_column("webhooks", "timeout_seconds")
    op.drop_column("webhooks", "headers")
    op.drop_column("webhooks", "content_type")
    op.drop_column("webhooks", "method")

    op.drop_column("integrations", "sync_enabled")
    op.drop_column("integrations", "enabled_events")
    op.drop_column("integrations", "external_id")

    op.drop_constraint(
        "fk_api_keys_created_by",
        "api_keys",
        type_="foreignkey",
    )

    op.drop_column("api_keys", "usage_count")
    op.drop_column("api_keys", "created_by")
    op.drop_column("api_keys", "description")