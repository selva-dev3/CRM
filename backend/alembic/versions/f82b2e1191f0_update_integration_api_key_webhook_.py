"""update integration api key webhook models

Revision ID: f82b2e1191f0
Revises: 7999f13a9ce6
Create Date: 2026-08-07 06:23:06.780755
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision: str = "f82b2e1191f0"
down_revision: Union[str, Sequence[str], None] = "7999f13a9ce6"
branch_labels = None
depends_on = None


def upgrade() -> None:

    # ==========================
    # API KEYS
    # ==========================

    op.add_column(
        "api_keys",
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.add_column(
        "api_keys",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    # ==========================
    # INTEGRATIONS
    # ==========================

    # Add nullable first
    op.add_column(
        "integrations",
        sa.Column("provider", sa.String(50), nullable=True),
    )

    op.add_column(
        "integrations",
        sa.Column("webhook_url", sa.Text(), nullable=True),
    )

    op.add_column(
        "integrations",
        sa.Column("credentials", sa.Text(), nullable=True),
    )

    op.add_column(
        "integrations",
        sa.Column("status", sa.String(30), nullable=True),
    )

    op.add_column(
        "integrations",
        sa.Column("last_error", sa.Text(), nullable=True),
    )

    op.add_column(
        "integrations",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    # Fill existing rows
    op.execute("""
        UPDATE integrations
        SET provider='mailchimp'
        WHERE provider IS NULL;
    """)

    op.execute("""
        UPDATE integrations
        SET status='connected'
        WHERE status IS NULL;
    """)

    # Make NOT NULL
    op.alter_column(
        "integrations",
        "provider",
        nullable=False,
    )

    op.alter_column(
        "integrations",
        "status",
        nullable=False,
    )

    op.create_index(
        op.f("ix_integrations_provider"),
        "integrations",
        ["provider"],
        unique=False,
    )

    # ==========================
    # WEBHOOKS
    # ==========================

    op.add_column(
        "webhooks",
        sa.Column("name", sa.String(100), nullable=True),
    )

    op.add_column(
        "webhooks",
        sa.Column(
            "last_triggered_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    op.add_column(
        "webhooks",
        sa.Column(
            "failure_count",
            sa.Integer(),
            nullable=True,
        ),
    )

    op.add_column(
        "webhooks",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    # Existing rows update
    op.execute("""
        UPDATE webhooks
        SET name='Webhook'
        WHERE name IS NULL;
    """)

    op.execute("""
        UPDATE webhooks
        SET failure_count=0
        WHERE failure_count IS NULL;
    """)

    # Make NOT NULL
    op.alter_column(
        "webhooks",
        "name",
        nullable=False,
    )

    op.alter_column(
        "webhooks",
        "failure_count",
        nullable=False,
    )


def downgrade() -> None:

    op.drop_column("webhooks", "updated_at")
    op.drop_column("webhooks", "failure_count")
    op.drop_column("webhooks", "last_triggered_at")
    op.drop_column("webhooks", "name")

    op.drop_index(
        op.f("ix_integrations_provider"),
        table_name="integrations",
    )

    op.drop_column("integrations", "updated_at")
    op.drop_column("integrations", "last_error")
    op.drop_column("integrations", "status")
    op.drop_column("integrations", "credentials")
    op.drop_column("integrations", "webhook_url")
    op.drop_column("integrations", "provider")

    op.drop_column("api_keys", "updated_at")
    op.drop_column("api_keys", "expires_at")