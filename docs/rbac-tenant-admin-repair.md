# Missing tenant Admin repair — September 8, 2026

## Confirmed incident and scope

Read-only inspection of Render resource `dpg-dach4t15efls73eea3t0-a`
(`CRM-Postgres`) found revision `t4d5e6f7a8b9` and four tenant users
mapped to global Admin `b7d1b2d8-0e9c-4a6c-9c0a-2b2e6e3f7a11`.
None of their organizations has a local Admin. No multiple-role users were found.
Migration `u5e6f7a8b9c0` can remap global roles only when a same-name local role
already exists, so its cross-organization preflight blocks deployment.

The exact user/organization pairs are fixed in
`backend/scripts/prepare_tenant_admin_repair.py`. This is an incident-specific
data repair, not a schema migration or general role provisioning mechanism.

The first restored-production rehearsal also confirmed that the global Admin's
149 grants include platform-only `organization:delete` and omit `api_keys:revoke`.
The latter permission is absent from the permission table. The original repair
correctly aborted. The user approved handling these exact differences on the
four new tenant roles; no other permission drift is authorized.

## What the repair changes

- Inserts four organization-scoped system Admin roles with deterministic IDs.
- Creates one organization-scoped custom `testing` role for the reviewed pending
  invitation, preserving its name, description, and exactly `activities:read`,
  `calendar:read`, and `calls:read`. The global custom role is preserved. The
  invitation is remapped by the existing migration, not by this repair.
- Verifies the invitation's fixed ID, pending status, organization, and global
  role reference, the source custom-role identity and exact grants, and absence
  of a same-name local role before writing. It locks invitations as well as the
  existing RBAC tables. Changes to these reviewed facts abort the whole repair.
- Rejects every additional custom-role reference eligible for remapping in that
  organization: legacy user role values, user-role assignments, other user
  invitations (regardless of status), organization invitations, and scalar or
  JSON-array registration defaults. Whitespace is normalized as in the migration.
  Malformed/non-array plural defaults also abort. The organization-invitation
  and settings tables are locked with the other checked tables.
- Accepts exactly two source grant sets: the approved `ADMIN_PERMISSIONS`, or
  that set with `api_keys:revoke` replaced by `organization:delete`, as observed
  in the production backup. All other grant differences abort, including both
  of those keys present or both absent.
- Inserts `api_keys:revoke` only if its normalized key is absent, using the same
  ID and metadata as the existing migration. Existing permission rows and IDs
  are preserved. An ID conflict aborts rather than overwriting another record.
- Gives the new roles exactly the approved Admin catalog, reusing existing
  permission IDs. They receive `api_keys:revoke` and never `organization:delete`
  or `super_admin:manage`. Existing global-role grants are not edited by the repair.
- Leaves user identities, organizations, admin flags, assignments, existing roles,
  existing grants, invitations, settings, and the Alembic revision unchanged.
- Leaves reassignment and legacy-role cleanup to the existing Alembic migration.

The SQL locks the checked tables while verifying and inserting, uses a five-second
lock timeout and a thirty-second statement timeout per statement, and aborts on
changed user assignments, an unexpected revision/global role, or an existing local
Admin. All writes are in one transaction. A repeat after success aborts for review
instead of duplicating roles. It does not delete or overwrite existing data.

## Generate the reviewable SQL

From the repository root:

```bash
backend/.venv/bin/python backend/scripts/prepare_tenant_admin_repair.py > /tmp/tenant-admin-repair-dry-run.sql
backend/.venv/bin/python backend/scripts/prepare_tenant_admin_repair.py --commit > /tmp/tenant-admin-repair-apply.sql
```

Both commands only write SQL to stdout. They never connect to a database or load
dotenv files. The default SQL ends with `ROLLBACK`; `--commit` emits `COMMIT`.
Do not run either SQL file on production as part of preparation: even a rollback
rehearsal obtains locks and temporarily writes rows.

## Execution gates and recovery

1. Obtain independent review and user confirmation before proceeding beyond
   preparation. Verify a full production backup and restore it to isolated staging.
2. On the restored copy, execute the dry-run file through psql with
   `ON_ERROR_STOP=1`. Confirm four Admin roles with 149 grants each and one
   `testing` role with three grants in
   the output, and confirm no persistent changes. Any error requires rollback
and review; do not relax the guards.
3. Apply the commit SQL to that restored copy, then run the existing Alembic
   upgrade. Confirm all migration checks pass, each affected user has one local
   Admin assignment, `users.role` agrees, platform users retain global Super Admin,
   and cross-organization assignments remain rejected. Exercise affected login
   and authorization flows. Additional production-data issues may block later
   migration checks and require separate review.
4. Only after the restored-copy rehearsal passes, seek explicit production
   approval for the concrete SQL and migration execution. Pause role/user writes
   and deployment retries during the approved maintenance window. Pause invitation
   creation/acceptance/updates and default-role-setting mutations as well, across
   the entire repair-to-migration window. Table locks end at repair commit and
   cannot protect that gap; do not proceed without these maintenance controls.
   Recheck the
   target resource, backup, and current revision before execution.
