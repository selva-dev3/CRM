"""Protect audited RBAC identities and relationship pairs.

Data cleanup is explicit: scripts/cleanup_render_rbac.py creates a recovery
snapshot before merging records. This migration refuses dirty data rather than
deleting it during a deployment.
"""

from alembic import op

revision = "p9e0f1a2b3c4"
down_revision = "o8d9e0f1a2b3"
branch_labels = None
depends_on = None

STATEMENTS = (
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_roles_scope_normalized_name "
    "ON public.roles (organization_id, lower(btrim(name))) NULLS NOT DISTINCT",
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_permissions_normalized_key "
    "ON public.permissions (lower(btrim(key)))",
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_role_permissions_pair "
    "ON public.role_permissions (role_id, permission_id)",
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_user_roles_pair "
    "ON public.user_roles (user_id, role_id)",
)


def upgrade() -> None:
    for statement in STATEMENTS:
        op.execute(statement)


def downgrade() -> None:
    for name in (
        "uq_user_roles_pair",
        "uq_role_permissions_pair",
        "uq_permissions_normalized_key",
        "uq_roles_scope_normalized_name",
    ):
        op.execute(f"DROP INDEX IF EXISTS public.{name}")
