# Roles, Permissions, and Organization Flow Audit

Audit date: September 7, 2026<br>
Source revision: `b792769`<br>
Database: `crm_postgres_om2o`<br>
Final database verification: September 7, 2026, 16:16 UTC<br>
Scope: analysis and verification only; no implementation or data cleanup authorized by this report.

## 1. FINAL VERDICT

**FAIL**

The required architecture is not implemented. Some tenant checks and duplicate protections work, but:

- Organizations do not automatically receive six organization-scoped default roles.
- All four organizations currently share one **global Admin** role.
- A **global custom role** is visible and assignable across organizations.
- One Super Admin account exists, but organization access remains restricted to its user's organization.
- Organization Admin permissions reach a database-wide reset operation.
- Organization member removal can delete the Super Admin account.

**Audit evidence:** source at `b792769`, live PostgreSQL database `crm_postgres_om2o`, existing recovery snapshot, and 213 passing backend unit tests. Database queries ran in database-enforced `READ ONLY` transactions.

No code, schema, role, permission, user, or data changes were made by the auditor during the audit. The shared checkout changed externally during inspection from `fix/rbac-canonical-cleanup` to `main`; the auditor did not perform that change. This Markdown file was subsequently created at the user's request to preserve the complete report.

Live login/browser workflows were not executed. Runtime conclusions below distinguish database observations, source tracing, and mocked verification. Database findings describe the audited snapshot, not a guarantee about later changes.

## 2. REQUIRED FLOW VS CURRENT FLOW

| Requirement | Expected | Current Implementation | Status |
|---|---|---|---|
| Organization creation | Create six defaults automatically | Registration/invitation creates organization without provisioning roles | FAIL |
| Default role scope | Separate records for each organization | Admin is global; five other defaults belong only to My CRM | FAIL |
| Super Admin account | One global account | One active account exists; singleton not enforced | PARTIAL |
| Super Admin access | Same login manages every organization | Resource checks restrict it to `users.organization_id` | FAIL |
| Custom role creation | Organization-scoped | Current create/clone endpoints derive scope server-side | PASS for these paths |
| Existing custom role isolation | No global custom roles | `testing` has `organization_id = NULL` | FAIL |
| Same name across organizations | Allowed with distinct IDs | Current unique index permits this | PASS |
| Duplicate names within organization | Prevented | Normalized scope/name unique index exists and is valid | PASS |
| Role assignment | Own organization or global Super Admin only | Own organization **or any global role** accepted | FAIL |
| Foreign organization role IDs | Rejected server-side | Explicitly scoped foreign roles rejected | PASS for inspected guarded paths |
| Permission assignment duplicates | Prevented | Valid unique `(role_id, permission_id)` index | PASS |
| Permission matrix | Correct grants per organization | Existing system-role grants match local matrix; role instances are missing/mis-scoped | PARTIAL |
| Membership/context | Explicit organization access | Single `users.organization_id`; no membership table or switching flow | FAIL for global administration |
| Frontend permissions | Show actual grants | Every system-role detail page displays the full catalog | FAIL |
| Database tenant relationships | Reject cross-organization assignments | FKs validate existence, not organization equality | FAIL |
| Global administration security | Restricted to Super Admin | Tenant-level permissions reach global operations | FAIL |

**Actual organization-scoped defaults:**

| Organization | Organization ID | Scoped defaults present | Missing |
|---|---|---|---|
| My CRM | `e1f39188-e8e4-42db-8563-6e9ed72d9dc1` | Sales Manager, Sales Executive, Marketing Executive, Customer Support, Read Only | Admin |
| Susanoox | `98543cc4-3667-426d-97b6-f23826f55f8a` | None | All six |
| test | `ae1e5a8d-24a3-4da8-bdf1-23a879fc4cb1` | None | All six |
| 12345 | `c04bc09a-73e5-4aa0-8205-1c1b709b7004` | None | All six |

## 3. SUPER ADMIN AUDIT

### Current account and global access

**Exactly one account currently exists, but the application does not enforce that requirement.**

