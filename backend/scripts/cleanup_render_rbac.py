"""Controlled cleanup for the audited CRM Render database; never loads .env.

Usage: python scripts/cleanup_render_rbac.py backup|apply|verify SCHEMA
All database access goes through the specified Render CLI resource.
"""

# SQL uses audited constants and a strict identifier allow-list; subprocess uses
# an argv list (no shell) and the user-selected, authenticated Render CLI.
# ruff: noqa: S608, S603, S607

import argparse
import importlib.util
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.core.rbac_matrix import SYSTEM_ROLE_PERMISSIONS  # noqa: E402

TARGET = "dpg-dach4t15efls73eea3t0-a"
ADMIN = "b7d1b2d8-0e9c-4a6c-9c0a-2b2e6e3f7a11"
OLD_ADMIN = "95efa96f-4d75-46ff-9e2f-183a16f7531d"
SUPER = "65bde2ea-0a91-47c1-b1c4-715c084d152f"
OLD_SUPER = "930f5fd6-d977-4bd2-a69b-6fc071a021cb"
SALES = "25a9ff3c-e3f0-480b-ad80-9769852bbd84"
ORG = "e1f39188-e8e4-42db-8563-6e9ed72d9dc1"


def require(condition: str, message: str) -> str:
    return (
        "DO $guard$ BEGIN IF NOT ("
        + condition
        + ") THEN RAISE EXCEPTION '"
        + message.replace("'", "''")
        + "'; END IF; END $guard$;\n"
    )


def expected_sql() -> str:
    values = ",".join(
        f"('{role}', '{key}')"
        for role, keys in SYSTEM_ROLE_PERMISSIONS.items()
        for key in sorted(keys)
    )
    return f"""
CREATE TEMP TABLE expected_grants ON COMMIT DROP AS
WITH approved(name,key) AS (VALUES {values})
SELECT r.id role_id,a.key FROM public.roles r JOIN approved a ON a.name=r.name
WHERE r.is_system_role
UNION ALL
SELECT r.id,p.key FROM public.roles r CROSS JOIN public.permissions p
WHERE r.id='{SUPER}' AND p.key <> 'all';
"""


def integrity_sql(schema: str) -> str:
    return "".join(
        [
            require("(SELECT count(*) FROM public.users)=5", "User count changed"),
            require(
                f"NOT EXISTS (SELECT id,organization_id FROM {schema}.users_roles EXCEPT SELECT id,organization_id FROM public.users)",
                "User identity or organization changed",
            ),
            require(
                "NOT EXISTS (SELECT 1 FROM public.user_roles ur LEFT JOIN public.users u ON u.id=ur.user_id LEFT JOIN public.roles r ON r.id=ur.role_id WHERE u.id IS NULL OR r.id IS NULL)",
                "Dangling user role",
            ),
            require(
                "NOT EXISTS (SELECT 1 FROM public.role_permissions rp LEFT JOIN public.roles r ON r.id=rp.role_id LEFT JOIN public.permissions p ON p.id=rp.permission_id WHERE r.id IS NULL OR p.id IS NULL)",
                "Dangling permission grant",
            ),
            require(
                "NOT EXISTS (SELECT 1 FROM public.user_roles ur JOIN public.users u ON u.id=ur.user_id JOIN public.roles r ON r.id=ur.role_id WHERE r.organization_id IS NOT NULL AND r.organization_id IS DISTINCT FROM u.organization_id)",
                "Cross-organization role mapping",
            ),
            require(
                "NOT EXISTS (SELECT role_id,permission_id FROM public.role_permissions GROUP BY role_id,permission_id HAVING count(*)>1)",
                "Duplicate grants",
            ),
            require(
                "NOT EXISTS (SELECT user_id,role_id FROM public.user_roles GROUP BY user_id,role_id HAVING count(*)>1)",
                "Duplicate user mappings",
            ),
            require(
                "NOT EXISTS (SELECT lower(btrim(key)) FROM public.permissions GROUP BY lower(btrim(key)) HAVING count(*)>1)",
                "Duplicate permission keys",
            ),
            require(
                "(SELECT count(*) FROM public.roles WHERE is_system_role)=7",
                "Expected seven system roles",
            ),
            require(
                "NOT EXISTS (SELECT lower(btrim(name)) FROM public.roles WHERE is_system_role GROUP BY lower(btrim(name)) HAVING count(*)>1)",
                "Duplicate system role names",
            ),
            require(
                "NOT EXISTS (SELECT role_id,key FROM expected_grants EXCEPT SELECT rp.role_id,p.key FROM public.role_permissions rp JOIN public.permissions p ON p.id=rp.permission_id)",
                "Missing approved permissions",
            ),
            require(
                "NOT EXISTS (SELECT rp.role_id,p.key FROM public.role_permissions rp JOIN public.permissions p ON p.id=rp.permission_id JOIN public.roles r ON r.id=rp.role_id WHERE r.is_system_role EXCEPT SELECT role_id,key FROM expected_grants)",
                "Unapproved permissions remain",
            ),
            require(
                f"NOT EXISTS (SELECT * FROM {schema}.roles WHERE NOT is_system_role EXCEPT SELECT * FROM public.roles WHERE NOT is_system_role)",
                "Custom role changed",
            ),
            require(
                f"NOT EXISTS (SELECT rp.* FROM {schema}.role_permissions rp JOIN {schema}.roles r ON r.id=rp.role_id WHERE NOT r.is_system_role EXCEPT SELECT rp.* FROM public.role_permissions rp JOIN public.roles r ON r.id=rp.role_id WHERE NOT r.is_system_role)",
                "Custom grants changed",
            ),
            require(
                f"NOT EXISTS (SELECT user_id,CASE WHEN role_id='{OLD_ADMIN}' THEN '{ADMIN}' ELSE role_id END FROM {schema}.user_roles EXCEPT SELECT user_id,role_id FROM public.user_roles)",
                "Existing assignment lost",
            ),
            require(
                f"NOT EXISTS (SELECT 1 FROM public.users WHERE role IN ('{OLD_ADMIN}','{OLD_SUPER}')) AND NOT EXISTS (SELECT 1 FROM public.user_invitations WHERE role IN ('{OLD_ADMIN}','{OLD_SUPER}')) AND NOT EXISTS (SELECT 1 FROM public.organization_invitations WHERE role_id IN ('{OLD_ADMIN}','{OLD_SUPER}')) AND NOT EXISTS (SELECT 1 FROM public.settings WHERE key LIKE 'default_registration_role%' AND (value LIKE '%{OLD_ADMIN}%' OR value LIKE '%{OLD_SUPER}%'))",
                "Deleted role still referenced",
            ),
        ]
    )


