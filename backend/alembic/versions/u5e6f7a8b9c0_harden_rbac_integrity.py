"""Remove wildcard grants and enforce one tenant-scoped role per user."""

# ruff: noqa: S608 -- SQL is generated only from the immutable catalog below.

from alembic import op

revision = "u5e6f7a8b9c0"
down_revision = "t4d5e6f7a8b9"
branch_labels = None
depends_on = None

APPROVED_KEYS = (
    "activities:create",
    "activities:export",
    "activities:read",
    "ai:configure",
    "ai:generate",
    "ai:read",
    "api_keys:create",
    "api_keys:read",
    "api_keys:revoke",
    "calendar:read",
    "calendar:sync",
    "calendar:write",
    "calls:create",
    "calls:delete",
    "calls:read",
    "calls:recording",
    "calls:update",
    "companies:bulk_delete",
    "companies:create",
    "companies:delete",
    "companies:export",
    "companies:import",
    "companies:read",
    "companies:update",
    "contacts:assign",
    "contacts:bulk_delete",
    "contacts:bulk_update",
    "contacts:create",
    "contacts:delete",
    "contacts:export",
    "contacts:import",
    "contacts:read",
    "contacts:update",
    "dashboard:customize",
    "dashboard:export",
    "dashboard:read",
    "deals:assign",
    "deals:bulk_delete",
    "deals:create",
    "deals:delete",
    "deals:export",
    "deals:import",
    "deals:pipeline",
    "deals:read",
    "deals:update",
    "documents:delete",
    "documents:read",
    "documents:share",
    "documents:upload",
    "emails:delete",
    "emails:read",
    "emails:send",
    "emails:templates",
    "integrations:apikeys",
    "integrations:manage",
    "integrations:read",
    "invitations:create",
    "invitations:read",
    "invitations:resend",
    "invitations:revoke",
    "invoices:create",
    "invoices:delete",
    "invoices:export",
    "invoices:import",
    "invoices:payment",
    "invoices:read",
    "invoices:send",
    "invoices:update",
    "leads:assign",
    "leads:bulk_delete",
    "leads:bulk_update",
    "leads:convert",
    "leads:create",
    "leads:delete",
    "leads:export",
    "leads:import",
    "leads:read",
    "leads:update",
    "meetings:create",
    "meetings:delete",
    "meetings:export",
    "meetings:invite",
    "meetings:read",
    "meetings:update",
    "notes:create",
    "notes:delete",
    "notes:read",
    "notes:update",
    "notifications:manage",
    "notifications:read",
    "notifications:send",
    "organization:audit",
    "organization:billing",
    "organization:branding",
    "organization:delete",
    "organization:domains",
    "organization:members",
    "organization:read",
    "organization:transfer_ownership",
    "organization:update",
    "products:create",
    "products:delete",
    "products:export",
    "products:import",
    "products:read",
    "products:update",
    "projects:assign",
    "projects:create",
    "projects:delete",
    "projects:read",
    "projects:update",
    "quotes:approve",
    "quotes:create",
    "quotes:delete",
    "quotes:export",
    "quotes:import",
    "quotes:read",
    "quotes:send",
    "quotes:update",
    "reports:create",
    "reports:delete",
    "reports:export",
    "reports:read",
    "reports:schedule",
    "roles:assign",
    "roles:create",
    "roles:delete",
    "roles:read",
    "roles:update",
    "settings:read",
    "settings:security",
    "settings:update",
    "super_admin:manage",
    "tasks:assign",
    "tasks:complete",
    "tasks:create",
    "tasks:delete",
    "tasks:export",
    "tasks:import",
    "tasks:read",
    "tasks:update",
    "users:assign_roles",
    "users:create",
    "users:delete",
    "users:export",
    "users:import",
    "users:invite",
    "users:read",
    "users:reset_password",
    "users:roles",
    "users:update",
)


def _sql_values(values: tuple[str, ...]) -> str:
    return ", ".join("('" + value.replace("'", "''") + "')" for value in values)