The database contains one active Super Admin user:

- User: `3214b610-dfd5-46fb-83e1-3cbe9d3afc55`
- `users.role`: `super_admin`
- Organization: My CRM
- Mapped global role: `65bde2ea-0a91-47c1-b1c4-715c084d152f`

Credential validity was not tested, and passwords were not inspected.

**Global permissions resolve, but global organization access does not.**

[`AuthService.get_user_permissions`](../backend/app/services/auth_service.py) expands an authorized global Super Admin role to every permission key. However:

- [`get_current_user`](../backend/app/api/v1/deps.py) requires an active organization on the user.
- [`OrganizationDomainService._require_requested_org`](../backend/app/services/organization_service.py) rejects any requested organization different from that user's organization.
- Users and Roles services apply the same current-organization restriction.
- No organization-context switching implementation was found.

Mocked verification confirmed that a Super Admin targeting another organization receives rejection **before the organization repository is read**.

### JWT/session flow

`login → password verification → active user/organization validation → JWT/session creation → permission resolution`

The JWT contains `sub` and `exp`. Organization and roles are resolved from database records, rather than trusted frontend claims. Access sessions are checked against a stored token digest; refresh tokens are persisted and rotated.

The token format could support global administration, but the current authorization/context implementation does not.

### Singleton and account protection failures

- A Super Admin actor can assign the global Super Admin role to another user. No singleton constraint prevents this.
- Super Admin identity checks are inconsistent: permission resolution considers mappings, while `is_super_admin_user` primarily follows `users.role`.
- Some Users operations protect a hardcoded email address, rather than a platform identity.
- [`OrganizationDomainService.remove_member`](../backend/app/services/organization_service.py) bypasses that protection and deletes the user record. Mocked verification confirmed this path accepts a Super Admin target.
- Ordinary role reassignment does not protect the existing Super Admin from demotion.
- Deleting its organization cascades to its user account.
- Disabling its organization prevents login/session use.

### Historical duplicate records

The recovery snapshot `rbac_recovery_20260907_120000` confirms:

| Role ID | Historical scope | Historical mappings | Current state |
|---|---|---:|---|
| Admin `95efa96f-4d75-46ff-9e2f-183a16f7531d` | My CRM | 1 | Absent |
| Admin `b7d1b2d8-0e9c-4a6c-9c0a-2b2e6e3f7a11` | Global | 2 | Present; now 4 mappings |
| Super Admin `930f5fd6-d977-4bd2-a69b-6fc071a021cb` | My CRM | 0 | Absent |
| Super Admin `65bde2ea-0a91-47c1-b1c4-715c084d152f` | Global | 1 | Present; 1 mapping |

These were **global-plus-tenant records**, not evidence of separate Super Admin logins for every organization.

The old organization-scoped Admin had a legitimate tenant assignment. Retaining only global Admin removed the duplicate-looking display but conflicts with the required architecture.

## 4. DEFAULT ROLE CREATION AUDIT

**No inspected organization-creation path provisions the required six roles.**

### Registration — `POST /api/v1/auth/register`

[`AuthService.register`](../backend/app/services/auth_service.py):

1. Finds the Free subscription plan.
2. Creates the organization.
3. Creates the initial user with `role = "Admin"`.
4. Creates organization settings and subscription.
5. Looks up an existing Admin role.
6. Creates a user-role mapping.
7. Commits the transaction.

[`AuthRepository.get_role_for_organization`](../backend/app/repositories/auth_repository.py) accepts either the organization's role or a global role. For new organizations, this selects the existing global Admin. It does not create defaults.

If no eligible Admin exists, registration fails with `RBAC_NOT_INITIALIZED`.

### New-organization invitation — `POST /api/v1/organizations/invitations/new-organization`

[`create_new_organization_invitation`](../backend/app/services/invitation_service.py) resolves a **global role before creating the organization**, then creates the organization, settings, subscription, and invitation. It creates no roles or role-permission assignments.

### Invitation acceptance

