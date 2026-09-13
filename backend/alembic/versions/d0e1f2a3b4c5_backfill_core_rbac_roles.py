"""Backfill canonical tenant roles and least-privilege record scopes.

Revision ID: d0e1f2a3b4c5
Revises: c9e0f1a2b3c4

This migration adds missing roles/grants/scopes and removes only explicitly
identified over-privileged role-permission mappings. It never deletes or
renames roles, permissions, user assignments, or business data.
"""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import insert

revision: str = "d0e1f2a3b4c5"
down_revision: str | None = "c9e0f1a2b3c4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _keys(spec: str) -> frozenset[str]:
    return frozenset(
        f"{module}:{action}"
        for line in spec.strip().splitlines()
        for module, actions in [line.strip().split(" ", 1)]
        for action in actions.split()
    )


# Immutable snapshot of the canonical grants at this revision.  Do not import
# application constants into a historical migration.
ROLE_PERMISSIONS = {
    "Admin": _keys("""
dashboard read customize export
leads read create update delete export import assign convert bulk_delete bulk_update
contacts read create update delete export import assign bulk_delete bulk_update
companies read create update delete export import bulk_delete
deals read create update delete pipeline export import assign bulk_delete
tasks read create update delete assign complete export import
meetings read create update delete invite export
calls read create update delete recording
emails read send templates delete
notes read create update delete
documents read upload delete share
products read create update delete export import
quotes read create update approve delete send export import
invoices read create update send delete payment export import
reports read create export schedule delete
calendar read write sync
users read create invite update delete export import roles reset_password assign_roles
roles read create update delete assign
organization read update billing domains branding audit members transfer_ownership
invitations read create resend revoke
integrations read manage apikeys
whatsapp read_assigned read_all send assign takeover manage_ai
notifications read manage send
settings read update security
activities read create export
ai read generate configure
api_keys read create revoke
projects read create update delete assign
orders read create update
tickets read create update delete assign export
knowledge_base read create update delete publish
teams read create update delete manage_members
workflows read create update delete
"""),
    "Sales Manager": _keys("""
whatsapp read_assigned read_all send assign takeover manage_ai
dashboard read customize export
leads read create update delete export import assign convert bulk_delete bulk_update
contacts read create update delete export import assign bulk_delete bulk_update
companies read create update delete export import bulk_delete
deals read create update delete pipeline export import assign bulk_delete
tasks read create update delete assign complete export import
meetings read create update delete invite export
calls read create update delete recording
emails read send templates
notes read create update delete
documents read upload delete share
products read create update delete export import
quotes read create update approve delete send export import
invoices read create update send delete payment export import
reports read create export schedule
calendar read write sync
activities read create export
ai read generate
orders read create update
"""),
    "Sales Executive": _keys("""
whatsapp read_assigned send takeover
dashboard read
leads read create update convert export
contacts read create update export
companies read create update
deals read create update pipeline export
tasks read create update complete
meetings read create update invite
calls read create update
emails read send templates
notes read create update
documents read upload share
products read
quotes read update send
invoices read
reports read
calendar read write
activities read create
ai read generate
orders read create update
"""),
    "Marketing Executive": _keys("""
dashboard read
leads read create update import export
contacts read create update import export
companies read
emails read send templates
tasks read create update complete
meetings read create update
calendar read write
reports read export
activities read create
ai read generate
"""),
    "Customer Support": _keys("""
whatsapp read_assigned send takeover
dashboard read
leads read
contacts read update
companies read update
tasks read create update complete
meetings read create update
calls read create update
emails read send
notes read create update
documents read upload
invoices read
calendar read write
activities read create
ai read
orders read
tickets read create update
knowledge_base read
"""),
    "Read Only": _keys("""
dashboard read
leads read
contacts read
companies read
deals read
tasks read
meetings read
calls read
emails read
notes read
documents read
products read
quotes read
invoices read
reports read
calendar read
activities read
ai read
projects read
orders read
"""),
    "Project Manager": _keys("""
dashboard read
projects read create update delete assign
tasks read create update delete assign complete export import
documents read upload delete share
contacts read
companies read
deals read
calendar read write
reports read
activities read create
"""),
    "Project Member": _keys("""
dashboard read
projects read
tasks read create update complete
documents read upload share
contacts read
companies read
deals read
calendar read write
activities read create
"""),
    "Support Manager": _keys("""
whatsapp read_assigned read_all send assign takeover
dashboard read
tickets read create update delete assign export
knowledge_base read create update delete publish
contacts read update
companies read update
tasks read create update assign complete
calls read create update
emails read send
notes read create update
documents read upload share
calendar read write
activities read create
reports read export
"""),
    "Finance/Accounts": _keys("""
dashboard read
contacts read
companies read
deals read
products read
quotes read
orders read update
invoices read create update send payment export import
reports read export
documents read upload share
"""),
}

