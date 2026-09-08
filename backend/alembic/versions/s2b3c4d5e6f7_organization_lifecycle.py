"""Organization lifecycle integrity and durable storage cleanup.

Existing identities, names, roles and credentials are never rewritten.
Recovery requires the documented coordinated database/object-storage backup.
"""

import sqlalchemy as sa
from alembic import op

revision = "s2b3c4d5e6f7"
down_revision = "s3c4d5e6f7a8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    if connection.scalar(sa.text("""
        SELECT EXISTS(SELECT 1 FROM organizations
        GROUP BY lower(btrim(name)) HAVING count(*) > 1)
    """)):
        raise RuntimeError("Duplicate organization names require review; no names were changed")
    op.execute(
        "CREATE UNIQUE INDEX uq_organizations_normalized_name ON organizations (lower(btrim(name)))"
    )
    for table in ("user_invitations", "custom_fields", "sla_policies"):
        source = sa.table(table, sa.column("organization_id", sa.String()))
        organizations = sa.table("organizations", sa.column("id", sa.String()))
        orphan = (
            sa.select(source.c.organization_id)
            .where(
                source.c.organization_id.is_not(None),
                ~sa.exists(
                    sa.select(organizations.c.id).where(
                        organizations.c.id == source.c.organization_id
                    )
                ),
            )
            .exists()
        )
        if connection.scalar(sa.select(orphan)):
            raise RuntimeError(
                f"Orphan organization references in {table}; review before migrating"
            )
        op.create_foreign_key(
            f"fk_{table}_organization_id",
            table,
            "organizations",
            ["organization_id"],
            ["id"],
            ondelete="CASCADE",
        )
    op.create_table(
        "organization_deletions",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("organization_id", sa.String(), nullable=False, unique=True),
        sa.Column("organization_name", sa.String(255), nullable=False),
        sa.Column(
            "actor_id", sa.String(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_organization_deletions_actor_id", "organization_deletions", ["actor_id"])
    op.create_table(
        "organization_file_cleanups",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "operation_id",
            sa.String(),
            sa.ForeignKey("organization_deletions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("object_key", sa.String(1024), nullable=False),
        sa.Column("bucket", sa.String(255), nullable=False),
        sa.Column("endpoint", sa.String(500), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("claimed_until", sa.DateTime(timezone=True)),
        sa.Column(
            "next_attempt_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("error_code", sa.String(80)),
        sa.UniqueConstraint("operation_id", "object_key"),
    )
    op.create_index(
        "ix_organization_file_cleanups_operation_id", "organization_file_cleanups", ["operation_id"]
    )
    op.create_index(
        "ix_organization_file_cleanups_status", "organization_file_cleanups", ["status"]
    )


def downgrade() -> None:
    raise RuntimeError("Deletion recovery requires a reviewed database and object-storage restore")