[`accept_organization_invitation`](../backend/app/services/invitation_service.py) can also create an organization for legacy invitations. It likewise does not provision defaults.

### Startup

[`RoleRepository.synchronize_system_roles`](../backend/app/repositories/role_repository.py):

- Iterates system-role names across the whole database.
- Preserves existing scopes.
- Creates a missing role globally.
- Treats a role existing in one organization as sufficient.
- Reconciles existing system-role grants.
- Rejects a scoped Super Admin.

This is **database-wide template initialization**, not per-organization provisioning. On a clean database, it creates all seven system roles globally.

The current startup advisory lock and database uniqueness protect against certain duplicates, but do not correct this architecture.

## 5. CUSTOM ROLE AUDIT

**Current creation is scoped correctly; existing global custom roles remain exposed.**

[`RoleService.create_role`](../backend/app/services/role_service.py) and `clone_role` derive organization scope from the authenticated user. Request schemas do not expose a writable `organization_id`.

Explicit foreign-organization custom roles are rejected for reading, editing, deleting, permission changes, and assignment through the inspected guards.

However, the live database contains:

- Role: `testing`
- ID: `680301a2-27df-49a8-8703-7302d1e343d2`
- `organization_id`: **NULL**
- `is_system_role`: **false**
- Permissions: `activities:read`, `calendar:read`, `calls:read`
- Referenced by a pending My CRM user invitation.

[`RoleRepository.list_roles`](../backend/app/repositories/role_repository.py) returns current-organization roles **plus all global roles**.

`_ensure_assignable_role_ownership` also accepts every global role. Therefore, an authorized user in another organization can list, read, assign, or clone `testing`.

Its edit/delete paths reject it because mutable roles must match the current organization exactly. Thus, it is globally exposed and assignable, but not normally editable through these endpoints.

The database does not prohibit creating another global custom role outside the guarded API.

### Backend operation coverage

| Operation | Server-side behavior |
|---|---|
| List / assignable list | Current organization plus global roles; assignable list excludes Super Admin by name |
| Get role | Rejects foreign scoped role; accepts global role |
| Create / clone | New role uses authenticated organization |
| Update / delete / bulk delete | Requires matching organization; system roles immutable |
| Assign role to user | Requires same-organization target user; role may be own organization or any global role |
| Replace / remove permissions | Requires matching organization; system roles immutable |
| Set registration default | Accepts own/global role; does not exclude Super Admin |
| Create/import permission definitions | Requires `roles:create`; changes global catalog |

## 6. ROLE-PERMISSION AUDIT

### Reported duplicate assignments

**The five reported duplicates existed historically, but do not exist now.**

For role `b7d1b2d8-0e9c-4a6c-9c0a-2b2e6e3f7a11`:

| Permission ID | Recovery snapshot count | Current count |
|---|---:|---:|
| `projects-assign-permission` | 2 | 1 |
| `projects-create-permission` | 2 | 1 |
| `projects-delete-permission` | 2 | 1 |
| `projects-read-permission` | 2 | 1 |
| `projects-update-permission` | 2 | 1 |

Current queries found:

- No duplicate role-permission pairs.
- No dangling role-permission references.
- No duplicate user-role pairs.
- No explicitly cross-organization user-role mappings.

### Why duplicates could occur

The historical implementation used check-before-insert in `RoleRepository.seed_permissions`, without relationship-pair uniqueness. Seeding ran both at startup and from `GET /roles/permissions/matrix`. The Docker startup command uses two workers.

Concurrent executions could both observe a missing assignment and insert different mapping IDs for the same pair.

This mechanism is established from source. **The exact process/request that inserted each historical duplicate is not recorded by the available evidence.**

### Current protection

Migration [`p9e0f1a2b3c4`](../backend/alembic/versions/p9e0f1a2b3c4_rbac_uniqueness.py) installs unique indexes. Live inspection confirmed they are unique, valid, and ready.

Current source also removes matrix-GET seeding and serializes startup initialization.

### Current permission matrix comparison

Actual grant keys, not just counts, were compared against the repository's declared approved [RBAC matrix](../backend/app/core/rbac_matrix.py).

