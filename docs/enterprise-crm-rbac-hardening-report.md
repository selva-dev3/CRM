# Enterprise CRM RBAC Production Hardening Report

## 1. Executive Summary

**Before: FAIL**

**After: PARTIAL — production verification remains**

Verification on 2026-09-08: **1,551 backend unit and integration tests** pass
in one uninterrupted run (405.29 seconds; 78 warnings), including **1,449 unit
and 102 integration tests**. **417 frontend tests in 69 files** pass. Frontend
lint, TypeScript, production build (42 pages), and changed-file Python lint pass.
The integration suite used a disposable migrated PostgreSQL database. A final
read-only integrity audit found zero anomalies in all nine checked categories.

Permission replacement initially violated the unique role-permission constraint
because SQLAlchemy inserted overlapping replacements before deleting old rows.
Both mutation paths now flush the deletes within the same transaction before
inserting replacements. PostgreSQL tests verify both endpoints. The full unit
run also exposed a pre-existing logging filter error with numeric arguments;
formatting before redaction fixes it without exposing credential values. Tests
cover numeric formatting, quoted secrets, and Bearer/Basic authorization values.
Offline conversion of an existing tenant account to the global platform account
now removes its old role mapping before changing scope, within one transaction;
failure restores the original membership, role mapping, and password hash.

The application now has a fail-closed, explicit permission model for HTTP and
WebSocket operations. Tenant-managed roles can only receive registered tenant
permissions, the legacy `all` value has no authorization meaning, tenant users
resolve at most one organization-scoped role, and global authority comes only
from `User.is_platform_admin`.

Production readiness is not marked PASS. PostgreSQL verification now runs in a
disposable local container with no production data attached, and does not constitute production verification. Existing production RBAC records have not been inspected
or changed; the migration has not been applied to production.

## 2. Architecture Changes

The final request path is:

`authentication -> active session -> active organization context -> one role -> explicit approved permissions -> resource tenant validation -> business rule -> operation`

`backend/app/core/rbac_matrix.py` is the authoritative permission-key and
system-role policy. Backend permission dependencies, role provisioning, role
mutation, and effective-permission resolution consume that policy. The frontend
catalog mirrors it, with an automated exact-set comparison that fails on drift.

Platform authority is non-delegable. `is_platform_admin` is the authority for
platform operations; email and role-name strings do not grant it. The global
Super Admin keeps a NULL stored organization membership and uses the existing
request-scoped organization context. A single effective-organization resolver
propagates that validated context through `/auth/me`, organization, user, role,
and invitation operations without persisting tenant membership on the platform
account.

The product now uses one effective role per tenant user. A database uniqueness
constraint prevents multiple `user_roles` mappings. Multiple legacy mappings or
cross-organization mappings fail closed. A user with no valid mapping may use a
single organization-scoped legacy `User.role` value during transition; invalid
or global values grant no permissions.

## 3. Security Fixes

- Tenant role create/update/clone/assignment accepts only registered tenant
  permission keys. Unknown keys, `all`, `organization:delete`, and
  `super_admin:manage` are rejected.
- Runtime permission resolution ignores arbitrary database permission rows and
  has no wildcard expansion.
- Startup seeding no longer creates or grants global Admin or other tenant-role
  templates. It maintains only the global Super Admin and already provisioned
  organization system roles.
- All protected CRM routers are covered by a permission-dependency regression
  check. Public invitation tokens, authenticated self-service profile/session
  actions, and platform-only organization lifecycle routes are explicit
  exceptions.
- Nested resources require both parent read/tenant validation and the child
  module permission.
- Organization invitation and user create/invite/update role assignment require
  `users:assign_roles` in addition to the operation permission.
- API key requests continue through both API-key scope validation and current
  user RBAC. API keys cannot invoke platform-admin dependencies.
- `require_user_session` rejects API keys on account, password, 2FA, session,
  self-profile/avatar, and API-key management routes, preventing narrow keys
  from changing account security or minting broader credentials.