ROLE_ALIASES = {
    "Sales Executive": ("Sales Executive", "Sales Representative", "Sales Rep", "Sales User"),
    "Customer Support": ("Customer Support", "Support Agent"),
    "Read Only": ("Read Only", "Analyst", "Viewer", "Analyst/Viewer", "Analyst / Viewer"),
    "Finance/Accounts": ("Finance/Accounts", "Finance / Accounts", "Finance", "Accounts"),
}

# These legacy mappings exceed the approved least-privilege matrix. Only the
# relationship rows are removed; permission catalog records remain untouched.
REMOVE_ROLE_PERMISSIONS = {
    "Sales Manager": _keys("""
projects read create update delete assign
"""),
    "Customer Support": _keys("""
whatsapp read_all assign manage_ai
"""),
    "Project Member": _keys("""
projects update
"""),
}

RECORD_SCOPE_MODULES = (
    "leads",
    "contacts",
    "companies",
    "deals",
    "tasks",
    "activities",
    "projects",
    "tickets",
    "documents",
    "quotes",
    "orders",
    "invoices",
    "payments",
)


def _scopes(default: str, *, none: tuple[str, ...] = ()) -> dict[str, str]:
    return {module: "none" if module in none else default for module in RECORD_SCOPE_MODULES}


ROLE_SCOPES = {
    "Admin": _scopes("all"),
    "Sales Manager": _scopes("team", none=("tickets",)),
    "Sales Executive": _scopes("assigned", none=("projects", "tickets")),
    "Marketing Executive": _scopes(
        "assigned",
        none=(
            "deals",
            "projects",
            "tickets",
            "documents",
            "quotes",
            "orders",
            "invoices",
            "payments",
        ),
    ),
    "Customer Support": _scopes("assigned", none=("deals", "projects", "quotes", "payments")),
    "Read Only": _scopes("all"),
    "Project Manager": _scopes(
        "team", none=("leads", "tickets", "quotes", "orders", "invoices", "payments")
    ),
    "Project Member": _scopes(
        "assigned", none=("leads", "tickets", "quotes", "orders", "invoices", "payments")
    ),
    "Support Manager": _scopes(
        "team", none=("leads", "deals", "projects", "quotes", "orders", "invoices", "payments")
    ),
    "Finance/Accounts": _scopes(
        "all", none=("leads", "tasks", "activities", "projects", "tickets")
    ),
}


def _stable_id(kind: str, *parts: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, ":".join(("crm", kind, *parts))))


def _normalized_role_name(value: str) -> str:
    return " ".join(value.strip().lower().replace("_", " ").split())


