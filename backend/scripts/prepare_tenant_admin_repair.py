"""Emit reviewed-scope SQL for the September 8 missing tenant Admin roles.

No connection or dotenv access. Default SQL rolls back; --commit only changes
the emitted transaction ending, and never executes it.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.rbac_matrix import ADMIN_PERMISSIONS  # noqa: E402

GLOBAL_ADMIN = "b7d1b2d8-0e9c-4a6c-9c0a-2b2e6e3f7a11"
INVITATION_ID = "971a3ea1-ace7-4c5c-a4fb-ebeb57123e0b"
CUSTOM_ROLE_ID = "680301a2-27df-49a8-8703-7302d1e343d2"
CUSTOM_ORG_ID = "e1f39188-e8e4-42db-8563-6e9ed72d9dc1"
CUSTOM_KEYS = ("activities:read", "calendar:read", "calls:read")
TARGETS = (
    ("31d77119-7453-445b-9930-6a8b00ce7dc4", "98543cc4-3667-426d-97b6-f23826f55f8a"),
    ("41ebbdd3-982a-4ade-aee0-4a0ecb965987", "ae1e5a8d-24a3-4da8-bdf1-23a879fc4cb1"),
    ("dfd38bda-e378-4d3b-8485-7fd651741378", "e1f39188-e8e4-42db-8563-6e9ed72d9dc1"),
    ("0e4a381c-6039-4501-b0f6-32ba1cdb54e4", "c04bc09a-73e5-4aa0-8205-1c1b709b7004"),
)


def _literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def build_sql(*, commit: bool = False) -> str:
    """Add approved tenant grants and the missing revoke key; Alembic reassigns."""
    targets = ",\n".join(f"({_literal(user)}, {_literal(org)})" for user, org in TARGETS)
    keys = ",\n".join(f"({_literal(key)})" for key in sorted(ADMIN_PERMISSIONS))
    custom_keys = ", ".join(f"({_literal(key)})" for key in CUSTOM_KEYS)
    # Inputs are repository constants, escaped as SQL literals, never user input.
    return f"""BEGIN;
SET LOCAL search_path = pg_catalog, public;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '30s';
LOCK TABLE public.alembic_version, public.organizations, public.users,
    public.roles, public.user_roles, public.permissions, public.role_permissions,
    public.user_invitations, public.organization_invitations, public.settings
    IN SHARE ROW EXCLUSIVE MODE;
CREATE TEMP TABLE tenant_admin_repair_targets (
    user_id text PRIMARY KEY, organization_id text UNIQUE NOT NULL
) ON COMMIT DROP;
INSERT INTO pg_temp.tenant_admin_repair_targets VALUES {targets};
CREATE TEMP TABLE tenant_admin_repair_keys (key text PRIMARY KEY) ON COMMIT DROP;
INSERT INTO pg_temp.tenant_admin_repair_keys VALUES {keys};
CREATE TEMP TABLE tenant_admin_repair_custom_keys (key text PRIMARY KEY) ON COMMIT DROP;
INSERT INTO pg_temp.tenant_admin_repair_custom_keys VALUES {custom_keys};
CREATE TEMP TABLE tenant_admin_repair_source_keys (key text PRIMARY KEY) ON COMMIT DROP;
INSERT INTO pg_temp.tenant_admin_repair_source_keys
SELECT key FROM pg_temp.tenant_admin_repair_keys WHERE key <> 'api_keys:revoke'
UNION ALL
SELECT CASE WHEN EXISTS (
    SELECT 1 FROM public.role_permissions rp JOIN public.permissions p ON p.id=rp.permission_id
    WHERE rp.role_id='{GLOBAL_ADMIN}' AND lower(btrim(p.key))='organization:delete'
) THEN 'organization:delete' ELSE 'api_keys:revoke' END;
DO $guard$
BEGIN
    IF (SELECT count(*) FROM public.alembic_version) <> 1
       OR NOT EXISTS (SELECT 1 FROM public.alembic_version WHERE version_num='t4d5e6f7a8b9') THEN
        RAISE EXCEPTION 'Repair blocked: unexpected migration revision';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM public.roles WHERE id='{GLOBAL_ADMIN}'
        AND organization_id IS NULL AND name='Admin' AND is_system_role
    ) THEN
        RAISE EXCEPTION 'Repair blocked: global Admin identity changed';
    END IF;
    IF EXISTS (
        SELECT 1 FROM pg_temp.tenant_admin_repair_targets target
        LEFT JOIN public.users u ON u.id=target.user_id
        WHERE u.id IS NULL OR u.organization_id IS DISTINCT FROM target.organization_id
           OR u.is_platform_admin IS DISTINCT FROM false
           OR (SELECT count(*) FROM public.user_roles ur WHERE ur.user_id=u.id) <> 1
           OR NOT EXISTS (SELECT 1 FROM public.user_roles ur
                          WHERE ur.user_id=u.id AND ur.role_id='{GLOBAL_ADMIN}')
    ) THEN
        RAISE EXCEPTION 'Repair blocked: reviewed user assignments changed';
    END IF;
    IF EXISTS (
        SELECT 1 FROM public.roles r
        JOIN pg_temp.tenant_admin_repair_targets target ON target.organization_id=r.organization_id
        WHERE lower(btrim(r.name))='admin'
    ) THEN
        RAISE EXCEPTION 'Repair blocked: tenant Admin already exists; review before retry';
    END IF;
    IF EXISTS (
        (SELECT lower(btrim(p.key)) FROM public.permissions p
         JOIN public.role_permissions rp ON rp.permission_id=p.id
         WHERE rp.role_id='{GLOBAL_ADMIN}'
         EXCEPT SELECT key FROM pg_temp.tenant_admin_repair_source_keys)
        UNION ALL
        (SELECT key FROM pg_temp.tenant_admin_repair_source_keys
         EXCEPT SELECT lower(btrim(p.key)) FROM public.permissions p
         JOIN public.role_permissions rp ON rp.permission_id=p.id
         WHERE rp.role_id='{GLOBAL_ADMIN}')
    ) THEN
        RAISE EXCEPTION 'Repair blocked: global Admin grants differ from reviewed permission sets';
    END IF;
