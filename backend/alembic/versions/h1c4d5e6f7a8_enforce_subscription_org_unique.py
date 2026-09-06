"""Enforce one subscription record per organization.

Existing duplicates require explicit provider-aware reconciliation. The
migration refuses to guess which financial record is authoritative.
"""

import sqlalchemy as sa
from alembic import op

revision = "h1c4d5e6f7a8"
down_revision = "g0b3c4d5e6f7"
branch_labels = None
depends_on = None

CONSTRAINT_NAME = "uq_organization_subscriptions_organization_id"


def upgrade() -> None:
    connection = op.get_bind()
    duplicate = connection.execute(sa.text("""
            SELECT organization_id
            FROM organization_subscriptions
            GROUP BY organization_id
            HAVING COUNT(*) > 1
            LIMIT 1
            """)).first()
    if duplicate:
        raise RuntimeError(
            "Duplicate organization subscription records require administrator reconciliation"
        )

    unique_constraints = sa.inspect(connection).get_unique_constraints("organization_subscriptions")
    if not any(
        constraint.get("column_names") == ["organization_id"] for constraint in unique_constraints
    ):
        op.create_unique_constraint(
            CONSTRAINT_NAME,
            "organization_subscriptions",
            ["organization_id"],
        )


def downgrade() -> None:
    raise RuntimeError(
        "Subscription organization uniqueness is forward-only; preserve billing integrity"
    )