| Existing role | Grants | Missing keys | Extra keys |
|---|---:|---:|---:|
| Super Admin | 151 | 0 against current catalog | 0 |
| Admin | 149 | 0 | 0 |
| Sales Manager | 107 | 0 | 0 |
| Sales Executive | 50 | 0 | 0 |
| Marketing Executive | 30 | 0 | 0 |
| Customer Support | 29 | 0 | 0 |
| Read Only | 19 | 0 | 0 |

No separate business-approved matrix was supplied; this verifies equality with the repository matrix, not independent approval of its policy.

### Remaining problems

- Correct grants on shared/missing roles do not satisfy tenant isolation.
- Permission creation and import affect the global catalog but are available through `roles:create`.
- Custom role creation can create unknown permission definitions automatically.
- Grant assignment does not enforce a delegable-permission boundary.
- Unknown permissions in update/assignment requests can be silently omitted.
- Create, update, and clone commit role changes separately from grants, allowing partial completion.
- System roles are immutable through the API even for Super Admin.
- Duplicate prevention does not provide concurrency-safe replacement semantics for simultaneous permission edits.

## 7. USER-ROLE AUDIT

**There are two authorization representations:**

1. `users.role`, containing a name or role UUID.
2. `user_roles`, containing role mappings.

`AuthService.get_user_permissions` combines these representations, then filters eligible roles by organization/global scope.

### What works

- Current create/update/assignment paths reject explicitly foreign scoped roles.
- User-by-ID operations generally require the same organization.
- `/auth` user-invitation acceptance revalidates organization and role.
- Its repository replaces all existing mappings.

### What fails

- Every global role is eligible, including global Admin and `testing`.
- `RoleService.assign_role_to_user` and `UserService.update_user` replace only the first mapping. Additional mappings can retain previous privileges.
- `user_roles` uniqueness is per pair, not per user; multiple roles remain possible despite singular-role application behavior.
- Ownership transfer changes only `users.role = "Admin"` and leaves mappings untouched.
- Name lookup can select an arbitrary organization's same-named role before ownership validation.
- Deleting a custom role cascades its mappings, but leaves `users.role` and invitation strings without referential protection.

### Organization-invitation flow is weaker than `/auth` invitation acceptance

`accept_organization_invitation`:

- Does not revalidate the invited role against the target organization.
- Stores role names rather than establishing a canonical mapping.
- Can overwrite an existing user's password and organization without the active-account/cross-organization checks used by `/auth` acceptance.
- Does not clear existing user-role mappings.
- Updates organization onboarding fields without restricting that behavior to an initial Admin invitation.
- Lacks the locked invitation-consumption flow used by `/auth` acceptance.

Additionally, organization invitation creation looks up pending invitations by email without tenant scope and can repoint an existing invitation.

These are source-confirmed paths; they were not exercised against live users.

## 8. DATABASE CONSTRAINT AUDIT

### GOOD

- Primary keys on all inspected core tables.
- Valid normalized role uniqueness: `(organization_id, lower(btrim(name))) NULLS NOT DISTINCT`.
- Same role name permitted in different organizations.
- Valid permission-key uniqueness, including normalized keys.
- Valid unique role-permission and user-role pairs.
- Non-null relationship IDs.
- Foreign keys from roles/users to organizations.
- Foreign keys from relationship tables to users, roles, and permissions.
- Supporting foreign-key indexes.
- No currently dangling relationship rows.

### MISSING

- Database enforcement that non-Super-Admin roles must be organization-scoped.
- Database enforcement that Super Admin must be global.
- A singleton platform-account invariant.
- Organization-equality enforcement for user-role assignment.
- A single-role-per-user constraint, if singular roles remain the policy.
- Canonical role references for `users.role` and invitations.
- A foreign key for `user_invitations.organization_id`.
- Stable system-role identity independent of display names.

No membership table, custom enforcement triggers, or row-level security was present on the inspected RBAC/user tables. RLS is optional defense in depth; its absence is not itself the root problem.