END $guard$;
DO $custom_guard$
DECLARE setting_record record; setting_json jsonb;
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM public.user_invitations
        WHERE id='{INVITATION_ID}' AND organization_id='{CUSTOM_ORG_ID}'
          AND btrim(role)='{CUSTOM_ROLE_ID}' AND status='pending'
    ) THEN
        RAISE EXCEPTION 'Repair blocked: reviewed invitation changed';
    END IF;
    IF EXISTS (
        SELECT 1 FROM public.users u WHERE u.organization_id='{CUSTOM_ORG_ID}'
          AND (btrim(u.role)='{CUSTOM_ROLE_ID}' OR EXISTS (
              SELECT 1 FROM public.user_roles ur
              WHERE ur.user_id=u.id AND ur.role_id='{CUSTOM_ROLE_ID}'
          ))
    ) OR EXISTS (
        SELECT 1 FROM public.user_invitations
        WHERE organization_id='{CUSTOM_ORG_ID}' AND btrim(role)='{CUSTOM_ROLE_ID}'
          AND id<>'{INVITATION_ID}'
    ) OR EXISTS (
        SELECT 1 FROM public.organization_invitations
        WHERE organization_id='{CUSTOM_ORG_ID}' AND btrim(role_id)='{CUSTOM_ROLE_ID}'
    ) OR EXISTS (
        SELECT 1 FROM public.settings
        WHERE key='default_registration_role:{CUSTOM_ORG_ID}'
          AND btrim(value)='{CUSTOM_ROLE_ID}'
    ) THEN
        RAISE EXCEPTION 'Repair blocked: additional custom-role references require review';
    END IF;
    FOR setting_record IN
        SELECT value FROM public.settings WHERE key='default_registration_roles:{CUSTOM_ORG_ID}'
    LOOP
        BEGIN
            setting_json := setting_record.value::jsonb;
        EXCEPTION WHEN invalid_text_representation THEN
            RAISE EXCEPTION 'Repair blocked: invalid custom-organization default role settings';
        END;
        IF setting_json IS NULL OR jsonb_typeof(setting_json)<>'array' THEN
            RAISE EXCEPTION 'Repair blocked: invalid custom-organization default role settings';
        END IF;
        IF EXISTS (SELECT 1 FROM jsonb_array_elements_text(setting_json) item(value)
                   WHERE btrim(item.value)='{CUSTOM_ROLE_ID}') THEN
            RAISE EXCEPTION 'Repair blocked: additional custom-role references require review';
        END IF;
    END LOOP;
    IF NOT EXISTS (
        SELECT 1 FROM public.roles WHERE id='{CUSTOM_ROLE_ID}' AND name='testing'
          AND organization_id IS NULL AND is_system_role=false
    ) THEN
        RAISE EXCEPTION 'Repair blocked: reviewed custom role changed';
    END IF;
    IF EXISTS (
        SELECT 1 FROM public.roles WHERE organization_id='{CUSTOM_ORG_ID}'
          AND lower(btrim(name))='testing'
    ) THEN
        RAISE EXCEPTION 'Repair blocked: local testing role already exists';
    END IF;
    IF EXISTS (
        (SELECT lower(btrim(p.key)) FROM public.permissions p
         JOIN public.role_permissions rp ON rp.permission_id=p.id
         WHERE rp.role_id='{CUSTOM_ROLE_ID}'
         EXCEPT SELECT key FROM pg_temp.tenant_admin_repair_custom_keys)
        UNION ALL
        (SELECT key FROM pg_temp.tenant_admin_repair_custom_keys
         EXCEPT SELECT lower(btrim(p.key)) FROM public.permissions p
         JOIN public.role_permissions rp ON rp.permission_id=p.id
         WHERE rp.role_id='{CUSTOM_ROLE_ID}')
    ) THEN
        RAISE EXCEPTION 'Repair blocked: custom grants differ from reviewed set';
    END IF;
