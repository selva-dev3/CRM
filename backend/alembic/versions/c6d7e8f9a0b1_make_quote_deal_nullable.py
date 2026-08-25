"""make quote deal linkage nullable and preserve quotes on deal deletion

Revision ID: c6d7e8f9a0b1
Revises: b5c6d7e8f9a0
Create Date: 2026-08-25 18:00:00.000000

Adoption-safe for databases whose Quote tables were created through
``Base.metadata.create_all``. Existing rows are never rewritten or deleted.
"""

import logging
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect, text

revision: str = "c6d7e8f9a0b1"
down_revision: str | Sequence[str] | None = "b5c6d7e8f9a0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE_NAME = "quotes"
COLUMN_NAME = "deal_id"
FK_NAME = "fk_quotes_deal_id_deals"
INDEX_NAME = "ix_quotes_deal_id"

logger = logging.getLogger("alembic.runtime")


def _deal_foreign_keys(inspector: sa.engine.reflection.Inspector) -> list[dict]:
    return [
        foreign_key
        for foreign_key in inspector.get_foreign_keys(TABLE_NAME)
        if foreign_key.get("constrained_columns") == [COLUMN_NAME]
        and foreign_key.get("referred_table") == "deals"
        and foreign_key.get("referred_columns") == ["id"]
    ]


def _has_orphaned_deal_ids(bind: sa.engine.Connection) -> bool:
    return (
        bind.execute(
            text(
                "SELECT 1 FROM quotes AS q "
                "LEFT JOIN deals AS d ON d.id = q.deal_id "
                "WHERE q.deal_id IS NOT NULL AND d.id IS NULL LIMIT 1"
            )
        ).first()
        is not None
    )


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if TABLE_NAME not in inspector.get_table_names():
        logger.warning("Skipping Quote deal migration: quotes table does not exist")
        return

    columns = {column["name"]: column for column in inspector.get_columns(TABLE_NAME)}
    if COLUMN_NAME not in columns:
        op.add_column(
            TABLE_NAME,
            sa.Column(COLUMN_NAME, sa.String(), nullable=True),
        )
    elif not columns[COLUMN_NAME].get("nullable", True):
        op.alter_column(
            TABLE_NAME,
            COLUMN_NAME,
            existing_type=columns[COLUMN_NAME]["type"],
            nullable=True,
        )

    foreign_keys = _deal_foreign_keys(inspector)
    valid_foreign_keys = [
        foreign_key
        for foreign_key in foreign_keys
        if (foreign_key.get("options") or {}).get("ondelete", "").upper() == "SET NULL"
    ]
    invalid_foreign_keys = [
        foreign_key for foreign_key in foreign_keys if foreign_key not in valid_foreign_keys
    ]

    if invalid_foreign_keys or not valid_foreign_keys:
        if _has_orphaned_deal_ids(bind):
            raise RuntimeError(
                "Cannot enforce quotes.deal_id foreign key: orphaned Deal IDs exist; "
                "resolve them without deleting Quote records before retrying"
            )
        for foreign_key in invalid_foreign_keys:
            constraint_name = foreign_key.get("name")
            if not constraint_name:
                raise RuntimeError("Cannot safely replace unnamed quotes.deal_id foreign key")
            op.drop_constraint(constraint_name, TABLE_NAME, type_="foreignkey")
        if not valid_foreign_keys:
            op.create_foreign_key(
                FK_NAME,
                TABLE_NAME,
                "deals",
                [COLUMN_NAME],
                ["id"],
                ondelete="SET NULL",
            )

    indexes = inspector.get_indexes(TABLE_NAME)
    if not any(index.get("column_names") == [COLUMN_NAME] for index in indexes):
        op.create_index(INDEX_NAME, TABLE_NAME, [COLUMN_NAME], unique=False)


def downgrade() -> None:
    """Keep the nullable linkage because reverting it can invalidate legacy data."""
    logger.warning("Quote deal nullability migration is intentionally non-destructive on downgrade")