def upgrade() -> None:
    values = _sql_values(APPROVED_KEYS)
    op.execute(
        "LOCK TABLE users, roles, user_roles, permissions, role_permissions, "
        "user_invitations, organization_invitations, settings "
        "IN SHARE ROW EXCLUSIVE MODE"
    )
    # Preserve existing permission IDs and mappings while normalizing legacy
    # casing/whitespace to the catalog representation. The existing normalized
    # unique index guarantees at most one row per normalized key.
    op.execute(
        f"""
        UPDATE permissions AS permission
        SET key = approved.key
        FROM (VALUES {values}) AS approved(key)
        WHERE lower(btrim(permission.key)) = approved.key
          AND permission.key <> approved.key
        """
    )
    op.execute(
        f"""
        INSERT INTO permissions (id, key, name, category)
        SELECT md5('rbac-permission:' || approved.key), approved.key, approved.key,
               split_part(approved.key, ':', 1)
        FROM (VALUES {values}) AS approved(key)
        ON CONFLICT DO NOTHING
        """
    )
    op.execute(
        f"""
        INSERT INTO role_permissions (id, role_id, permission_id)
        SELECT md5('rbac-role-permission:' || rp.role_id || ':' || approved_permission.id),
               rp.role_id, approved_permission.id
        FROM role_permissions AS rp
        JOIN permissions AS wildcard ON wildcard.id = rp.permission_id
        JOIN roles AS legacy_role ON legacy_role.id = rp.role_id
        CROSS JOIN permissions AS approved_permission
        WHERE lower(btrim(wildcard.key)) = 'all'
          AND approved_permission.key IN (SELECT key FROM (VALUES {values}) AS approved(key))
          AND (
            approved_permission.key NOT IN ('organization:delete', 'super_admin:manage')
            OR (
              legacy_role.organization_id IS NULL
              AND lower(replace(btrim(legacy_role.name), '_', ' ')) = 'super admin'
            )
          )
        ON CONFLICT DO NOTHING
        """
    )
    op.execute(
        "DELETE FROM role_permissions USING permissions "
        "WHERE role_permissions.permission_id = permissions.id "
        "AND lower(btrim(permissions.key)) = 'all'"
    )
    op.execute("DELETE FROM permissions WHERE lower(btrim(key)) = 'all'")
    op.execute(
        """
        DELETE FROM role_permissions rp
        USING permissions permission, roles role
        WHERE rp.permission_id = permission.id
          AND rp.role_id = role.id
          AND permission.key IN ('organization:delete', 'super_admin:manage')
          AND NOT (
            role.organization_id IS NULL
            AND lower(replace(btrim(role.name), '_', ' ')) = 'super admin'
          )
        """
    )

    # Replace a legacy global role mapping with the equivalent tenant role when
    # that tenant role already exists. This preserves the user's named role.
    op.execute(
        """
        DELETE FROM user_roles legacy
        USING users u, roles global_role, roles local_role, user_roles existing
        WHERE legacy.user_id = u.id
          AND legacy.role_id = global_role.id
          AND global_role.organization_id IS NULL
          AND NOT u.is_platform_admin
          AND local_role.organization_id = u.organization_id
          AND lower(btrim(local_role.name)) = lower(btrim(global_role.name))
          AND existing.user_id = u.id
          AND existing.role_id = local_role.id
        """
    )
    op.execute(
        """
        UPDATE user_roles legacy
        SET role_id = local_role.id
        FROM users u, roles global_role, roles local_role
        WHERE legacy.user_id = u.id
          AND legacy.role_id = global_role.id
          AND global_role.organization_id IS NULL
          AND NOT u.is_platform_admin
          AND local_role.organization_id = u.organization_id
          AND lower(btrim(local_role.name)) = lower(btrim(global_role.name))
        """
    )
    op.execute(
        """
        UPDATE users u
        SET role = local_role.id
        FROM roles global_role, roles local_role
        WHERE btrim(u.role) = global_role.id
          AND NOT u.is_platform_admin
          AND global_role.organization_id IS NULL
          AND lower(replace(btrim(global_role.name), '_', ' ')) <> 'super admin'
          AND local_role.organization_id = u.organization_id
          AND lower(btrim(local_role.name)) = lower(btrim(global_role.name))
        """
    )
    op.execute(
        """
        UPDATE user_invitations invitation
        SET role = local_role.id
        FROM roles global_role, roles local_role
        WHERE btrim(invitation.role) = global_role.id
          AND global_role.organization_id IS NULL
          AND lower(replace(btrim(global_role.name), '_', ' ')) <> 'super admin'
          AND local_role.organization_id = invitation.organization_id
          AND lower(btrim(local_role.name)) = lower(btrim(global_role.name))
        """
    )
    op.execute(
        """
        UPDATE organization_invitations invitation
        SET role_id = local_role.id
        FROM roles global_role, roles local_role
        WHERE btrim(invitation.role_id) = global_role.id
          AND global_role.organization_id IS NULL
          AND lower(replace(btrim(global_role.name), '_', ' ')) <> 'super admin'
          AND local_role.organization_id = invitation.organization_id
          AND lower(btrim(local_role.name)) = lower(btrim(global_role.name))
        """
    )
    op.execute(
        """
        CREATE FUNCTION pg_temp.rbac_safe_jsonb(value text) RETURNS jsonb AS $$
        BEGIN
          RETURN value::jsonb;
        EXCEPTION WHEN invalid_text_representation THEN
          RETURN NULL;
        END;
        $$ LANGUAGE plpgsql IMMUTABLE
        """
    )
    op.execute(
        """
        UPDATE settings setting
        SET value = local_role.id
        FROM roles global_role, roles local_role
        WHERE global_role.organization_id IS NULL
          AND lower(replace(btrim(global_role.name), '_', ' ')) <> 'super admin'
          AND local_role.organization_id IS NOT NULL
          AND lower(btrim(local_role.name)) = lower(btrim(global_role.name))
          AND setting.key = 'default_registration_role:' || local_role.organization_id
          AND btrim(setting.value) = global_role.id
        """
    )
    op.execute(
        """
        UPDATE settings setting
        SET value = (
          SELECT COALESCE(
            jsonb_agg(
              CASE
                WHEN jsonb_typeof(item.value) = 'string' THEN
                  to_jsonb(COALESCE((
                    SELECT local_role.id
                    FROM roles global_role
                    JOIN roles local_role
                      ON local_role.organization_id = substring(
                           setting.key FROM length('default_registration_roles:') + 1
                         )
                     AND lower(btrim(local_role.name)) = lower(btrim(global_role.name))
                    WHERE global_role.id = btrim(item.value #>> '{}')
                      AND global_role.organization_id IS NULL
                      AND lower(replace(btrim(global_role.name), '_', ' ')) <> 'super admin'
                    LIMIT 1
                  ), btrim(item.value #>> '{}')))
                ELSE item.value
              END
              ORDER BY item.ordinality
            ),
            '[]'::jsonb
          )::text
          FROM jsonb_array_elements(pg_temp.rbac_safe_jsonb(setting.value))
               WITH ORDINALITY item(value, ordinality)
        )
        WHERE left(setting.key, length('default_registration_roles:'))
              = 'default_registration_roles:'
          AND jsonb_typeof(pg_temp.rbac_safe_jsonb(setting.value)) = 'array'
        """
    )

    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM user_roles GROUP BY user_id HAVING count(*) > 1) THEN
            RAISE EXCEPTION 'RBAC migration blocked: users with multiple roles require reviewed cleanup';
          END IF;
          IF EXISTS (
            SELECT 1
            FROM user_roles ur
            JOIN users u ON u.id = ur.user_id
            JOIN roles r ON r.id = ur.role_id
            WHERE (u.is_platform_admin AND NOT (
                     u.organization_id IS NULL AND r.organization_id IS NULL
                     AND lower(replace(btrim(r.name), '_', ' ')) = 'super admin'
                   ))
               OR (NOT u.is_platform_admin AND r.organization_id IS DISTINCT FROM u.organization_id)
          ) THEN
            RAISE EXCEPTION 'RBAC migration blocked: cross-organization role mappings require reviewed cleanup';
          END IF;
          IF EXISTS (
            SELECT 1
            FROM users u
            JOIN roles r ON btrim(u.role) = r.id
            WHERE NOT u.is_platform_admin
              AND r.organization_id IS NULL
          ) THEN
            RAISE EXCEPTION 'RBAC migration blocked: legacy global user role values require reviewed cleanup';
          END IF;
          IF EXISTS (
            SELECT 1
            FROM user_invitations invitation
            JOIN roles r ON btrim(invitation.role) = r.id
            WHERE r.organization_id IS NULL
              AND lower(replace(btrim(r.name), '_', ' ')) <> 'super admin'
          ) THEN
            RAISE EXCEPTION 'RBAC migration blocked: unresolved user invitation roles require reviewed cleanup';
          END IF;
          IF EXISTS (
            SELECT 1
            FROM organization_invitations invitation
            JOIN roles r ON btrim(invitation.role_id) = r.id
            WHERE r.organization_id IS NULL
              AND lower(replace(btrim(r.name), '_', ' ')) <> 'super admin'
          ) THEN
            RAISE EXCEPTION 'RBAC migration blocked: unresolved organization invitation roles require reviewed cleanup';
          END IF;
          IF EXISTS (
            SELECT 1 FROM settings setting
            WHERE left(setting.key, length('default_registration_roles:'))
                  = 'default_registration_roles:'
              AND (
                pg_temp.rbac_safe_jsonb(setting.value) IS NULL
                OR jsonb_typeof(pg_temp.rbac_safe_jsonb(setting.value)) <> 'array'
              )
          ) THEN
            RAISE EXCEPTION 'RBAC migration blocked: invalid default role settings require reviewed cleanup';
          END IF;
          IF EXISTS (
            SELECT 1
            FROM settings setting
            JOIN roles r ON r.organization_id IS NULL
            WHERE (
                (left(setting.key, length('default_registration_role:'))
                   = 'default_registration_role:'
                 AND btrim(setting.value) = r.id)
                OR
                (left(setting.key, length('default_registration_roles:'))
                   = 'default_registration_roles:'
                 AND EXISTS (
                   SELECT 1
                   FROM jsonb_array_elements_text(
                     pg_temp.rbac_safe_jsonb(setting.value)
                   ) item(value)
                   WHERE btrim(item.value) = r.id
                 ))
              )
              AND r.organization_id IS NULL
              AND lower(replace(btrim(r.name), '_', ' ')) <> 'super admin'
          ) THEN
            RAISE EXCEPTION 'RBAC migration blocked: unresolved default role settings require reviewed cleanup';
          END IF;
        END $$
        """
    )
    # UserRole is authoritative. Reconcile the denormalized display field only
    # after tenant/platform scope has passed the preflight above.
    op.execute(
        """
        UPDATE users u
        SET role = ur.role_id
        FROM user_roles ur
        WHERE ur.user_id = u.id
          AND NOT u.is_platform_admin
          AND u.role IS DISTINCT FROM ur.role_id
        """
    )
    # At this point no tenant user can depend on a global tenant-role template.
    # Removing those templates prevents startup from reviving global Admin-like roles.
    op.execute(
        "DELETE FROM roles WHERE organization_id IS NULL AND is_system_role "
        "AND lower(replace(btrim(name), '_', ' ')) <> 'super admin'"
    )
    op.execute("CREATE UNIQUE INDEX uq_user_roles_user ON user_roles (user_id)")
    op.drop_constraint("user_roles_role_id_fkey", "user_roles", type_="foreignkey")
    op.create_foreign_key(
        "user_roles_role_id_fkey",
        "user_roles",
        "roles",
        ["role_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_check_constraint(
        "ck_permissions_no_wildcard", "permissions", "lower(btrim(key)) <> 'all'"
    )
    op.execute(
        """
        CREATE FUNCTION enforce_user_role_scope() RETURNS trigger AS $$
        DECLARE user_org text; platform_admin boolean; role_org text; role_name text;
        BEGIN
          PERFORM pg_advisory_xact_lock(hashtextextended('rbac-user:' || NEW.user_id, 0));
          PERFORM pg_advisory_xact_lock(hashtextextended('rbac-role:' || NEW.role_id, 0));
          SELECT organization_id, is_platform_admin INTO user_org, platform_admin
          FROM users WHERE id = NEW.user_id;
          SELECT organization_id, lower(replace(btrim(name), '_', ' '))
          INTO role_org, role_name FROM roles WHERE id = NEW.role_id;
          IF platform_admin THEN
            IF user_org IS NOT NULL OR role_org IS NOT NULL OR role_name <> 'super admin' THEN
              RAISE EXCEPTION 'platform users may only hold the global Super Admin role';
            END IF;
          ELSIF role_org IS DISTINCT FROM user_org THEN
            RAISE EXCEPTION 'tenant users may only hold roles from their organization';
          END IF;
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        "CREATE TRIGGER trg_user_role_scope BEFORE INSERT OR UPDATE ON user_roles "
        "FOR EACH ROW EXECUTE FUNCTION enforce_user_role_scope()"
    )
    op.execute(
        """
        CREATE FUNCTION enforce_user_scope_update() RETURNS trigger AS $$
        BEGIN
          PERFORM pg_advisory_xact_lock(hashtextextended('rbac-user:' || NEW.id, 0));
          IF EXISTS (
            SELECT 1 FROM user_roles ur JOIN roles r ON r.id = ur.role_id
            WHERE ur.user_id = NEW.id
              AND (
                (NEW.is_platform_admin AND NOT (
                  NEW.organization_id IS NULL AND r.organization_id IS NULL
                  AND lower(replace(btrim(r.name), '_', ' ')) = 'super admin'
                ))
                OR (NOT NEW.is_platform_admin
                    AND r.organization_id IS DISTINCT FROM NEW.organization_id)
              )
          ) THEN
            RAISE EXCEPTION 'user scope update would invalidate its role mapping';
          END IF;
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        "CREATE TRIGGER trg_user_scope_update "
        "BEFORE UPDATE OF organization_id, is_platform_admin ON users "
        "FOR EACH ROW EXECUTE FUNCTION enforce_user_scope_update()"
    )
    op.execute(
        """
        CREATE FUNCTION enforce_role_scope_update() RETURNS trigger AS $$
        BEGIN
          PERFORM pg_advisory_xact_lock(hashtextextended('rbac-role:' || NEW.id, 0));
          IF EXISTS (
            SELECT 1 FROM user_roles ur JOIN users u ON u.id = ur.user_id
            WHERE ur.role_id = NEW.id
              AND (
                (u.is_platform_admin AND NOT (
                  u.organization_id IS NULL AND NEW.organization_id IS NULL
                  AND lower(replace(btrim(NEW.name), '_', ' ')) = 'super admin'
                ))
                OR (NOT u.is_platform_admin
                    AND NEW.organization_id IS DISTINCT FROM u.organization_id)
              )
          ) THEN
            RAISE EXCEPTION 'role scope update would invalidate user mappings';
          END IF;
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        "CREATE TRIGGER trg_role_scope_update "
        "BEFORE UPDATE OF organization_id, name ON roles "
        "FOR EACH ROW EXECUTE FUNCTION enforce_role_scope_update()"
    )


def downgrade() -> None:
    raise RuntimeError(
        "RBAC hardening is forward-only because legacy wildcard grants and global tenant-role "
        "templates cannot be reconstructed safely"
    )