def build_sql(phase: str, schema: str) -> str:
    if not re.fullmatch(r"rbac_recovery_[0-9]{8}_[0-9]{6}", schema):
        raise ValueError("Recovery schema must be rbac_recovery_YYYYMMDD_HHMMSS")
    sql = "BEGIN; SET LOCAL lock_timeout='10s'; SET LOCAL statement_timeout='60s';\n"
    sql += require("current_database()='crm_postgres_om2o'", "Wrong database")
    if phase == "backup":
        sql += "LOCK TABLE public.roles,public.permissions,public.role_permissions,public.user_roles,public.users,public.user_invitations,public.organization_invitations,public.settings IN SHARE MODE;\n"
        sql += require(
            "(SELECT count(*) FROM public.roles)=10 AND (SELECT count(*) FROM public.permissions)=151 AND (SELECT count(*) FROM public.role_permissions)=697 AND (SELECT count(*) FROM public.users)=5 AND (SELECT count(*) FROM public.user_roles)=4",
            "Audit changed: rerun audit",
        )
        sql += f"CREATE SCHEMA {schema}; REVOKE ALL ON SCHEMA {schema} FROM PUBLIC;\n"
        for table in ("roles", "permissions", "role_permissions", "user_roles"):
            sql += f"CREATE TABLE {schema}.{table} AS TABLE public.{table};\n"
            sql += require(
                f"(SELECT count(*) FROM {schema}.{table})=(SELECT count(*) FROM public.{table})",
                f"Snapshot count mismatch: {table}",
            )
        sql += f"""
CREATE TABLE {schema}.users_roles AS SELECT id,organization_id,role FROM public.users;
CREATE TABLE {schema}.user_invitation_roles AS SELECT id,organization_id,role FROM public.user_invitations;
CREATE TABLE {schema}.organization_invitation_roles AS SELECT id,organization_id,role_id FROM public.organization_invitations;
CREATE TABLE {schema}.registration_settings AS SELECT * FROM public.settings WHERE key LIKE 'default_registration_role%';
CREATE TABLE {schema}.metadata AS SELECT current_database() database_name,now() captured_at,'{TARGET}' render_id;
COMMIT;
SELECT * FROM {schema}.metadata;
"""
        return sql
    if phase == "apply":
        sql += "LOCK TABLE public.roles,public.permissions,public.role_permissions,public.user_roles,public.users,public.user_invitations,public.organization_invitations,public.settings IN SHARE ROW EXCLUSIVE MODE;\n"
        for table in ("roles", "permissions", "role_permissions", "user_roles"):
            sql += require(
                f"NOT EXISTS ((TABLE public.{table} EXCEPT TABLE {schema}.{table}) UNION ALL (TABLE {schema}.{table} EXCEPT TABLE public.{table}))",
                f"Snapshot drift: {table}",
            )
        sql += require(
            f"(SELECT count(*) FROM public.roles WHERE id IN ('{ADMIN}','{SUPER}') AND organization_id IS NULL AND is_system_role)=2 AND (SELECT count(*) FROM public.roles WHERE id IN ('{OLD_ADMIN}','{OLD_SUPER}') AND organization_id='{ORG}' AND is_system_role)=2",
            "Canonical role scope changed",
        )
        sql += require(
            f"NOT EXISTS (SELECT 1 FROM public.user_roles WHERE role_id='{OLD_SUPER}') AND NOT EXISTS (SELECT 1 FROM public.users WHERE role='{OLD_SUPER}')",
            "Scoped Super Admin gained users",
        )
        sql += f"""
UPDATE public.user_roles SET role_id='{ADMIN}' WHERE role_id='{OLD_ADMIN}';
UPDATE public.users SET role='{ADMIN}' WHERE role='{OLD_ADMIN}';
UPDATE public.user_invitations SET role='{ADMIN}' WHERE role='{OLD_ADMIN}';
UPDATE public.organization_invitations SET role_id='{ADMIN}' WHERE role_id='{OLD_ADMIN}';
UPDATE public.settings SET value=replace(replace(value,'{OLD_ADMIN}','{ADMIN}'),'{OLD_SUPER}','{SALES}') WHERE key LIKE 'default_registration_role%';
"""
        sql += require(
            f"NOT EXISTS (SELECT 1 FROM public.user_roles WHERE role_id IN ('{OLD_ADMIN}','{OLD_SUPER}')) AND NOT EXISTS (SELECT 1 FROM public.user_invitations WHERE role IN ('{OLD_ADMIN}','{OLD_SUPER}')) AND NOT EXISTS (SELECT 1 FROM public.organization_invitations WHERE role_id IN ('{OLD_ADMIN}','{OLD_SUPER}'))",
            "Role still referenced before deletion",
        )
        sql += f"""
DELETE FROM public.role_permissions WHERE role_id IN ('{OLD_ADMIN}','{OLD_SUPER}');
DELETE FROM public.roles WHERE id IN ('{OLD_ADMIN}','{OLD_SUPER}');
INSERT INTO public.user_roles(id,user_id,role_id)
SELECT gen_random_uuid()::text,u.id,'{ADMIN}' FROM public.users u
WHERE u.role='Admin' AND NOT EXISTS(SELECT 1 FROM public.user_roles ur WHERE ur.user_id=u.id);
DELETE FROM public.role_permissions rp USING (
 SELECT id,row_number() OVER(PARTITION BY role_id,permission_id ORDER BY id) ordinal
 FROM public.role_permissions
) duplicates WHERE rp.id=duplicates.id AND duplicates.ordinal>1;
"""
        sql += expected_sql()
        sql += require(
            "NOT EXISTS(SELECT e.key FROM expected_grants e LEFT JOIN public.permissions p ON p.key=e.key WHERE p.id IS NULL)",
            "Approved catalog key missing",
        )
        sql += """
DELETE FROM public.role_permissions rp USING public.roles r,public.permissions p
WHERE rp.role_id=r.id AND rp.permission_id=p.id AND r.is_system_role
AND NOT EXISTS(SELECT 1 FROM expected_grants e WHERE e.role_id=r.id AND e.key=p.key);
INSERT INTO public.role_permissions(id,role_id,permission_id)
SELECT gen_random_uuid()::text,e.role_id,p.id FROM expected_grants e
JOIN public.permissions p ON p.key=e.key
WHERE NOT EXISTS(SELECT 1 FROM public.role_permissions rp WHERE rp.role_id=e.role_id AND rp.permission_id=p.id);
"""
        migration_path = (
            Path(__file__).resolve().parents[1] / "alembic/versions/p9e0f1a2b3c4_rbac_uniqueness.py"
        )
        spec = importlib.util.spec_from_file_location("rbac_forward_migration", migration_path)
        if spec is None or spec.loader is None:
            raise RuntimeError("Cannot load forward migration")
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        sql += require(
            "(SELECT count(*) FROM public.alembic_version)=1 AND (SELECT version_num FROM public.alembic_version)='o8d9e0f1a2b3'",
            "Unexpected migration revision",
        )
        sql += ";\n".join(migration.STATEMENTS) + ";\n"
        sql += "UPDATE public.alembic_version SET version_num='p9e0f1a2b3c4' WHERE version_num='o8d9e0f1a2b3';\n"
    else:
        sql += expected_sql()
    sql += integrity_sql(schema)
    sql += """
SELECT r.id,r.organization_id,r.name,count(rp.id) permission_count
FROM public.roles r LEFT JOIN public.role_permissions rp ON rp.role_id=r.id
GROUP BY r.id ORDER BY r.name;
SELECT r.name,p.key FROM public.roles r JOIN public.role_permissions rp ON rp.role_id=r.id
JOIN public.permissions p ON p.id=rp.permission_id WHERE p.key='emails:send' ORDER BY r.name;
SELECT r.name,count(ur.id) user_count FROM public.roles r LEFT JOIN public.user_roles ur ON ur.role_id=r.id GROUP BY r.id ORDER BY r.name;
COMMIT;
"""
    return sql


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("backup", "apply", "verify"))
    parser.add_argument("schema")
    parser.add_argument("--sql-only", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="Roll back the complete transaction")
    args = parser.parse_args()
    sql = build_sql(args.phase, args.schema)
    if args.dry_run:
        sql = sql.replace("COMMIT;", "ROLLBACK;")
    if args.sql_only:
        sys.stdout.write(sql)
        return
    subprocess.run(["render", "psql", TARGET, "--command", sql, "--output", "text"], check=True)


if __name__ == "__main__":
    main()