### RISK

- `users.organization_id` is non-null with `ON DELETE CASCADE`: deleting the Super Admin's host organization deletes the platform account.
- Role deletion removes mappings but leaves legacy string references.
- Name normalization does not unify recognized aliases such as `Super Admin` and `super_admin`.
- Historical Admin migration `c9d4e5f6a7b8` checks whether each user already has that particular Admin mapping—not whether they already have any role—so it can add Admin to already-assigned users.
- That migration's downgrade selects Admin by name without identifying the exact originally-created role.
- `IF NOT EXISTS` index creation would not detect an incorrectly defined pre-existing index with the same name. The current live indexes were independently checked and are correct.

## 9. FRONTEND AUDIT

### Roles list

[Roles API hooks](../frontend/src/lib/api/roles.ts) fetch `/roles` and `/roles/assignable` without organization parameters. That correctly leaves authorization to the backend, but the backend includes global roles.

Role responses omit `organization_id`, so the UI cannot distinguish global and tenant records with the same name.

The list renders separate IDs separately. Global and tenant same-named records can therefore appear as duplicate-looking rows.

### Incorrect permission display

[`RoleDetailPage.assignedPermissions`](../frontend/src/app/%28dashboard%29/roles/%5Bid%5D/page.tsx) returns the entire permission matrix whenever `role.is_system_role` is true.

Consequently, Read Only can visually appear to have all permissions despite having only 19 actual grants. This affects display, not backend enforcement.

### Assignment and defaults

- The shared role selector fetches assignable roles, filters Super Admin, and submits role IDs.
- It defaults to Admin or the first returned role.
- Roles-page row actions can still open Super Admin assignment.
- UI assignment gating uses `users:roles`, while the role assignment endpoint requires `roles:assign`.
- The UI offers “Set Registration Default” for Super Admin.
- Backend default-setting methods allow that configuration, although actual registration hardcodes Admin and does not consume it consistently.

### Organization administration

[`OrganizationPage`](../frontend/src/app/%28dashboard%29/organization/page.tsx) uses stored role/email heuristics for its Super Admin presentation.

Despite the multi-organization presentation, it fetches only `useCurrentOrganizationQuery()` and wraps that single organization in an array. There is no functioning all-organization list or switcher.

### Caching and errors

- Role query keys omit organization identity.
- Logout clears the query cache, which is good.
- Session replacement/verification does not provide equivalent organization-specific cache isolation.
- Roles-list query failures are not explicitly surfaced through an `isError` state.
- Default-role APIs can return fabricated compatibility roles.
- Role audit history, import, and export endpoints contain placeholder responses.

Frontend findings are source-verified; authenticated browser rendering was not tested.

## 10. ROOT CAUSES

