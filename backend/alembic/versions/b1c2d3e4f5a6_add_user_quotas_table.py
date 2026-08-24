"""add user_quotas table (per-user sales quota targets)

Revision ID: b1c2d3e4f5a6
Revises: a9b8c7d6e5f4
Create Date: 2026-08-24 00:00:00.000000

Adoption-safe: databases whose schema was previously created by the
application's ``Base.metadata.create_all`` startup hook already contain
this table outside Alembic; for those the migration verifies structure
and skips re-creation (same approach as migration b3c4d5e6f7a8).
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "b1c2d3e4f5a6"
down_revision: Union[str, Sequence[str], None] = "a9b8c7d6e5f4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_USER_QUOTAS_COLUMNS = {
    "id",
    "organization_id",
    "user_id",
    "target_amount",
    "created_at",
    "updated_at",
}


def _verify_existing_table(inspector: sa.engine.reflection.Inspector) -> None:
    columns = {c["name"] for c in inspector.get_columns("user_quotas")}
    missing = _USER_QUOTAS_COLUMNS - columns
    if missing:
        raise RuntimeError(
            f"Table 'user_quotas' already exists but is missing columns "
            f"{sorted(missing)} expected by migration b1c2d3e4f5a6."
        )

    pk = inspector.get_pk_constraint("user_quotas")
    if "id" not in (pk.get("constrained_columns") or []):
        raise RuntimeError("Table 'user_quotas' already exists but has no primary key on 'id'.")

    fk_targets = {
        (tuple(fk.get("constrained_columns") or ()), fk.get("referred_table"))
        for fk in inspector.get_foreign_keys("user_quotas")
    }
    for constrained, referred in [(("organization_id",), "organizations"), (("user_id",), "users")]:
        if (constrained, referred) not in fk_targets:
            raise RuntimeError(
                f"Table 'user_quotas' already exists but is missing foreign key "
                f"{'/'.join(constrained)} -> {referred}(id)."
            )


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    existing = set(inspector.get_table_names())

    if "user_quotas" not in existing:
        op.create_table(
            "user_quotas",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column(
                "organization_id",
                sa.String(),
                sa.ForeignKey("organizations.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "user_id",
                sa.String(),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("target_amount", sa.Float(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
        )
        op.create_index(
            op.f("ix_user_quotas_organization_id"), "user_quotas", ["organization_id"], unique=False
        )
        op.create_index(op.f("ix_user_quotas_user_id"), "user_quotas", ["user_id"], unique=True)
    else:
        _verify_existing_table(inspector)


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    existing = set(inspector.get_table_names())
    if "user_quotas" in existing:
        index_names = {idx["name"] for idx in inspector.get_indexes("user_quotas")}
        if op.f("ix_user_quotas_user_id") in index_names:
            op.drop_index(op.f("ix_user_quotas_user_id"), table_name="user_quotas")
        if op.f("ix_user_quotas_organization_id") in index_names:
            op.drop_index(op.f("ix_user_quotas_organization_id"), table_name="user_quotas")
        op.drop_table("user_quotas")