END $custom_guard$;
-- Match the existing hardening migration's ID and metadata for this one missing key.
INSERT INTO public.permissions (id, key, name, category)
SELECT md5('rbac-permission:api_keys:revoke'), 'api_keys:revoke', 'api_keys:revoke', 'api_keys'
WHERE NOT EXISTS (SELECT 1 FROM public.permissions WHERE lower(btrim(key))='api_keys:revoke');
INSERT INTO public.roles (id, organization_id, name, is_system_role)
SELECT md5('tenant-admin-repair-20260908:' || organization_id), organization_id, 'Admin', true
FROM pg_temp.tenant_admin_repair_targets;
INSERT INTO public.role_permissions (id, role_id, permission_id)
SELECT md5('tenant-admin-repair-20260908:' || target.organization_id || ':' || p.id),
       md5('tenant-admin-repair-20260908:' || target.organization_id), p.id
FROM pg_temp.tenant_admin_repair_targets target
CROSS JOIN pg_temp.tenant_admin_repair_keys approved
JOIN public.permissions p ON lower(btrim(p.key))=approved.key;
INSERT INTO public.roles (id, organization_id, name, description, is_system_role)
SELECT md5('tenant-custom-repair-20260909:{CUSTOM_ORG_ID}:{CUSTOM_ROLE_ID}'),
       '{CUSTOM_ORG_ID}', name, description, false
FROM public.roles WHERE id='{CUSTOM_ROLE_ID}';
INSERT INTO public.role_permissions (id, role_id, permission_id)
SELECT md5('tenant-custom-grant-20260909:{CUSTOM_ORG_ID}:' || rp.permission_id),
       md5('tenant-custom-repair-20260909:{CUSTOM_ORG_ID}:{CUSTOM_ROLE_ID}'), rp.permission_id
FROM public.role_permissions rp WHERE rp.role_id='{CUSTOM_ROLE_ID}';
SELECT r.id, r.organization_id, r.name, count(rp.id) AS permission_count
FROM pg_temp.tenant_admin_repair_targets target
JOIN public.roles r ON r.id=md5('tenant-admin-repair-20260908:' || target.organization_id)
JOIN public.role_permissions rp ON rp.role_id=r.id
GROUP BY r.id, r.organization_id, r.name
ORDER BY r.organization_id;
SELECT r.id, r.organization_id, r.name, count(rp.id) AS permission_count
FROM public.roles r JOIN public.role_permissions rp ON rp.role_id=r.id
WHERE r.id=md5('tenant-custom-repair-20260909:{CUSTOM_ORG_ID}:{CUSTOM_ROLE_ID}')
GROUP BY r.id, r.organization_id, r.name;
{"COMMIT" if commit else "ROLLBACK"};
"""  # noqa: S608 -- Only escaped repository constants are interpolated.


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--commit",
        action="store_true",
        help="Emit COMMIT instead of ROLLBACK; does not execute SQL",
    )
    args = parser.parse_args()
    sys.stdout.write(build_sql(commit=args.commit))


if __name__ == "__main__":
    main()