| Finding | Exact implementation | Endpoint / table / migration |
|---|---|---|
| No organization-scoped provisioning | `AuthService.register` in `backend/app/services/auth_service.py`; `create_new_organization_invitation` and `accept_organization_invitation` in `backend/app/services/invitation_service.py` | `/auth/register`; `/organizations/invitations/new-organization`; invitation acceptance; `roles`, `role_permissions` |
| Global defaults reused | `AuthRepository.get_role_for_organization` in `backend/app/repositories/auth_repository.py`; `RoleRepository.synchronize_system_roles` in `backend/app/repositories/role_repository.py` | `roles`; startup; migration `f9a0b1c2d3e4` creates global Admin |
| Super Admin cannot manage other organizations | `get_current_user` in `backend/app/api/v1/deps.py`; `OrganizationDomainService._require_requested_org` in `backend/app/services/organization_service.py`; `UserService._require_same_org_user` in `backend/app/services/user_service.py` | `/organizations/{id}`, `/users/{id}`, Roles APIs; `users.organization_id` |
| Global custom role exposure | `RoleRepository.list_roles`; `RoleService._ensure_assignable_role_ownership` in `backend/app/services/role_service.py`; `UserService._resolve_assignable_role` | `/roles`, `/roles/assignable`, role assignment; `testing` |
| Singleton not enforced | `ensure_can_assign_role` in `backend/app/core/permissions.py` authorizes additional Super Admin assignments | User creation/invitation/assignment; `users`, `user_roles` |
| Global reset available to tenant Admin | `backend/app/api/v1/routers/settings.py` checks only `settings:update`; `SettingsService.reset_database` in `backend/app/services/settings_service.py` operates database-wide | `POST /api/v1/settings/reset-database`; public tables |
| Super Admin deletion protection bypass | `OrganizationDomainService.remove_member` calls repository deletion without platform protection | `DELETE /organizations/members/{user_id}`; `users` |
| Global settings writable by tenant permission | `SettingsService.update_system_settings` writes unscoped settings keys | `PUT /settings`; `settings` |
| Unbounded permission delegation | `RoleService.create_role`, `update_role`, `assign_permissions`, `create_permission`, `clone_role` | Role/permission APIs; global `permissions` |
| Stale role privileges | First-mapping replacement in Role/User services; legacy-only ownership transfer in Organization service | `users.role`, `user_roles`; assignment/update/transfer endpoints |
| Unsafe organization invitation acceptance | `invitation_service.accept_organization_invitation` differs from hardened `AuthService.accept_auth_user_invitation` | `/organizations/invitations/{token}/accept`; users/invitations |
| Historical duplicate grants | Concurrent check-before-insert seeding in `RoleRepository.seed_permissions`, formerly also on matrix GET | `role_permissions`; historical schema `8a1b2c3d4e5f`; corrected uniqueness in `p9e0f1a2b3c4` |
| Historical duplicate-looking roles | Global Admin/Super Admin migrations coexist with older tenant records | `f9a0b1c2d3e4`, `c3d4e5f6a7b9`; recovery snapshot confirms scope |
| Misleading permission UI | `RoleDetailPage.assignedPermissions` equates system role with every permission | `frontend/src/app/(dashboard)/roles/[id]/page.tsx` |
| Missing global organization UI | `OrganizationPage` fetches one current organization | `frontend/src/app/(dashboard)/organization/page.tsx` |

The reset implementation also contains a hardcoded fallback administrator password. It is not reproduced here, and the reset was not executed.

### Verification performed

- Read-only live role, user, organization, invitation, and mapping inspection.
- Read-only recovery-snapshot comparison.
- Exact grant comparison against the local matrix.
- Live index validity, foreign-key, nullability, trigger, and RLS inspection.
- **213 backend tests passed**, with 19 existing mock/deprecation warnings.
- Additional in-memory probes verified foreign-organization rejection, global custom-role acceptance, and Super Admin member-removal exposure.

The focused test files were:

- `backend/app/tests/unit/test_role_service.py`
- `backend/app/tests/unit/test_rbac_permissions.py`
- `backend/app/tests/unit/test_user_tenancy.py`
- `backend/app/tests/unit/test_organization_service.py`
- `backend/app/tests/unit/test_user_service.py`
- `backend/app/tests/unit/test_auth_service.py`
- `backend/app/tests/unit/test_rbac_matrix.py`

The initial test attempt failed during collection because synthetic settings lacked an S3 placeholder secret; rerunning with synthetic placeholders passed. No real credentials or `.env` files were loaded.

No live mutation probes, login attempts, frontend build/lint, or authenticated browser tests were performed. Passing tests establish existing behavior, not compliance with the required architecture; several tests explicitly expect shared global roles.

## 11. SAFE IMPLEMENTATION PLAN

### Phase 1 → Backend

1. Define one platform Super Admin identity independent of tenant membership.
2. Centralize authorization of organization context: ordinary users stay in their organization; the platform account may select authorized target organizations.
3. Restrict global settings/reset/catalog administration to the platform identity.
4. Protect the platform account across assignment, member removal, organization deletion, and invitation flows.
5. Add one transactional organization-provisioning service that creates the six scoped defaults, their grants, and the initial Admin mapping.
6. Route registration and both organization-invitation creation paths through it.
7. Resolve roles by ID and scope; allow global Super Admin only through an explicit platform path.
8. Establish one authoritative assignment representation and replace assignments consistently.
9. Unify invitation acceptance validation and locking.
10. Validate permission keys and delegation policy; make role/grant operations atomic.