- Global platform users cannot create platform-owned tenant API keys. An
  organization user creates usable keys; the UI explains this restriction.
- Legacy user invitations expire after 24 hours from persisted `created_at`;
  public details and locked acceptance fail closed on expired/missing timestamps.
  Expired invitations no longer block a new invite to that email.
- Legacy invitation acceptance never reactivates an existing account or changes
  its credentials. Direct creation and acceptance serialize membership limits
  and subscription usage with the organization lock.
- Invitation batches commit atomically before sending email. A delivery failure
  explicitly reports that invitations were saved.
- Authorization denials log actor ID, organization ID, and required permission
  without credentials or tokens.
- Frontend authorization no longer treats `all`, email text, or role-name text as
  authority. Role selection no longer silently assigns an Admin fallback.
- Role deletion locks the target role, rejects every durable user, invitation,
  and default-setting reference, and is backed by a restrictive user-role
  foreign key. Role assignment and invitation flows take a compatible role lock.
- The final active organization Admin cannot be deactivated or demoted; active
  organization users are locked so concurrent demotions cannot bypass the rule.
- Bulk user deactivation requires `users:delete`, matching the equivalent
  single-user destructive operation.

## 4. Permission Changes

| Operation | Previous permission | Final permission |
|---|---|---|
| Task export | `tasks:read` | `tasks:export` |
| Task import | `tasks:create` | `tasks:import` |
| Meeting export | `meetings:read` | `meetings:export` |
| Quote export | `quotes:read` | `quotes:export` |
| Quote import | `quotes:create` | `quotes:import` |
| Invoice export | `invoices:read` | `invoices:export` |
| Invoice import | `invoices:create` | `invoices:import` |
| Report delete | `reports:create` | `reports:delete` |
| Administrative password reset | `users:update` | `users:reset_password` |
| API key list | `integrations:apikeys` | `api_keys:read` |
| API key create | `integrations:apikeys` | `api_keys:create` + login session |
| API key revoke | `integrations:apikeys` | `api_keys:revoke` + login session |
| AI configuration | settings permissions | `ai:configure` |
| Organization member management | generic organization permissions | `organization:members` |
| Ownership transfer | `organization:update` | `organization:transfer_ownership` |
| User/invitation role selection | `users:roles` or invitation-only | `users:assign_roles` plus operation permission |
| Bulk user deactivation | `users:update` | `users:delete` |
| Organization deletion | tenant Admin catalog | platform-only `organization:delete` plus platform-admin dependency |

Registered permissions without a routed product action are explicitly tracked
by the consistency test: `activities:create`, `activities:export`,
`contacts:assign`, `contacts:bulk_update`, `dashboard:export`,
`documents:share`, and `projects:assign`. `super_admin:manage` is intentionally
enforced through the non-delegable platform-admin dependency rather than normal
tenant RBAC.

## 5. Role Changes

- The six tenant system roles remain Admin, Sales Manager, Sales Executive,
  Marketing Executive, Customer Support, and Read Only.
- Tenant system roles remain organization-scoped and immutable through tenant
  role APIs.
- The global Super Admin is the only global system role.
- Tenant Admin no longer receives platform-only organization deletion.
- Custom roles are scoped to the current organization, protected by normalized
  name uniqueness, and cannot use reserved system-role names.
- Role creation, update, cloning, permission replacement, assignment, and
  deletion commit atomically and roll back on failure.
- Assigned custom roles cannot be deleted.

## 6. Frontend Changes

- Added the missing permission keys to the centralized frontend catalog.
- Removed wildcard permission behavior and legacy email/role authority checks.
- Added or corrected gates for call, meeting, note, email, notification, task,
  quote, invoice, report, integration, API-key, user, role, and organization
  actions.
- User create/invite actions require their operation permission,
  `users:assign_roles`, and `roles:read` because the form must load an
  assignable role.
- Organization profile, branding, member, billing, domain, ownership, and audit
  actions and queries use their exact permission gates. Unauthorized tabs are
  omitted and their queries remain disabled.
