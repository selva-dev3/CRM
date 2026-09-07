"""Separate the singleton platform identity from organization membership.

Preserve the existing platform user ID and credentials. Ambiguous identities
require manual review; passwords and email changes belong to secure provisioning.
"""

import sqlalchemy as sa
from alembic import op

revision = "r1a2b3c4d5e6"
down_revision = "q0f1a2b3c4d5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    connection.execute(sa.text("LOCK TABLE users, roles, user_roles IN SHARE ROW EXCLUSIVE MODE"))
    candidates = connection.execute(sa.text("""
        SELECT DISTINCT u.id FROM users u
        LEFT JOIN user_roles ur ON ur.user_id = u.id
        LEFT JOIN roles r ON r.id = ur.role_id OR r.id = u.role
        WHERE lower(replace(btrim(u.role), '_', ' ')) = 'super admin'
           OR (r.organization_id IS NULL
               AND lower(replace(btrim(r.name), '_', ' ')) = 'super admin')
    """)).scalars().all()
    if len(candidates) > 1:
        raise RuntimeError(
            "Multiple platform administrator candidates; review identities before migrating"
        )
    if candidates and connection.scalar(
        sa.text("""
        SELECT EXISTS(SELECT 1 FROM user_roles ur JOIN roles r ON r.id = ur.role_id
        WHERE ur.user_id = :user_id AND
          (r.organization_id IS NOT NULL OR lower(replace(btrim(r.name), '_', ' ')) <> 'super admin'))
    """),
        {"user_id": candidates[0]},
    ):
        raise RuntimeError(
            "Platform candidate has organization role assignments; review before migrating"
        )
    # Authentication is case insensitive; two case variants must not resolve to
    # different identities. Existing collisions stop the migration for review.
    op.execute("CREATE UNIQUE INDEX uq_users_normalized_email ON users (lower(btrim(email)))")
    op.add_column(
        "users",
        sa.Column("is_platform_admin", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.alter_column("users", "organization_id", nullable=True)
    if candidates:
        connection.execute(
            sa.text("""
            UPDATE users SET is_platform_admin = true, organization_id = NULL, role = 'Super Admin'
            WHERE id = :user_id
        """),
            {"user_id": candidates[0]},
        )
    op.create_index(
        "uq_users_platform_admin",
        "users",
        ["is_platform_admin"],
        unique=True,
        postgresql_where=sa.text("is_platform_admin"),
    )
    op.create_check_constraint(
        "ck_users_platform_scope",
        "users",
        "(is_platform_admin AND organization_id IS NULL AND is_active) OR "
        "(NOT is_platform_admin AND organization_id IS NOT NULL)",
    )
    op.create_check_constraint(
        "ck_roles_super_admin_global",
        "roles",
        "lower(replace(btrim(name), '_', ' ')) <> 'super admin' OR "
        "(organization_id IS NULL AND is_system_role)",
    )
    op.execute("""CREATE UNIQUE INDEX uq_roles_platform_super_admin ON roles
        ((lower(replace(btrim(name), '_', ' '))))
        WHERE lower(replace(btrim(name), '_', ' ')) = 'super admin'""")
    op.execute("""
        CREATE FUNCTION protect_platform_user() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'TRUNCATE' THEN
                RAISE EXCEPTION 'Platform accounts cannot be truncated' USING ERRCODE = '23514';
            END IF;
            IF TG_OP = 'DELETE' THEN
                IF OLD.is_platform_admin THEN
                    RAISE EXCEPTION 'Platform account cannot be deleted' USING ERRCODE = '23514';
                END IF;
                RETURN OLD;
            END IF;
            IF TG_OP = 'UPDATE' AND OLD.is_platform_admin AND NOT NEW.is_platform_admin THEN
                RAISE EXCEPTION 'Platform account cannot be demoted' USING ERRCODE = '23514';
            END IF;
            IF NOT NEW.is_platform_admin AND (
                lower(replace(btrim(NEW.role), '_', ' ')) = 'super admin' OR EXISTS (
                    SELECT 1 FROM roles WHERE id = NEW.role
                    AND lower(replace(btrim(name), '_', ' ')) = 'super admin'
                )
            ) THEN
                RAISE EXCEPTION 'Super Admin is reserved for the platform account' USING ERRCODE = '23514';
            END IF;
            IF NEW.is_platform_admin AND NEW.role <> 'Super Admin' THEN
                RAISE EXCEPTION 'Platform role cannot be changed' USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END $$
    """)
    op.execute(
        "CREATE TRIGGER protect_platform_user BEFORE INSERT OR UPDATE OR DELETE ON users FOR EACH ROW EXECUTE FUNCTION protect_platform_user()"
    )
    op.execute(
        "CREATE TRIGGER protect_platform_truncate BEFORE TRUNCATE ON users FOR EACH STATEMENT EXECUTE FUNCTION protect_platform_user()"
    )
    op.execute("""
        CREATE FUNCTION protect_platform_role_mapping() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE platform_user boolean; platform_role boolean;
        BEGIN
            SELECT is_platform_admin INTO platform_user FROM users WHERE id = NEW.user_id;
            SELECT lower(replace(btrim(name), '_', ' ')) = 'super admin'
                INTO platform_role FROM roles WHERE id = NEW.role_id;
            IF platform_user IS DISTINCT FROM platform_role THEN
                RAISE EXCEPTION 'Platform role assignment is reserved' USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END $$
    """)
    op.execute(
        "CREATE TRIGGER protect_platform_role_mapping BEFORE INSERT OR UPDATE ON user_roles FOR EACH ROW EXECUTE FUNCTION protect_platform_role_mapping()"
    )


def downgrade() -> None:
    raise RuntimeError(
        "Global platform identity cannot be made tenant-owned automatically; use an audited recovery migration"
    )
