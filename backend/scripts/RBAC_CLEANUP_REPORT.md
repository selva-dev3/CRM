# Render RBAC cleanup — 2026-09-07

Target: `render psql dpg-dach4t15efls73eea3t0-a`, resource `CRM-Postgres`,
database `crm_postgres_om2o`, user `crm_postgres_om2o_user`, PostgreSQL 18.6.
The cleanup was rehearsed with ROLLBACK, then COMMITted and independently verified.

## Recovery point

Schema `rbac_recovery_20260907_120000`, captured at **2026-09-07 15:15:59 UTC**,
contains the full original roles, permissions, role_permissions and user_roles;
user and invitation role projections; and registration settings. It contains no
passwords or invitation tokens. Access to the recovery schema was revoked from
PUBLIC. This is a recovery point for these changes, not a full database backup.

Do not delete the recovery schema until deployment and acceptance are complete.
Restoration must be reviewed against intervening writes. In a maintenance window,
lock the affected tables, downgrade the four new indexes through the forward
migration's downgrade, restore the two removed role rows from the snapshot, then
restore their grants, the migrated user's role/mapping, the two invitation role
values and the two registration settings. Reverse the permission differences
from the snapshot only after checking for later legitimate changes. Remove the
new legacy Admin mapping only if unchanged. Never overwrite whole users or
invitation tables, restore credentials, or reset passwords. Verify all references
and role scope before committing; roll back on any unexpected state.

## Root cause and scope

Historical migrations separately initialized global Admin/Super Admin while older
tenant-scoped versions existed. The role list legitimately returned global plus
tenant roles, exposing both. There were no normalized role-name or relationship
pair uniqueness constraints. Permission seeding did check-before-insert on startup
and on GET of the permission matrix, allowing concurrent duplicate project links.
The exact historical process that inserted each duplicate link is not recorded.

Permission keys were already unique. `users:roles` and `users:assign_roles` share
the display label "Assign User Roles" but are both approved, distinct keys. No
permission records were deleted and no unique display-name constraint was added.

## Canonicalization performed

| Role | Canonical ID | Removed ID |
|---|---|---|
| Admin | b7d1b2d8-0e9c-4a6c-9c0a-2b2e6e3f7a11 | 95efa96f-4d75-46ff-9e2f-183a16f7531d |
| Super Admin | 65bde2ea-0a91-47c1-b1c4-715c084d152f | 930f5fd6-d977-4bd2-a69b-6fc071a021cb |

Both canonical roles are global. The removed roles belonged to organization
`e1f39188-e8e4-42db-8563-6e9ed72d9dc1`. Global Admin already served multiple
organizations. One tenant Admin mapping and users.role were migrated, along with
two invitation references. The removed Super Admin had no users, but two legacy
default settings referenced it; these now reference the existing Sales Executive.
One previously unmapped legacy Admin user received an explicit global Admin link,
preserving their existing effective access. All five users and their organizations
are unchanged. Final mappings: four Admin, one Super Admin.

Other system roles retain their existing tenant scope. `testing` and its three
grants and pending invitation are preserved. No global copies of tenant roles
were created. Consequently other organizations still see the global roles plus
their own roles, not tenant roles belonging to My CRM.

## Exact permission changes

| Retained system role | Extra removed | Missing added | Final unique grants |
|---|---:|---:|---:|
| Super Admin | 0 | 151 | 151 |
| Admin | 0 | 0 | 149 |
| Sales Manager | 5 | 5 | 107 |
| Sales Executive | 8 | 4 | 50 |
| Marketing Executive | 9 | 4 | 30 |
| Customer Support | 6 | 3 | 29 |
| Read Only | 4 | 1 | 19 |

Additionally removed: 290 links belonging to the two removed roles and five
duplicate Admin project links. Total: 32 unapproved grants removed, 168 missing
grants added, 535 system grants plus three custom grants remain.

- Sales Manager removed emails:delete, notifications:read/send, reports:delete,
  users:read; added all five projects permissions.
- Sales Executive removed calendar:sync, calls:recording, contacts:assign,
  deals:assign, leads:assign, notifications:read/send, quotes:create; added
  contacts:export, deals:export, invoices:read, leads:export.
- Marketing removed activities:export, companies:export, dashboard:export,
  notes:create/read/update, notifications:read/send, reports:create; added
  calendar:write, meetings:create/update, tasks:complete.
- Support removed calls:recording, contacts:create, documents:share, notes:delete,
  notifications:read/send; added ai:read, invoices:read, leads:read.
- Read Only removed notifications:read, organization:read, roles:read, users:read;
  added projects:read.

## Migration and initialization

New revision `p9e0f1a2b3c4`, parent `o8d9e0f1a2b3`, adds unique indexes:

- roles(organization_id, lower(btrim(name))) NULLS NOT DISTINCT
- permissions(lower(btrim(key)))
- role_permissions(role_id, permission_id)
- user_roles(user_id, role_id)

The controlled Render runner executes this new migration's SQL and updates the
Alembic revision in the same verified transaction. Historical migrations are
unchanged. The normal migration refuses dirty data instead of automatically
deleting it. PostgreSQL 15+ is required for NULLS NOT DISTINCT (target is 18.6).

Backend changes add one approved matrix, supply missing approved catalog keys,
serialize startup initialization with a transaction advisory lock, reconcile
system grants, preserve existing scopes and custom roles, reserve system names
against custom recreation, remove writes from the matrix GET, and propagate
permission-persistence failures. These source changes require commit and deployment;
database uniqueness is already active.

## Verification

The cleanup and independent verification asserted: exact matrix equality; seven
system roles; no duplicate keys/links; no dangling user or permission references;
no cross-organization mappings; preserved custom roles/grants and user identities;
and no references to deleted role IDs. Email sending is explicitly assigned to all
six writable system roles and absent from Read Only.

Rollback-only insert probes confirmed rejection of duplicate global roles, tenant
roles, normalized permission keys, role-permission pairs and user-role pairs.

Run post-deployment verification using:

```sh
backend/.venv/bin/python backend/scripts/cleanup_render_rbac.py verify rbac_recovery_20260907_120000
```

Do not rerun `apply`: it intentionally refuses snapshot drift after the first run.
`backup`, `apply --dry-run`, and `apply` are explicitly controlled operations.

Final verification after incorporating upstream PRs #151 and #152: all **1,090 backend unit tests** passed, including the RBAC
matrix, repeated initialization, role APIs, authorization and migration graph
tests. All **368 frontend tests**, frontend lint, TypeScript and production build
passed. Backend lint and targeted mypy passed. The Alembic graph test was updated
to the new head with user approval. Tests used synthetic settings, not .env or
production credentials. Existing mock/deprecation warnings remain.

All **59 PostgreSQL workflow integration tests were skipped** because an isolated
test database was not configured; never point those tests at this production
database. Render cleanup and uniqueness tests were separately executed against
the actual database as described above. Live browser verification could not run
because no browser was connected. No credentials were created or sessions
impersonated.

## Remaining deployment considerations

The live database is already at the new revision, so deploy this migration file
with the backend source before running further Alembic upgrades. Do not redeploy
an older checkout that cannot resolve the new revision. Code has not been pushed
or deployed without the separate Git confirmation required by repository rules.
Authenticated Roles/Users page and HTTP workflow checks remain required after
deployment; database and unit checks do not substitute for those checks.