- Role selectors use the backend's tenant-scoped assignable-role response and do
  not choose a fallback role.
- Role and permission mutation hooks invalidate role/user queries and trigger an
  authoritative `/auth/me` refresh in the current tab and other tabs.
- Initial API-key creation requires `api_keys:create`; regeneration additionally
  requires `api_keys:revoke`. Role permission selection/removal requires
  `roles:assign`, and protected system roles remain immutable.
- Existing platform organization selection and switching behavior is retained.

## 7. Backend Changes

- Standardized authorization on `require_permission()` plus explicit
  `require_platform_admin` for platform lifecycle operations.
- Removed `require_role()` and role-name based business authorization.
- Effective permissions are loaded from current role mappings on every request;
  they are not stored in JWT claims.
- The validated platform tenant selection is returned by `/auth/me` and is used
  consistently by role, user, organization, and invitation services.
- Corrected export/import, password reset, API key, AI, organization, and report
  permission mismatches.
- Added parent and child permissions to company, contact, deal, lead, quote, and
  invoice related-resource routes.
- User access-state and role-member endpoints now require their matching user
  permissions, and permission grant changes require `roles:assign`.
- Enforced exact organization ownership in role repositories, user management,
  invitation onboarding, and ownership transfer.
- Replaced fabricated role audit output with persisted `AuditLog` reads.
- Role lists batch-load permission grants instead of issuing one query per role.

## 8. WebSocket Changes

WebSockets authenticate the JWT, validate the live session, active user, active
organization, explicit organization context, and `notifications:read`. The
connection revalidates session, user, organization, membership, and permissions
at most every 30 seconds and before processing each client message, including
session expiration. Each authorization read transaction ends before the socket
waits for network input, so long-lived sockets do not pin pooled connections.

Client-originated publishing is denied. Publishing remains on the separately
permission-gated HTTP system-alert path. Server broadcasts are filtered by
organization, and platform administrators use the existing explicit request
organization context without changing their stored NULL membership.

## 9. Database Changes

Migration `u5e6f7a8b9c0_harden_rbac_integrity.py` is forward-only and:

- locks affected tables for the migration transaction before compatibility checks;
- provisions missing approved permission catalog rows;
- canonicalizes mixed-case or whitespace-padded approved keys while preserving
  permission IDs and role mappings;
- expands legacy wildcard grants to explicit permissions while withholding
  platform-only keys from tenant roles;
- removes wildcard mappings and the wildcard permission row;
- remaps legacy global tenant-role mappings and stored role IDs to an equivalent
  role in the user's organization;
- remaps legacy role references in both invitation tables and organization
  default-role settings while preserving ordered and non-string JSON elements,
  trims string IDs, and aborts on unresolved references to global roles being removed;
- blocks migration when ambiguous multiple-role or cross-organization records
  need reviewed cleanup;
- safely removes unreferenced legacy global tenant system-role templates;
- adds one-role-per-user uniqueness;
- changes the user-role role foreign key to `ON DELETE RESTRICT`;
- adds PostgreSQL insert/update triggers preventing cross-organization user-role
  mappings and serializes relevant role/user scope changes with transaction
  advisory locks;
- adds a database check rejecting the `all` permission key.

Historical migrations were not edited. Existing arbitrary permission rows are
preserved for a reviewed data-cleanup decision but cannot be assigned or enforced
by tenant role APIs.

## 10. Audit Logging

Real audit records are persisted in the role/user transaction for role creation,
role update, permission replacement/removal, role deletion, cloning, and role
assignment, legacy invitation creation, and role assignment on invitation
acceptance. Records contain actor, organization, action, target, before/after
state, and database timestamp where supported. Passwords, tokens, and secrets
are not included.

## 11. Tests

Backend command run in `backend/`; frontend commands run in `frontend/`:

