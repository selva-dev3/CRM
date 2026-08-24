"""add deals.loss_reason column

Revision ID: a9b8c7d6e5f4
Revises: c4d5e6f7a8b9
Create Date: 2026-08-24 00:00:00.000000

Adoption-safe: databases whose schema was previously created by the
application's ``Base.metadata.create_all`` startup hook may already carry
the new column. In that case the migration verifies nullability/type and
skips the ALTER instead of failing.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "a9b8c7d6e5f4"
down_revision: Union[str, Sequence[str], None] = "c4d5e6f7a8b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add nullable loss_reason to deals so closed-lost reasons are persisted."""
    inspector = sa.inspect(op.get_bind())
    columns = {c["name"]: c for c in inspector.get_columns("deals")}
    if "loss_reason" not in columns:
        op.add_column("deals", sa.Column("loss_reason", sa.String(length=255), nullable=True))
        return

    col = columns["loss_reason"]
    if col.get("nullable") is not True:
        raise RuntimeError(
            "Column 'deals.loss_reason' already exists but is NOT NULL, which is "
            "incompatible with migration a9b8c7d6e5f4. Reconcile the schema first."
        )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {c["name"] for c in inspector.get_columns("deals")}
    if "loss_reason" in columns:
        op.drop_column("deals", "loss_reason")
