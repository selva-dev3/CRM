"""Connect meetings to calendar and add communication ownership.

Revision ID: f3b5d7e9a1c2
Revises: e2a4c6d8f0b1
"""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f3b5d7e9a1c2"
down_revision: str | None = "e2a4c6d8f0b1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

MODULES = ("calls", "emails", "calendar", "meetings", "notes")
ROLE_DEFAULTS = {
    "admin": "all",
    "sales manager": "team",
    "sales executive": "assigned",
    "marketing executive": "assigned",
    "customer support": "assigned",
    "read only": "all",
    "project manager": "team",
    "project member": "assigned",
    "support manager": "team",
    "finance/accounts": "all",
}


def _stable_id(role_id: str, module: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"crm:record-scope:{role_id}:{module}"))


def upgrade() -> None:
    connection = op.get_bind()
    op.add_column("calendar_events", sa.Column("organization_id", sa.String(), nullable=True))
    connection.execute(
        sa.text(
            """
            UPDATE calendar_events AS event
            SET organization_id = users.organization_id
            FROM users
            WHERE users.id = event.user_id
            """
        )
    )
    orphan = connection.execute(
        sa.text("SELECT id FROM calendar_events WHERE organization_id IS NULL LIMIT 1")
    ).scalar_one_or_none()
    if orphan is not None:
        raise RuntimeError(
            "Calendar tenant backfill failed; event has no owning organization: " + str(orphan)
        )
    op.alter_column("calendar_events", "organization_id", nullable=False)
    op.create_foreign_key(
        "calendar_events_organization_id_fkey",
        "calendar_events",
        "organizations",
        ["organization_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_calendar_events_organization_id", "calendar_events", ["organization_id"]
    )
    op.add_column(
        "calendar_events",
        sa.Column("status", sa.String(length=50), nullable=False, server_default="Scheduled"),
    )
    op.create_index("ix_calendar_events_status", "calendar_events", ["status"])
    op.alter_column("calendar_events", "user_id", existing_type=sa.String(), nullable=True)
    op.drop_constraint("calendar_events_user_id_fkey", "calendar_events", type_="foreignkey")
    op.create_foreign_key(
        "calendar_events_user_id_fkey",
        "calendar_events",
        "users",
        ["user_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.add_column("emails", sa.Column("created_by", sa.String(), nullable=True))
    connection.execute(
        sa.text(
            """
            UPDATE emails AS email
            SET created_by = users.id
            FROM users
            WHERE users.organization_id = email.organization_id
              AND lower(users.email) = lower(email.from_email)
            """
        )
    )
    op.create_foreign_key(
        "emails_created_by_fkey", "emails", "users", ["created_by"], ["id"], ondelete="SET NULL"
    )
    op.create_index("ix_emails_created_by", "emails", ["created_by"])

    op.add_column("meetings", sa.Column("created_by", sa.String(), nullable=True))
    op.create_foreign_key(
        "meetings_created_by_fkey",
        "meetings",
        "users",
        ["created_by"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_meetings_created_by", "meetings", ["created_by"])
    op.add_column("meetings", sa.Column("calendar_event_id", sa.String(), nullable=True))
    op.create_foreign_key(
        "meetings_calendar_event_id_fkey",
        "meetings",
        "calendar_events",
        ["calendar_event_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_meetings_calendar_event_id", "meetings", ["calendar_event_id"], unique=True
    )

    roles = connection.execute(sa.text("SELECT id, lower(trim(name)) FROM roles")).all()
    rows = []
    for role_id, normalized_name in roles:
        default = ROLE_DEFAULTS.get(normalized_name, "none")
        for module in MODULES:
            rows.append(
                {
                    "id": _stable_id(role_id, module),
                    "role_id": role_id,
                    "module": module,
                    "scope": default,
                }
            )
    if rows:
        connection.execute(
            sa.text(
                """
                INSERT INTO role_record_scopes (id, role_id, module, scope)
                VALUES (:id, :role_id, :module, :scope)
                ON CONFLICT (role_id, module) DO NOTHING
                """
            ),
            rows,
        )


def downgrade() -> None:
    connection = op.get_bind()
    contains_business_data = connection.execute(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM calendar_events) "
            "OR EXISTS (SELECT 1 FROM emails WHERE created_by IS NOT NULL) "
            "OR EXISTS ("
            "SELECT 1 FROM meetings "
            "WHERE created_by IS NOT NULL OR calendar_event_id IS NOT NULL"
            ")"
        )
    ).scalar_one()
    if contains_business_data:
        raise RuntimeError(
            "Cannot downgrade communication ownership/calendar linkage while business data exists"
        )
    role_ids = connection.execute(sa.text("SELECT id FROM roles")).scalars().all()
    migration_scope_ids = [
        _stable_id(role_id, module) for role_id in role_ids for module in MODULES
    ]
    if migration_scope_ids:
        connection.execute(
            sa.text(
                "DELETE FROM role_record_scopes "
                "WHERE id = ANY(:ids) AND module = ANY(:modules)"
            ),
            {"ids": migration_scope_ids, "modules": list(MODULES)},
        )
    op.drop_index("ix_meetings_calendar_event_id", table_name="meetings")
    op.drop_constraint("meetings_calendar_event_id_fkey", "meetings", type_="foreignkey")
    op.drop_column("meetings", "calendar_event_id")
    op.drop_index("ix_meetings_created_by", table_name="meetings")
    op.drop_constraint("meetings_created_by_fkey", "meetings", type_="foreignkey")
    op.drop_column("meetings", "created_by")
    op.drop_index("ix_emails_created_by", table_name="emails")
    op.drop_constraint("emails_created_by_fkey", "emails", type_="foreignkey")
    op.drop_column("emails", "created_by")
    op.drop_constraint("calendar_events_user_id_fkey", "calendar_events", type_="foreignkey")
    op.create_foreign_key(
        "calendar_events_user_id_fkey",
        "calendar_events",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.drop_index("ix_calendar_events_status", table_name="calendar_events")
    op.drop_column("calendar_events", "status")
    op.drop_index("ix_calendar_events_organization_id", table_name="calendar_events")
    op.drop_constraint("calendar_events_organization_id_fkey", "calendar_events", type_="foreignkey")
    op.drop_column("calendar_events", "organization_id")