```bash
# RBAC_TEST_DATABASE_URL denotes the disposable localhost crm_workflow_test DB.
# The actual run used localhost port 55442, with synthetic test credentials.
CRM_DISABLE_DOTENV=1 SECRET_KEY=test-only DATABASE_URL="$RBAC_TEST_DATABASE_URL" CRM_WORKFLOW_TEST_DATABASE_URL="$RBAC_TEST_DATABASE_URL" AWS_SECRET_ACCESS_KEY=test-secret .venv/bin/pytest -q app/tests/unit app/tests/integration
# 1551 passed, 78 warnings in 405.29 seconds.

npm test -- --reporter=dot
# 417 passed in 69 files.
npm run lint
npx tsc --noEmit
npm run build
# All pass; production build generates 42 pages.
```

The strengthened invitation-acceptance/cache regression was subsequently run
separately: all 5 tests in that file pass. It verifies that actual AuthProvider
login handling clears the previous organization, cached tenant data, and an
in-flight tenant request. Repeated manual-invoice integration runs also pass,
verifying cleanup of the test-owned secondary organization.

The 78 backend warnings include dependency/Starlette deprecations and unawaited
AsyncMock warnings in notification-service unit tests. The run passes, but is
not warning-free; those warnings are not evidence of production verification.

Changed Python files pass `ruff check`; `git diff --check` passes. Catalog
consistency, WebSocket revocation/isolation, permission denial, role transactions,
nested-resource gates, invitation expiry, and logging-redaction tests are included
in the full unit suite. PostgreSQL tests exercise migration remapping and
concurrent cross-tenant mapping rejection, actual role replacement, singleton
platform identity, login, switching, and scoped invitation member limits.

Sandboxed Python runs stalled during asyncio teardown. The uninterrupted combined
unit and integration run passes outside that sandbox. No production database is used by tests.

## 12. Security Verification

| Verification | Result |
|---|---|
| Unknown/arbitrary permission rejection | PASS |
| Legacy `all` authorization rejection | PASS |
| Platform permission non-delegation | PASS |
| Multiple-role fail-closed behavior | PASS |
| Cross-organization role assignment | PASS |
| Route permission coverage | PASS |
| Nested parent/child permission coverage | PASS |
| Export/import exact permissions | PASS |
| Password reset exact permission | PASS |
| API-key scope plus RBAC | PASS |
| WebSocket client publish denial | PASS |
| WebSocket permission revocation | PASS |
| WebSocket tenant isolation | PASS |
| Frontend/backend catalog equality | PASS |
| Isolated PostgreSQL migration | PASS |
| Complete isolated integration suite | PASS |
| Isolated database integrity audit (nine anomaly categories) | PASS |
| Existing production RBAC data audit | NOT VERIFIED |

An isolated read-only database audit checks normalized permission/role duplicates,
multiple user roles, duplicate grants, orphan mappings, cross-tenant mappings,
wildcard rows, and platform accounts with tenant membership. These checks apply
only to the disposable test database, not existing production records. Each
category returned zero anomalies; the database was at migration
`u5e6f7a8b9c0`.

Independent review by a different model completed with **PASS** after the final
combined test run. It reported no remaining blocking or actionable issues in
correctness, security, tenant isolation, transactions, migrations, performance,
frontend cache behavior, or regressions. This verdict covers the current change
and isolated verification, not production deployment.

## 13. Remaining Issues

1. Verify a backup and restoration procedure, then run the forward-only migration
   against a restored production snapshot or
   isolated staging PostgreSQL database. Review and remediate any migration block
   identifying multiple roles, cross-organization mappings, or unresolved legacy
   global role IDs.
2. Inspect arbitrary/obsolete permission rows reported by the database. They are
   inert after this change but intentionally not deleted without record-level
   review.
3. Verify production configuration and a controlled post-deployment login/switching
   smoke test after a reviewed snapshot migration.
4. Decide whether the registered permissions without product actions should gain
   endpoints or be retired in a later reviewed catalog migration.

## 14. Production Readiness

**PARTIAL — Remaining Verification**

Deployment approval must wait for a production-snapshot data compatibility
audit and production configuration verification, followed by a controlled
post-deployment smoke test. Passing isolated tests alone is not a production
readiness claim.
