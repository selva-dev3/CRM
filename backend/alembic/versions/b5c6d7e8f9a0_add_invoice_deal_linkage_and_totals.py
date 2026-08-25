"""add invoice-deal linkage, money totals and one-invoice-per-deal uniqueness

Revision ID: b5c6d7e8f9a0
Revises: c4d5e6f7a8b9
Create Date: 2026-08-25 10:00:00.000000

Adoption-safe: databases whose schema was previously created by the
application's ``Base.metadata.create_all`` startup hook (development mode
in ``app/main.py``) may already contain these columns/indexes. Existing
state is inspected first; each DDL step is applied only when missing.
The one-invoice-per-deal unique index is only created when no duplicate
``deal_id`` values exist — financial records are never modified or
deleted by this migration.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect, text

# revision identifiers, used by Alembic.
revision: str = "b5c6d7e8f9a0"
down_revision: str | Sequence[str] | None = "d5e6f7a8b9c0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UNIQUE_INDEX_NAME = "uq_invoices_one_per_deal"


def _add_column_if_not_exists(inspector: sa.engine.reflection.Inspector, table: str, column: sa.Column) -> None:
    if table not in inspector.get_table_names():
        return
    existing_columns = {c["name"] for c in inspector.get_columns(table)}
    if column.name not in existing_columns:
        op.add_column(table, column)


def _upgrade_invoices_columns(inspector: sa.engine.reflection.Inspector) -> None:
    _add_column_if_not_exists(
        inspector,
        "invoices",
        sa.Column("deal_id", sa.String(), sa.ForeignKey("deals.id", ondelete="SET NULL"), nullable=True),
    )
    _add_column_if_not_exists(
        inspector,
        "invoices",
        sa.Column("company_id", sa.String(), sa.ForeignKey("companies.id", ondelete="SET NULL"), nullable=True),
    )
    _add_column_if_not_exists(
        inspector,
        "invoices",
        sa.Column("contact_id", sa.String(), sa.ForeignKey("contacts.id", ondelete="SET NULL"), nullable=True),
    )
    _add_column_if_not_exists(
        inspector,
        "invoices",
        sa.Column("currency", sa.String(length=10), nullable=False, server_default="USD"),
    )
    _add_column_if_not_exists(
        inspector,
        "invoices",
        sa.Column("subtotal", sa.Float(), nullable=False, server_default="0"),
    )
    _add_column_if_not_exists(
        inspector,
        "invoices",
        sa.Column("discount_total", sa.Float(), nullable=False, server_default="0"),
    )
    _add_column_if_not_exists(
        inspector,
        "invoices",
        sa.Column("tax_total", sa.Float(), nullable=False, server_default="0"),
    )
    _add_column_if_not_exists(
        inspector,
        "invoices",
        sa.Column("paid_amount", sa.Float(), nullable=False, server_default="0"),
    )
    _add_column_if_not_exists(inspector, "invoices", sa.Column("notes", sa.Text(), nullable=True))
    _add_column_if_not_exists(
        inspector,
        "invoices",
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
    )


def _upgrade_invoice_items_columns(inspector: sa.engine.reflection.Inspector) -> None:
    _add_column_if_not_exists(
        inspector,
        "invoice_items",
        sa.Column("description", sa.String(length=255), nullable=True),
    )
    _add_column_if_not_exists(
        inspector,
        "invoice_items",
        sa.Column("discount_percent", sa.Float(), nullable=False, server_default="0"),
    )
    _add_column_if_not_exists(
        inspector,
        "invoice_items",
        sa.Column("tax_percent", sa.Float(), nullable=False, server_default="0"),
    )


def _create_unique_index_if_safe() -> bool:
    """Create the partial unique index guarding one active invoice per deal.

    Non-destructive: when legacy rows already contain duplicated ``deal_id``
    values the index is skipped (with a logged warning) instead of failing
    the deploy or touching financial records.
    """
    bind = op.get_bind()
    inspector = inspect(bind)
    if "invoices" not in inspector.get_table_names():
        return False

    index_names = {idx["name"] for idx in inspector.get_indexes("invoices")}
    if UNIQUE_INDEX_NAME in index_names:
        return True

    duplicates = bind.execute(
        text(
            "SELECT deal_id FROM invoices "
            "WHERE deal_id IS NOT NULL "
            "GROUP BY deal_id HAVING COUNT(*) > 1 LIMIT 1"
        )
    ).first()
    if duplicates is not None:
        import logging

        logging.getLogger("alembic.runtime").warning(
            "Skipping %s: invoices table already contains multiple invoices "
            "for at least one deal. Resolve duplicates manually before re-run.",
            UNIQUE_INDEX_NAME,
        )
        return False

    op.create_index(
        UNIQUE_INDEX_NAME,
        "invoices",
        ["deal_id"],
        unique=True,
        postgresql_where=text("deal_id IS NOT NULL"),
        sqlite_where=text("deal_id IS NOT NULL"),
    )
    return True


def upgrade() -> None:
    inspector = inspect(op.get_bind())
    _upgrade_invoices_columns(inspector)
    _upgrade_invoice_items_columns(inspector)
    _create_unique_index_if_safe()


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if "invoices" in inspector.get_table_names():
        index_names = {idx["name"] for idx in inspector.get_indexes("invoices")}
        if UNIQUE_INDEX_NAME in index_names:
            op.drop_index(UNIQUE_INDEX_NAME, table_name="invoices")

        existing_columns = {c["name"] for c in inspector.get_columns("invoices")}
        for column_name in (
            "sent_at",
            "notes",
            "paid_amount",
            "tax_total",
            "discount_total",
            "subtotal",
            "currency",
            "contact_id",
            "company_id",
            "deal_id",
        ):
            if column_name in existing_columns:
                op.drop_column("invoices", column_name)

    if "invoice_items" in inspector.get_table_names():
        item_columns = {c["name"] for c in inspector.get_columns("invoice_items")}
        for column_name in ("tax_percent", "discount_percent", "description"):
            if column_name in item_columns:
                op.drop_column("invoice_items", column_name)