def upgrade() -> None:
    connection = op.get_bind()
    # Prevent a tenant from being inserted after the snapshot and missing this
    # backfill. PostgreSQL INSERT takes ROW EXCLUSIVE, which conflicts with this
    # lock; existing tenant traffic can continue reading while the short,
    # transaction-scoped migration completes.
    connection.execute(sa.text("LOCK TABLE organizations IN SHARE MODE"))
    role_table = sa.table(
        "roles",
        sa.column("id", sa.String()),
        sa.column("organization_id", sa.String()),
        sa.column("name", sa.String()),
        sa.column("description", sa.Text()),
        sa.column("is_system_role", sa.Boolean()),
    )
    permission_table = sa.table(
        "permissions", sa.column("id", sa.String()), sa.column("key", sa.String())
    )
    role_permission_table = sa.table(
        "role_permissions",
        sa.column("id", sa.String()),
        sa.column("role_id", sa.String()),
        sa.column("permission_id", sa.String()),
    )
    scope_table = sa.table(
        "role_record_scopes",
        sa.column("id", sa.String()),
        sa.column("role_id", sa.String()),
        sa.column("module", sa.String()),
        sa.column("scope", sa.String()),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )

    permission_ids = dict(
        connection.execute(sa.select(permission_table.c.key, permission_table.c.id)).all()
    )
    required_keys = set().union(*ROLE_PERMISSIONS.values())
    missing_keys = sorted(required_keys - permission_ids.keys())
    if missing_keys:
        raise RuntimeError(
            "RBAC role backfill aborted; permission catalog is missing: " + ", ".join(missing_keys)
        )

    organization_ids = list(
        connection.execute(sa.text("SELECT id FROM organizations ORDER BY id")).scalars()
    )
    existing_roles = (
        connection.execute(
            sa.select(
                role_table.c.id,
                role_table.c.organization_id,
                role_table.c.name,
                role_table.c.is_system_role,
            ).where(role_table.c.organization_id.in_(organization_ids))
        )
        .mappings()
        .all()
        if organization_ids
        else []
    )
    roles_to_insert = []
    resolved_roles = []
    for organization_id in organization_ids:
        for role_name, permission_keys in ROLE_PERMISSIONS.items():
            aliases = {
                _normalized_role_name(value) for value in ROLE_ALIASES.get(role_name, (role_name,))
            }
            matches = [
                row
                for row in existing_roles
                if row["organization_id"] == organization_id
                and _normalized_role_name(str(row["name"])) in aliases
            ]
            if len(matches) > 1:
                names = ", ".join(sorted(str(row["name"]) for row in matches))
                raise RuntimeError(
                    f"RBAC role backfill aborted; ambiguous aliases for {role_name!r} "
                    f"in organization {organization_id}: {names}"
                )
            existing = matches[0] if matches else None
            if existing and not existing["is_system_role"]:
                raise RuntimeError(
                    f"RBAC role backfill aborted; custom role conflicts with {role_name!r} "
                    f"in organization {organization_id}"
                )

            role_id = existing["id"] if existing else _stable_id("role", organization_id, role_name)
            if not existing:
                roles_to_insert.append(
                    {
                        "id": role_id,
                        "organization_id": organization_id,
                        "name": role_name,
                        "description": f"System {role_name} role",
                        "is_system_role": True,
                    }
                )
            resolved_roles.append((role_id, role_name, permission_keys))

    if roles_to_insert:
        connection.execute(insert(role_table).values(roles_to_insert).on_conflict_do_nothing())

    grant_rows = [
        {
            "id": _stable_id("role-permission", role_id, permission_ids[key]),
            "role_id": role_id,
            "permission_id": permission_ids[key],
        }
        for role_id, _, permission_keys in resolved_roles
        for key in sorted(permission_keys)
    ]
    if grant_rows:
        connection.execute(
            insert(role_permission_table)
            .values(grant_rows)
            .on_conflict_do_nothing(index_elements=["role_id", "permission_id"])
        )

    removal_pairs = [
        (role_id, permission_ids[key])
        for role_id, role_name, _ in resolved_roles
        for key in sorted(REMOVE_ROLE_PERMISSIONS.get(role_name, frozenset()))
    ]
    if removal_pairs:
        connection.execute(
            sa.delete(role_permission_table).where(
                sa.tuple_(
                    role_permission_table.c.role_id,
                    role_permission_table.c.permission_id,
                ).in_(removal_pairs)
            )
        )

    scope_rows = [
        {
            "id": _stable_id("role-scope", role_id, module),
            "role_id": role_id,
            "module": module,
            "scope": scope,
        }
        for role_id, role_name, _ in resolved_roles
        for module, scope in ROLE_SCOPES[role_name].items()
    ]
    if scope_rows:
        scope_insert = insert(scope_table).values(scope_rows)
        connection.execute(
            scope_insert.on_conflict_do_update(
                index_elements=["role_id", "module"],
                set_={"scope": scope_insert.excluded.scope, "updated_at": sa.func.now()},
                where=scope_table.c.scope != scope_insert.excluded.scope,
            )
        )

    # Existing custom roles predate the Activities scope. Preserve their prior
    # effective visibility explicitly; runtime handling of any other missing
    # scope remains fail-closed.
    custom_roles = (
        connection.execute(
            sa.select(role_table.c.id).where(
                role_table.c.organization_id.is_not(None),
                role_table.c.is_system_role.is_(False),
            )
        )
        .scalars()
        .all()
    )
    if custom_roles:
        connection.execute(
            insert(scope_table)
            .values(
                [
                    {
                        "id": _stable_id("role-scope", role_id, "activities"),
                        "role_id": role_id,
                        "module": "activities",
                        "scope": "all",
                    }
                    for role_id in custom_roles
                ]
            )
            .on_conflict_do_nothing(index_elements=["role_id", "module"])
        )


def downgrade() -> None:
    # Intentionally irreversible: roles may be assigned after this migration.
    # Removing them or their grants during rollback would violate user safety.
    pass