5. Apply using psql with `ON_ERROR_STOP=1`, then run the approved migration/deploy
   workflow and repeat the verification above. Do not stamp Alembic or bypass the
   migration's guards. The repair alone does not complete the migration.

A failed repair transaction rolls back. If the repair committed but migration
fails, its five roles and newly inserted permission may remain; investigate rather
than blindly reapplying or deleting them. The existing migration is forward-only. Recovery after migration
requires a reviewed backup-restoration plan; never automatically downgrade or
delete roles that may now have assignments.

## Local validation

`backend/app/tests/integration/test_tenant_admin_repair.py` exercises synthetic
copies of the four assignments on disposable PostgreSQL, including reproduction
of the original migration failure, dry-run rollback, exact grants, preserved
users and custom/platform roles, successful migration, repeat refusal, drift
rejection, and the post-migration tenant-isolation trigger.
It covers both accepted source grant sets and preservation of an existing
normalized revoke permission ID.

Run using the existing dotenv-disabled isolated runner, pointed only at the
dedicated localhost `crm_workflow_test` database:

```bash
cd backend
CRM_WORKFLOW_TEST_DATABASE_URL=postgresql+asyncpg://workflow_test:disposable-test-only@127.0.0.1:55442/crm_workflow_test .venv/bin/python -m app.tests.run_isolated_workflow -q app/tests/integration/test_tenant_admin_repair.py app/tests/integration/test_rbac_hardening_migration.py
```

Synthetic tests do not replace a restored-production rehearsal or production
authorization testing. No production repair or migration has been executed during
preparation.

## Prior permission-only rehearsal and approved scope extension

The revised permission repair passed 27 tests on PostgreSQL 18.6, including both
accepted permission sets, migration regression coverage, and catalog tests. Scoped
lint, formatting, type checks, and Python compilation passed.

A restricted local backup was restored to an isolated PostgreSQL 18.6 instance.
All 101 table row counts and content fingerprints (2,682 rows) matched the source
snapshot. The original migration failure was reproduced with complete rollback.
The revised repair's dry run left every table unchanged. Applying it on the copy
inserted only four roles, their approved grants, and the missing revoke permission.

The subsequent migration rolled back at its separate invitation-role preflight:
pending user invitation `971a3ea1-ace7-4c5c-a4fb-ebeb57123e0b` references global
custom role `testing` (`680301a2-27df-49a8-8703-7302d1e343d2`) in organization
`e1f39188-e8e4-42db-8563-6e9ed72d9dc1`, which has no same-name local role.
That custom role grants exactly `activities:read`, `calendar:read`, and `calls:read`.
The other global-role user invitations have matching local Admin roles after this
repair. No organization-invitation or default-role-setting blockers were identified
on the restored copy.

On September 9 the user approved extending the repair to create the local custom
role while preserving the original role and invitation data. The combined repair
now covers that blocker; it requires fresh validation and independent review.
Production execution still requires separate explicit approval.

## Combined repair verification — September 9

All 33 tests passed on PostgreSQL 18.6, including the invitation remap,
preservation of invitation fields other than role, copied custom-role metadata
and exact grants, and rejection of invitation/custom-role drift. Scoped Ruff,
Black, mypy, and Python compilation passed.

The combined repair was rehearsed against the verified production backup in an
isolated PostgreSQL 18.6 container. All 101 source-table fingerprints and 2,682
rows matched before execution. The dry run made no persistent changes. The
applied repair inserted five roles, 599 grants, and one permission. The existing
migration then completed successfully to `u5e6f7a8b9c0`, remapped the four users
and the invitation, preserved user identities and organizations, and preserved
platform assignments and original global custom-role grants. An attempted
cross-organization mapping was rejected by the database trigger.

Using the existing HTTP auth and role routers against the migrated copy, all
four affected users passed login, `/auth/me`, exact Admin permission resolution,
and tenant-scoped role listing. Cross-tenant role access, organization switching,
and a read-only platform-permission probe were denied. Temporary test passwords
were used only in the disposable copy and restored afterward; production
credentials were neither used nor changed. Dotenv loading and external network
connections were disabled. This smoke test covers backend routes, not browser
UI, deployment configuration, or production password verification.

Production remains unchanged. Before execution, obtain explicit approval, verify
fresh production state and a current backup, and review the exact generated SQL
and maintenance plan. The backup used for rehearsal is the September 8 snapshot,
not proof that production has remained unchanged since then.

## Scope-guard review correction verification

The independent review identified that additional custom-role references could
become eligible for remapping when the local role is created. The user approved
the reference-inventory guards and expanded maintenance controls above.

After the correction, all 35 PostgreSQL 18.6 tests passed. The added test exercises
eight rejection cases for each accepted source-permission set: legacy user role,
user-role mapping, extra user invitation, organization invitation, scalar default,
array default, malformed JSON, and non-array JSON. Each case verifies complete
rollback without partial repair writes. Lint, formatting, type checks, and Python
compilation passed.

The guarded repair again passed the verified-backup rehearsal, full migration,
database isolation check, and all four users' backend login/authorization checks.
No production writes were performed. The separate-transaction maintenance window
and fresh production state/backup checks remain required before execution.
