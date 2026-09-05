"""Add authoritative deal close timestamps and stage history.

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d1e2f3
"""

import sqlalchemy as sa
from alembic import op

revision = "b8c9d0e1f2a3"
down_revision = "a7b8c9d1e2f3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("deals", sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_deals_closed_at", "deals", ["closed_at"], unique=False)
    op.execute("""
        UPDATE deals
        SET closed_at = updated_at
        WHERE stage IN ('Closed Won', 'Closed Lost') AND closed_at IS NULL
        """)

    op.create_table(
        "deal_stage_history",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("deal_id", sa.String(), nullable=False),
        sa.Column("stage", sa.String(length=100), nullable=False),
        sa.Column(
            "entered_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("exited_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("actor_id", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(
            ["actor_id"],
            ["users.id"],
            name="fk_deal_stage_history_actor_id_users",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["deal_id"],
            ["deals.id"],
            name="fk_deal_stage_history_deal_id_deals",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_deal_stage_history_organization_id_organizations",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_deal_stage_history_organization_id",
        "deal_stage_history",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        "ix_deal_stage_history_deal_id",
        "deal_stage_history",
        ["deal_id"],
        unique=False,
    )
    op.create_index(
        "ix_deal_stage_history_stage",
        "deal_stage_history",
        ["stage"],
        unique=False,
    )
    op.create_index(
        "ix_deal_stage_history_entered_at",
        "deal_stage_history",
        ["entered_at"],
        unique=False,
    )
    op.create_index(
        "ix_deal_stage_history_exited_at",
        "deal_stage_history",
        ["exited_at"],
        unique=False,
    )
    op.create_index(
        "ix_deal_stage_history_actor_id",
        "deal_stage_history",
        ["actor_id"],
        unique=False,
    )
    op.create_index(
        "uq_deal_stage_history_current",
        "deal_stage_history",
        ["deal_id"],
        unique=True,
        postgresql_where=sa.text("exited_at IS NULL"),
    )
    op.execute("""
        INSERT INTO deal_stage_history
            (id, organization_id, deal_id, stage, entered_at, exited_at, actor_id)
        SELECT
            md5(random()::text || clock_timestamp()::text || id),
            organization_id,
            id,
            stage,
            COALESCE(closed_at, created_at),
            NULL,
            NULL
        FROM deals
        """)


def downgrade() -> None:
    op.drop_index("uq_deal_stage_history_current", table_name="deal_stage_history")
    op.drop_index("ix_deal_stage_history_actor_id", table_name="deal_stage_history")
    op.drop_index("ix_deal_stage_history_exited_at", table_name="deal_stage_history")
    op.drop_index("ix_deal_stage_history_entered_at", table_name="deal_stage_history")
    op.drop_index("ix_deal_stage_history_stage", table_name="deal_stage_history")
    op.drop_index("ix_deal_stage_history_deal_id", table_name="deal_stage_history")
    op.drop_index("ix_deal_stage_history_organization_id", table_name="deal_stage_history")
    op.drop_table("deal_stage_history")
    op.drop_index("ix_deals_closed_at", table_name="deals")
    op.drop_column("deals", "closed_at")
