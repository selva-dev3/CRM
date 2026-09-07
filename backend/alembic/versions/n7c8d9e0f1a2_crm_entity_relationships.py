"""Add organization-safe CRM entity relationships to activities and documents.

Revision ID: n7c8d9e0f1a2
Revises: m6b7c8d9e0f1
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "n7c8d9e0f1a2"
down_revision: str | Sequence[str] | None = "m6b7c8d9e0f1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CRM_TARGETS = {
    "lead": "leads",
    "contact": "contacts",
    "company": "companies",
    "deal": "deals",
}
NOTE_BACKFILLS = (
    "UPDATE notes SET lead_id = entity_id WHERE lower(entity_type) = 'lead' AND EXISTS (SELECT 1 FROM leads WHERE leads.id = notes.entity_id AND leads.organization_id = notes.organization_id)",
    "UPDATE notes SET contact_id = entity_id WHERE lower(entity_type) = 'contact' AND EXISTS (SELECT 1 FROM contacts WHERE contacts.id = notes.entity_id AND contacts.organization_id = notes.organization_id)",
    "UPDATE notes SET company_id = entity_id WHERE lower(entity_type) = 'company' AND EXISTS (SELECT 1 FROM companies WHERE companies.id = notes.entity_id AND companies.organization_id = notes.organization_id)",
    "UPDATE notes SET deal_id = entity_id WHERE lower(entity_type) = 'deal' AND EXISTS (SELECT 1 FROM deals WHERE deals.id = notes.entity_id AND deals.organization_id = notes.organization_id)",
)


def _add_links(table: str, targets: dict[str, str]) -> None:
    for name, target in targets.items():
        column = f"{name}_id"
        op.add_column(table, sa.Column(column, sa.String(), nullable=True))
        op.create_foreign_key(
            f"fk_{table}_{column}_{target}", table, target, [column], ["id"], ondelete="SET NULL"
        )
        op.create_index(f"ix_{table}_{column}", table, [column])


def _drop_links(table: str, targets: dict[str, str]) -> None:
    for name, target in reversed(tuple(targets.items())):
        column = f"{name}_id"
        op.drop_index(f"ix_{table}_{column}", table_name=table)
        op.drop_constraint(f"fk_{table}_{column}_{target}", table, type_="foreignkey")
        op.drop_column(table, column)


def upgrade() -> None:
    op.add_column("meetings", sa.Column("location", sa.String(length=500)))
    op.add_column(
        "meetings",
        sa.Column("status", sa.String(length=50), nullable=False, server_default="Scheduled"),
    )
    op.create_index("ix_meetings_status", "meetings", ["status"])
    _add_links("tasks", CRM_TARGETS)
    _add_links("meetings", CRM_TARGETS)
    _add_links("notes", CRM_TARGETS)
    _add_links(
        "documents",
        {**CRM_TARGETS, "quote": "quotes", "invoice": "invoices", "payment": "payments"},
    )
    _add_links("emails", {"contact": "contacts", "company": "companies", "deal": "deals"})
    _add_links("call_logs", {"lead": "leads", "company": "companies", "deal": "deals"})
    op.drop_constraint("call_logs_contact_id_fkey", "call_logs", type_="foreignkey")
    op.alter_column("call_logs", "contact_id", existing_type=sa.String(), nullable=True)
    op.create_foreign_key(
        "fk_call_logs_contact_id_contacts",
        "call_logs",
        "contacts",
        ["contact_id"],
        ["id"],
        ondelete="SET NULL",
    )
    for statement in NOTE_BACKFILLS:
        op.execute(statement)


def downgrade() -> None:
    op.drop_constraint("fk_call_logs_contact_id_contacts", "call_logs", type_="foreignkey")
    op.alter_column("call_logs", "contact_id", existing_type=sa.String(), nullable=False)
    op.create_foreign_key(
        "call_logs_contact_id_fkey",
        "call_logs",
        "contacts",
        ["contact_id"],
        ["id"],
        ondelete="CASCADE",
    )
    _drop_links("call_logs", {"lead": "leads", "company": "companies", "deal": "deals"})
    _drop_links("emails", {"contact": "contacts", "company": "companies", "deal": "deals"})
    _drop_links(
        "documents",
        {**CRM_TARGETS, "quote": "quotes", "invoice": "invoices", "payment": "payments"},
    )
    _drop_links("notes", CRM_TARGETS)
    _drop_links("meetings", CRM_TARGETS)
    _drop_links("tasks", CRM_TARGETS)
    op.drop_index("ix_meetings_status", table_name="meetings")
    op.drop_column("meetings", "status")
    op.drop_column("meetings", "location")