### Phase 2 → Database

1. Preserve the existing valid uniqueness indexes.
2. Add explicit platform identity and role-scope invariants.
3. Enforce organization-consistent tenant role assignments.
4. Decouple platform-account survival from organization cascades.
5. Add canonical role references for users/invitations.
6. Enforce singular assignment if that remains the approved business rule.
7. Introduce stable system-role identifiers.
8. Use additive migrations before retiring legacy representations.

### Phase 3 → Frontend

1. Display only actual assigned permissions.
2. Include explicit role scope in API responses.
3. Implement Super Admin organization listing/context selection.
4. Remove email-based platform identity checks.
5. Scope query keys to organization and clear relevant caches on context changes.
6. Align frontend gates with backend permission contracts.
7. Remove Super Admin from tenant defaults and ordinary assignment flows.
8. Replace placeholder audit/default responses and show real errors.

### Phase 4 → Data cleanup/migration

1. Capture a fresh approved recovery point and inventory all references.
2. Provision missing scoped defaults for each organization.
3. Map each existing global-Admin assignment to its organization's Admin without changing user identity or credentials.
4. Determine `testing`'s intended owner before changing scope; its invitation reference alone is insufficient proof.
5. Preserve the existing platform user and global Super Admin identity.
6. Reconcile legacy strings, mappings, invitations, and defaults.
7. Compare effective permissions before and after every planned mapping.
8. Retire obsolete records only after explicit review and verification.

Do not rerun the existing cleanup's global-Admin canonicalization as the solution to this requirement.

### Phase 5 → Tests

Add isolated PostgreSQL integration tests for provisioning, concurrency, constraints, cross-tenant IDs, singleton enforcement, platform-account protection, invitation races, and stale mappings. Add frontend tests for real grants and organization-context/cache isolation.

### Phase 6 → Production verification

Verify the deployed revision, migration state, six defaults per organization, singleton platform identity, exact grants, absence of invalid mappings, and same-session organization access. Execute approved acceptance tests with controlled accounts and monitor authorization failures. Keep the recovery point until acceptance is complete.

## 12. TEST CASES

These are required acceptance tests, not claims that live mutations were performed.

| Case | Test | Required result | Current evidence |
|---|---|---|---|
| A | Create Organization A through each supported flow | Organization and initial Admin established atomically | Organization creation exists; role provisioning missing |
| B | Create Organization B | Independent organization initialization | Same missing provisioning |
| C | Inspect defaults in A and B | Exactly six required roles each | FAIL in current database |
| D | Compare same-named role IDs | Different IDs with correct organization IDs | Shared global Admin violates requirement |
| E | Create custom role in A | `organization_id = A` | Current create path enforces this |
| F | List A custom role from B | Never returned | Scoped roles filtered; existing global custom role leaks |
| G | Assign A custom role to B user | Reject; no changes | Guarded API rejects; database alone does not |
| H | Edit B role from A | Reject; no changes | Ownership guard rejects |
| I | Login with Super Admin; access A | Authorized without tenant account recreation | Only its host organization currently works |
| J | Same login accesses B | Authorized | Current service guard rejects |
| K | Same login lists/manages all organizations | All authorized organizations available | Not implemented |
| L | Create another organization | Super Admin account count remains one | No automatic account creation, but singleton not enforced |
| M | Attempt duplicate default role in one organization, including concurrent requests | Database rejects duplicate; API returns controlled conflict | Valid normalized unique index exists |
| N | Attempt duplicate role-permission pair concurrently | Duplicate prevented; controlled API behavior | Valid pair index exists |

Also require tests proving that tenant Admins cannot reset global data, delete/demote Super Admin, mutate global settings, or retain old privileges after reassignment.

No destructive SQL is included. This report does not authorize implementation, cleanup, user changes, commits, or deployment.
