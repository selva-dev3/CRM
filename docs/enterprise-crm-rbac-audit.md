# Enterprise CRM RBAC Audit Report

Audit date: September 8, 2026  
Source revision: `9694c81`  
Scope: read-only source audit; no application code, schema, migration, configuration, credential, or database changes were authorized or performed.

## 1. Executive Summary

**Overall status: FAIL**

RBAC is broadly implemented and the backend usually acts as the final security boundary. Authentication, database-backed permission resolution, platform-administrator checks, and organization-scoped repository queries are present throughout most modules.

The audit nevertheless confirmed several high-risk authorization problems:

- Tenant administrators can submit arbitrary permission strings while creating custom roles. Missing strings are inserted into the global permission catalog.
- The legacy `all` permission is honored by frontend helpers and several backend service checks. A custom role can therefore bypass granular secondary permission checks in AI and project operations.
- Several nested endpoints expose deals, quotes, invoices, notes, and documents using the parent entity's permission instead of the returned resource's permission.
- Task, meeting, quote, and invoice export/import endpoints use different permissions from the corresponding catalog keys.
- Administrative password reset uses `users:update` instead of `users:reset_password`.
- WebSocket users holding `notifications:read` can broadcast arbitrary messages to every connection in their organization.
- Many frontend mutation controls have no permission gate, although their backend endpoints are protected.
- Role mutation audit logs are fabricated placeholder responses rather than persisted audit records.
- Role creation and update are not fully transactional.

No confirmed unauthenticated access to an ordinary CRM CRUD endpoint was found. No confirmed cross-organization IDOR was found in the inspected repository and service flows. The primary findings concern privilege expansion within an organization, permission-policy inconsistencies, stale client authorization, and incomplete defense in depth.

The live database was not connected during this source-only audit. Deployed role IDs, assigned-user counts, existing duplicate or orphan rows, and the exact live permission catalog are therefore **NOT VERIFIED**.

## 2. RBAC Architecture

The primary authorization path is:

```text
JWT session or API key
        ↓
get_current_user()
        ↓
Organization context validation
        ↓
UserRole + legacy users.role
        ↓
RolePermission
        ↓
Permission.key
        ↓
require_permission()
        ↓
Organization-scoped service/repository query
```

Primary implementation locations:

- `backend/app/models/rbac.py`: Role, Permission, RolePermission, and UserRole models.
- `backend/app/models/auth.py`: User, platform administrator identity, sessions, and invitation records.
- `backend/app/api/v1/deps.py`: authentication, organization context, `require_platform_admin()`, and `require_permission()`.
- `backend/app/services/auth_service.py`: effective role and permission resolution.
- `backend/app/core/rbac_matrix.py`: approved system-role grant matrix.
- `backend/app/services/role_service.py`: role, permission, assignment, and default-role operations.
- `frontend/src/lib/permissions.ts`: frontend permission catalog and helpers.
- `frontend/src/hooks/use-has-permission.ts`: reactive client permission state.
- `frontend/src/components/common/permission-gate.tsx`: component-level gate.
- `frontend/src/constants/navigation.ts`: navigation and route-level read gates.

### Multiple-role behavior

A user can have multiple `user_roles` records because uniqueness covers only `(user_id, role_id)`. Effective permissions are the union of all authorized role mappings plus the legacy `users.role` value.

Normal user and role assignment flows call `replace_user_role()`, which reduces managed users to one mapping. The database does not enforce one role per user, while several role-management reads use only the first mapping.

**Status: PARTIALLY IMPLEMENTED**

### Permission propagation

- JWTs do not contain a permission snapshot.
- HTTP authorization resolves permissions from the database on every request, so backend changes take effect on the next request.
- The frontend persists the user and permissions locally. Role mutations invalidate role queries but do not refresh the affected user's `/auth/me` state.
- Existing WebSocket connections validate permissions only during connection.

| Layer | Status |
|---|---|
| Backend HTTP | IMPLEMENTED |
| Frontend state | PARTIALLY IMPLEMENTED |
| WebSocket propagation | INCORRECT |

## 3. Roles Found

The code-defined system roles are:

| Role | Scope | Type | Grant count |
|---|---|---|---:|
| Super Admin | Global only | System | Every database permission |
| Admin | Organization | System | 149 |
| Sales Manager | Organization | System | 107 |
| Sales Executive | Organization | System | 50 |
| Marketing Executive | Organization | System | 30 |
| Customer Support | Organization | System | 29 |
| Read Only | Organization | System | 19 |

Custom organization roles are supported.

The legacy `UserRole` enum contains `Organization Admin`, while the actual system matrix uses `Admin`. The enum omits `Read Only`. Current routers do not use the legacy `require_role()` dependency, so this mismatch does not currently grant backend access.

Runtime UUIDs, custom roles, assigned-user counts, and duplicate status are **NOT VERIFIED** without a live database query.

### Actual system-role grants

- **Admin:** every catalog permission except `super_admin:manage`.
- **Sales Manager:** full CRM CRUD, import, export, and assignment across leads, contacts, companies, deals, tasks, meetings, calls, notes, documents, products, quotes, and invoices; email read/send/templates; report read/create/export/schedule; calendar; activities; AI read/generate; and projects.
- **Sales Executive:** dashboard read; lead/contact/company/deal operations; tasks and meetings; calls; email; notes; document upload/share; product read; quote read/update/send; invoice read; report read; calendar; activities; AI read/generate.
- **Marketing Executive:** dashboard; lead and contact read/create/update/import/export; company read; email read/send/templates; tasks; meetings; calendar; report read/export; activities; AI read/generate.
- **Customer Support:** dashboard; lead read; contact/company read/update; tasks; meetings; calls; email read/send; notes; document read/upload; invoice read; calendar; activities; AI read.
- **Read Only:** read access to dashboard, leads, contacts, companies, deals, tasks, meetings, calls, emails, notes, documents, products, quotes, invoices, reports, calendar, activities, AI, and projects.

## 4. Permission Catalog

The backend system matrix contains 150 permission keys.

| Module | Actual actions |
|---|---|
| dashboard | `read`, `customize`, `export` |
| leads | `read`, `create`, `update`, `delete`, `export`, `import`, `assign`, `convert`, `bulk_delete`, `bulk_update` |
| contacts | `read`, `create`, `update`, `delete`, `export`, `import`, `assign`, `bulk_delete`, `bulk_update` |
| companies | `read`, `create`, `update`, `delete`, `export`, `import`, `bulk_delete` |
| deals | `read`, `create`, `update`, `delete`, `pipeline`, `export`, `import`, `assign`, `bulk_delete` |
| tasks | `read`, `create`, `update`, `delete`, `assign`, `complete`, `export`, `import` |
| meetings | `read`, `create`, `update`, `delete`, `invite`, `export` |
| calls | `read`, `create`, `update`, `delete`, `recording` |
| emails | `read`, `send`, `templates`, `delete` |
| notes | `read`, `create`, `update`, `delete` |
| documents | `read`, `upload`, `delete`, `share` |
| products | `read`, `create`, `update`, `delete`, `export`, `import` |
| quotes | `read`, `create`, `update`, `delete`, `approve`, `send`, `export`, `import` |
| invoices | `read`, `create`, `update`, `delete`, `send`, `payment`, `export`, `import` |
| reports | `read`, `create`, `delete`, `export`, `schedule` |
| calendar | `read`, `write`, `sync` |
| users | `read`, `create`, `invite`, `update`, `delete`, `export`, `import`, `roles`, `assign_roles`, `reset_password` |
| roles | `read`, `create`, `update`, `delete`, `assign` |
| organization | `read`, `update`, `billing`, `domains`, `branding`, `audit`, `members`, `delete`, `transfer_ownership` |
| invitations | `read`, `create`, `resend`, `revoke` |
| integrations | `read`, `manage`, `apikeys` |
| notifications | `read`, `manage`, `send` |
| settings | `read`, `update`, `security` |
| activities | `read`, `create`, `export` |
| AI | `read`, `generate`, `configure` |
| API keys | `read`, `create` |
| projects | `read`, `create`, `update`, `delete`, `assign` |
| platform | `super_admin:manage` |

### Catalog keys with no runtime backend enforcement

The following 22 keys are assigned by the matrix but are not used as runtime authorization decisions:

```text
activities:create
activities:export
ai:configure
api_keys:create
api_keys:read
contacts:assign
contacts:bulk_update
dashboard:export
documents:share
invoices:export
invoices:import
meetings:export
organization:delete
organization:members
organization:transfer_ownership
quotes:export
quotes:import
reports:delete
tasks:export
tasks:import
users:assign_roles
users:reset_password
```

`super_admin:manage` is not used to authorize platform operations. Platform operations deliberately use `is_platform_admin`, which is safer than a delegable tenant permission.

### Frontend catalog drift

The frontend catalog has 134 keys and omits these 16 backend keys:

```text
ai:configure
api_keys:create
api_keys:read
invoices:export
invoices:import
meetings:export
organization:delete
organization:members
organization:transfer_ownership
quotes:export
quotes:import
reports:delete
tasks:export
tasks:import
users:assign_roles
users:reset_password
```

**Status: INCORRECT**

## 5. Module Coverage

| Module | Read | Create | Update | Delete | Special | Frontend | Backend | Tenant isolation | Status |
|---|---|---|---|---|---|---|---|---|---|
| Dashboard | Yes | N/A | Customize | N/A | AI | Partial | Yes | Yes | PARTIAL |
| Leads | Yes | Yes | Yes | Yes | Assign/convert/import/export | Partial | Partial | Yes | PARTIAL |
| Contacts | Yes | Yes | Yes | Yes | Merge/import/export | Partial | Partial | Yes | PARTIAL |
| Companies | Yes | Yes | Yes | Yes | Related CRM data | Partial | Incorrect nested gates | Yes | FAIL |
| Deals | Yes | Yes | Yes | Yes | Pipeline/assign/clone | Partial | Partial | Yes | PARTIAL |
| Tasks | Yes | Yes | Yes | Yes | Complete/assign/import/export | Partial | Wrong import/export keys | Yes | PARTIAL |
| Meetings | Yes | Yes | Yes | Yes | RSVP/transcript/export | Partial | Wrong export key | Yes | PARTIAL |
| Calls | Yes | Yes | Yes | Yes | Recording/AI | Partial | Yes | Yes | PARTIAL |
| Emails | Yes | Send | Draft/template | Yes | Campaign/signature | Partial | Yes | Yes | PARTIAL |
| Notes | Yes | Yes | Yes | Yes | Pin/bulk delete | Partial | Partial nested gates | Yes | PARTIAL |
| Documents | Yes | Upload | N/A | Yes | Download/share | Partial | Partial nested gates | Yes | PARTIAL |
| Products | Yes | Yes | Yes | Yes | Inventory/import/export | Partial | Yes | Yes | PARTIAL |
| Quotes | Yes | Yes | Yes | Yes | Approve/send/import/export | Partial | Wrong import/export keys | Yes | PARTIAL |
| Invoices | Yes | Yes | Yes | Yes | Send/payment/import/export | Partial | Wrong import/export keys | Yes | PARTIAL |
| Payments | Yes | Through invoice | N/A | N/A | Record/reconcile | Yes | Yes | Yes | PASS |
| Reports | Yes | Yes | N/A | Yes | Export/schedule | Partial | Wrong delete key | Yes | PARTIAL |
| Calendar | Yes | Yes | Yes | Yes | Sync | Partial | Yes | Yes | PARTIAL |
| Users | Yes | Yes | Yes | Yes | Invite/roles/reset | Partial | Wrong reset key | Yes | PARTIAL |
| Roles | Yes | Yes | Yes | Yes | Assign/permissions/default | Partial | Unsafe permission creation | Partial | FAIL |
| Organization | Yes | Platform only | Yes | Platform only | Billing/member/ownership | Partial | Platform delete safe | Yes | PARTIAL |
| Invitations | Yes | Yes | N/A | Revoke | Accept/resend | Partial | Yes | Yes | PASS |
| Integrations | Yes | Yes | Yes | Yes | OAuth/API keys/sync | Missing action gates | Yes | Yes | PARTIAL |
| Notifications | Yes | N/A | Preferences | Yes | Broadcast/WebSocket | Missing | Incorrect WebSocket | Yes | FAIL |
| Settings | Yes | Yes | Yes | Yes | Audit/webhooks/backups | Partial | Yes | Yes | PARTIAL |
| Activities | Indirect | No direct endpoint | No | No | AI/report filters | Missing | Partial | Yes | PARTIAL |
| AI | Yes | Generate | Configure | Conversations | CRM actions/search | Partial | `all` bypass risk | Yes | PARTIAL |
| API Keys | Yes | Yes | N/A | Revoke | Broad scopes | Missing action gates | Uses `integrations:apikeys` | Yes | PARTIAL |
| Projects | Yes | Yes | Yes | Yes | Assignment | No UI | Yes | Yes | PARTIAL |
| WebSockets | Notification read | Client publish | N/A | N/A | Organization broadcast | N/A | Incorrect | Yes | FAIL |

## 6. Frontend RBAC

### Correctly implemented

- Sidebar entries are filtered by read permissions.
- Dashboard routes use centralized top-level permission guards.
- Detail routes inherit their module's read permission.
- List pages for leads, contacts, companies, deals, documents, products, and several administrative modules gate many mutation actions.
- Organization creation and deletion are shown only when `user.is_platform_admin` is true.
- Deleted-organization events clear organization context and query caches.

### Missing frontend permission gates

Confirmed examples include:

- Call delete and bulk delete in `frontend/src/app/(dashboard)/calls/page.tsx`.
- Meeting reschedule and cancel in `frontend/src/app/(dashboard)/meetings/page.tsx`.
- Note edit, pin, delete, and bulk delete in `frontend/src/app/(dashboard)/notes/page.tsx`.
- Email template creation and bulk deletion in `frontend/src/app/(dashboard)/email/page.tsx`.
- Notification broadcast, preferences, registration, and deletion in `frontend/src/app/(dashboard)/notifications/page.tsx`.
- Task row edit and detail-page update/delete/complete actions.
- Company, contact, deal, meeting, product, and task detail-page mutations.
- Integration connect, disconnect, test, synchronization, and API-key operations.

These are missing frontend gates. Most corresponding backend endpoints still reject unauthorized requests.

### Hardcoded frontend checks

`frontend/src/app/(dashboard)/organization/page.tsx` checks a locally stored role and `superadmin@gmail.com`. The exported page ultimately selects the platform organization list using `is_platform_admin`, so this does not create backend platform authority, but it is obsolete and misleading.

Role pages identify a Super Admin role using name substrings and the old `sys-admin` identifier. This can incorrectly classify custom role names containing `super`.

## 7. Backend RBAC

### Correct enforcement

Most sensitive endpoints use `require_permission()`.

The dependency:

1. Authenticates the session or API key.
2. Validates the session and active user.
3. Resolves platform organization context.
4. Resolves current permissions from database mappings.
5. Applies API-key scopes as an additional restriction.
6. Denies missing permissions.

Platform organization provisioning, deletion, cleanup status, and retry use explicit `require_platform_admin()`.

Repository and service methods generally filter resources by the effective organization ID and return 404 for cross-tenant IDs.

### Missing backend authorization

No ordinary authenticated CRM CRUD route was confirmed to be completely missing backend authorization.

Permission-free routes belong to intentional categories:

- Login and password recovery.
- Invitation token validation and acceptance.
- Public quote and invoice capability tokens.
- Signed billing and delivery webhooks.
- Signed OAuth callbacks.
- Authenticated user self-profile operations.

### Bypassed or incorrect authorization

#### Arbitrary permission creation through custom roles — High

`RoleService.create_role()` creates every missing permission submitted in `payload.permissions`. This bypasses the explicit platform-only permission-creation endpoint and allows a tenant role administrator to mutate the global permission catalog.

The API schema only validates `permissions` as `list[str]`; it does not constrain values to the approved catalog.

#### Legacy `all` bypass — High

Frontend helpers honor `all`. Backend AI and project service checks also accept it as a wildcard, while the main `require_permission()` dependency does not.

A custom role containing `ai:generate` and `all` can therefore pass secondary AI resource checks without the associated CRM read permissions.

#### WebSocket read-to-write escalation — High

WebSocket authentication requires only `notifications:read`. After connecting, every received client message is broadcast to all connections in the organization. Read permission therefore grants publish capability.

Existing connections revalidate session revocation, but do not revalidate permissions or organization status after connection.

## 8. Database RBAC

### Implemented constraints

- Role and Permission primary keys.
- RolePermission and UserRole foreign keys with cascade.
- Unique normalized permission keys.
- Unique RolePermission and UserRole pairs.
- Unique normalized role names per organization scope.
- A single global system Super Admin role.
- At most one `is_platform_admin=true` user.
- Platform admin must be active and have no stored organization.
- Tenant users must have an organization.
- Database triggers protect the platform identity from deletion, demotion, tenant membership, and tenant role assignment.

### Partial constraints

- There is no uniqueness constraint on `user_roles.user_id`; multiple roles are permitted.
- There is no composite database constraint proving `user.organization_id == role.organization_id`.
- Cross-organization mappings can exist as data, although permission resolution filters them out.
- Legacy `users.role` and normalized `user_roles` coexist and are both included in permission resolution.
- Permissions are global, including dynamically created custom permission keys.

### Duplicate and orphan status

Schema constraints prevent new duplicate role-permission and user-role pairs. Cascades prevent ordinary orphan mappings after role, permission, or user deletion.

Existing live duplicates, cross-organization mappings, custom keys, and orphan data are **NOT VERIFIED**.

## 9. Organization Isolation

**Status: IMPLEMENTED with data-integrity gaps**

Normal users derive their organization from the authenticated database user. They cannot select another organization using `X-Organization-ID`.

Platform administrators may select an active organization explicitly. The stored global account remains organization-neutral.

Confirmed tenant-scoped modules include leads, contacts, companies, deals, tasks, meetings, calls, email, documents, notes, products, projects, quotes, invoices, payments, reports, integrations, notifications, users, roles, and settings.

No confirmed cross-organization IDOR was found in the inspected HTTP flows.

The main weakness is that tenant membership and role ownership are validated by application queries rather than a database-level composite relationship.

## 10. Super Admin

**Status: IMPLEMENTED**

- The authoritative marker is `users.is_platform_admin`.
- The platform user has `organization_id = NULL`.
- A partial unique index limits the database to one platform admin.
- Platform operations reject API keys.
- Tenant APIs cannot assign the Super Admin role.
- Organization deletion explicitly protects the platform identity.
- Organization switching validates that the selected organization exists and is active.
- Platform permissions are recomputed as all current database permission keys.
- Tenant Admin holding `super_admin:manage` does not become a platform admin.

The hardcoded `PROTECTED_SUPERADMIN_EMAIL` in `backend/app/services/user_service.py` is `superadmin@gmail.com`, while platform lifecycle protection uses `superadmin@mycrm.com`. Database and flag-based protections still protect the platform identity, but the stale constant is inconsistent.

## 11. Custom Roles

**Status: FAIL**

Correct behavior:

- Created roles receive the current organization ID.
- Reserved system-role names are rejected.
- System roles cannot be updated or deleted.
- Foreign-organization custom roles are hidden or rejected.
- Role deletion cascades RolePermission and UserRole mappings.
- Normal assignment replaces managed mappings.
- Super Admin cannot be assigned through tenant APIs.

Incorrect behavior:

- Custom role creation accepts arbitrary permission keys.
- Arbitrary keys become global Permission rows.
- `all` is accepted and honored by parts of the application.
- Role creation commits the role before assigning permissions, so failure can leave a role without the requested grants.
- Role update commits metadata before replacing permissions.
- Unknown permissions on update or assignment may be silently ignored.
- Update responses can return requested permission strings that were not assigned.
- Legacy global non-Super-Admin roles remain assignable when an organization lacks a local shadow role.
- Role-change audit logs are not persisted.

## 12. Privilege Escalation Risks

| Severity | File/function | Problem | Impact | Recommended fix |
|---|---|---|---|---|
| High | `role_service.py:create_role` | Tenant role creation inserts unknown global permission keys | Catalog corruption and future privilege exposure | Reject keys absent from the approved catalog |
| High | AI/project services | `all` accepted as a wildcard | Custom roles bypass secondary resource checks | Remove runtime wildcard handling |
| High | `websockets.py:_run_socket` | `notifications:read` grants organization broadcast | Event injection and false notifications | Separate subscribe and publish authorization |
| High | Company related-resource endpoints | Company read returns quotes, invoices, deals, and documents | Users read modules they were not granted | Require parent read and target-module read |
| High | Contact related-deals endpoint | Contact read returns linked deals | Deal data exposed without `deals:read` | Require `deals:read` |
| High | Lead document endpoints | Lead read/create grants document access | Document access without document permissions | Require `documents:read` or `documents:upload` |
| High | `users.py:admin_reset_user_password` | Password reset uses `users:update` | Broader roles can trigger credential resets | Require `users:reset_password` |
| High | Export endpoints | Read permissions authorize exports | Read Only can export task, meeting, quote, or invoice data | Require module export permissions |
| Medium | Role create/update | Split commits | Partially provisioned roles and misleading state | Use one transaction |
| Medium | Role mappings | Multiple mappings plus legacy role | Unintended permission unions | Define and enforce role cardinality |
| Medium | Role audit endpoint | Returns fabricated static events | False security audit history | Persist role mutation audit events |
| Medium | WebSockets | Permission checked only at connection | Removed permissions remain effective | Revalidate or disconnect after changes |
| Medium | Frontend actions | Many mutations remain visible | Easier probing and inconsistent UI | Gate each action with its backend permission |
| Low | Super Admin email checks | Conflicting addresses and localStorage logic | Incorrect protection and display heuristics | Use `is_platform_admin` only |
| Low | Role enum | `Organization Admin` differs from `Admin`; Read Only missing | Future role-check errors | Remove or align the enum |

## 13. Incorrect Permission Usage

| Action | Current permission | Catalog permission |
|---|---|---|
| Task CSV export | `tasks:read` | `tasks:export` |
| Task CSV import | `tasks:create` | `tasks:import` |
| Meeting iCal export | `meetings:read` | `meetings:export` |
| Quote CSV export | `quotes:read` | `quotes:export` |
| Quote CSV import | `quotes:create` | `quotes:import` |
| Invoice CSV export | `invoices:read` | `invoices:export` |
| Invoice CSV import | `invoices:create` | `invoices:import` |
| Delete custom report | `reports:create` | `reports:delete` |
| Administrative password reset | `users:update` | `users:reset_password` |
| API-key list/create/revoke | `integrations:apikeys` | `api_keys:read` and `api_keys:create` exist but are unused |
| AI configuration | Settings permissions | `ai:configure` exists but is unused |
| Organization member management | `organization:update` | `organization:members` exists but is unused |
| Ownership transfer | `organization:update` | `organization:transfer_ownership` exists but is unused |

Nested-resource mismatches:

- Company deals use `companies:read` without `deals:read`.
- Company quotes use `companies:read` without `quotes:read`.
- Company invoices use `companies:read` without `invoices:read`.
- Company documents use `companies:read` without `documents:read`.
- Contact deals use `contacts:read` without `deals:read`.
- Lead documents use `leads:read` or `leads:create` without document permissions.
- Company, contact, deal, and lead note creation use parent-module create permissions instead of `notes:create`.
- Lead task creation uses `leads:create` instead of `tasks:create`.

## 14. Hardcoded Authorization

### Safe or intentional

- `is_platform_admin` checks for organization provisioning, deletion, switching, and global settings.
- System-role mutation protection through `is_system_role`.
- Super Admin assignment rejection in user, role, and invitation services.
- Database-trigger protection for the platform identity.

### Security risk or inconsistency

- `superadmin@gmail.com` frontend and user-service checks conflict with `superadmin@mycrm.com`.
- Frontend role screens identify Super Admin using name substrings and `sys-admin`.
- Legacy `require_role()` compares string role names and grants Super Admin by name. It is currently unused by routers.
- User display logic infers Super Administrator from whether an email contains `superadmin`.
- Role default fallbacks fabricate a `sys-manager`/`manager` role on database failure. This does not authorize backend requests but hides configuration errors.

## 15. Missing RBAC

No complete backend permission omission was confirmed on ordinary CRM HTTP CRUD endpoints.

Missing or incomplete areas are:

- Frontend action gates across detail pages, notifications, and integrations.
- Direct Activities create/export enforcement.
- Frontend Projects module.
- Permission-specific export/import enforcement.
- Permission-specific user reset, organization member, ownership, and API-key enforcement.
- WebSocket publish authorization.
- WebSocket permission-revocation propagation.
- Persisted audit records for role and permission changes.
- Documented and enforced row ownership for Sales Executive resources.

The code currently implements organization-wide resource permissions. It does not restrict Sales Executives to leads or deals assigned to them. Whether assignment ownership is required is **NOT VERIFIED** from an authoritative policy document.

## 16. Duplicate and Orphan RBAC Data

| Check | Result |
|---|---|
| Duplicate normalized permission keys | Prevented by database constraint |
| Duplicate normalized role names per scope | Prevented by database constraint |
| Duplicate UserRole pair | Prevented |
| Duplicate RolePermission pair | Prevented |
| Multiple roles per user | Allowed |
| Orphan UserRole mappings | Prevented by foreign-key cascade |
| Orphan RolePermission mappings | Prevented by foreign-key cascade |
| Cross-organization role mappings | Possible as data; ignored by permission resolution |
| Existing duplicate/custom catalog rows | NOT VERIFIED |
| Conflicting legacy and mapped roles | NOT VERIFIED |
| Existing role IDs and assignment counts | NOT VERIFIED |

## 17. Test Coverage

Existing tests cover:

- Permission dependency allow/deny behavior.
- Fail-closed permission resolution.
- Foreign-role mapping rejection.
- Platform administrator singleton and database protection.
- Organization creation, deletion, and context switching.
- Tenant-role rejection of platform lifecycle endpoints.
- User cross-tenant access.
- Quote, invoice, payment, document, lead-call, and project tenant isolation.
- Route dependency wiring for most routers.
- Frontend permission helpers, navigation filtering, and PermissionGate behavior.
- Platform organization action visibility.
- WebSocket authentication and inactive session/organization rejection.

Critical gaps:

- Route wiring coverage omits the payments and projects routers.
- No test prevents arbitrary permission creation through `POST /roles`.
- No test rejects `all` for custom roles.
- No test covers WebSocket client broadcast authorization.
- No test verifies WebSocket permission revocation.
- No test asserts that export/import endpoints use their catalog permissions.
- No test checks `users:reset_password` enforcement.
- No nested-resource permission-composition tests for company, contact, or lead data.
- Limited frontend mutation-visibility tests for detail pages.
- No real role-mutation audit-log test.
- No test defining intentional multiple-role semantics.

Tests were inspected but not executed because this was a strict read-only audit and integration tests create database records.

## 18. Priority Fix Plan

### Phase 1 — Critical Security

1. Reject unknown and `all` permission keys in tenant role APIs.
2. Remove wildcard behavior from backend AI and project permission checks.
3. Stop client-originated WebSocket broadcasts or require an explicit send permission.
4. Correct nested-resource permission composition.
5. Require `users:reset_password` for administrative resets.

### Phase 2 — Backend Authorization

1. Activate the catalog's export, import, delete, member, ownership, and API-key permissions.
2. Add tests mapping every endpoint action to its intended catalog key.
3. Decide whether related-resource endpoints require both parent and resource permissions.

### Phase 3 — Tenant Isolation

1. Add cross-organization role-mapping integrity validation.
2. Audit existing mappings for foreign-role assignments.
3. Define Sales Executive ownership rules and enforce them if required.

### Phase 4 — Frontend RBAC

1. Gate every mutation action.
2. Remove email and role-name authorization heuristics.
3. Add the 16 missing permission constants.
4. Refresh `/auth/me` after changes affecting the current user.

### Phase 5 — Role and Permission Data Cleanup

1. Define one-role versus multiple-role behavior.
2. Remove obsolete permission keys or connect them to operations.
3. Audit dynamically created permissions and legacy `all` mappings.
4. Replace fabricated role audit and default-role responses.

### Phase 6 — Tests

Add backend integration and frontend component coverage for every confirmed issue, including WebSockets and nested resources.

### Phase 7 — Final Verification

Run the complete backend and frontend suites against an isolated database, inspect actual RBAC rows for anomalies, and perform cross-tenant direct-ID tests for every resource.

## 19. Final Verdict

1. **Is RBAC implemented across the entire CRM?**  
   **PARTIALLY.** A common architecture exists, but several modules use incorrect or incomplete permissions.

2. **Which modules are fully protected?**  
   Payments and the core platform organization lifecycle have the strongest verified end-to-end enforcement. Invitations are consistently tenant-scoped.

3. **Which modules are partially protected?**  
   Dashboard, leads, contacts, deals, tasks, meetings, calls, emails, notes, documents, products, quotes, invoices, reports, calendar, users, organization, integrations, settings, activities, AI, API keys, and projects.

4. **Which modules have missing backend authorization?**  
   No ordinary CRM CRUD module was found completely unprotected. WebSocket publishing lacks an appropriate authorization boundary, and several nested operations bypass their target module's permission.

5. **Are there privilege-escalation risks?**  
   **Yes.** Arbitrary permission creation, `all` wildcard handling, nested-resource mismatches, password-reset permission mismatch, and WebSocket broadcasting are confirmed risks.

6. **Are there cross-organization authorization risks?**  
   No confirmed HTTP IDOR was found. Cross-organization role mappings can exist at the database level, but current permission resolution ignores them.

7. **Are frontend and backend permissions consistent?**  
   **No.** Sixteen backend keys are absent from the frontend and many actions lack frontend gates.

8. **Are roles and permissions correctly scoped?**  
   System-role provisioning and normal tenant-role ownership are mostly correct. Legacy global-role fallback, globally inserted custom permission keys, multiple mappings, and absence of a composite tenant constraint make this partial.

9. **Is the RBAC system production-ready?**  
   **No.** The confirmed high-risk findings require remediation and isolated verification first.

## 20. Audit Verification

- Source, models, migrations, routers, services, repositories, frontend gates, and RBAC-related tests were inspected.
- The permission catalog and system-role counts were derived from the project constants.
- No live database query was performed.
- No test suite was executed because integration tests mutate isolated test data and this audit was explicitly read-only.
- No source code, database record, migration, configuration file, environment file, secret, or credential was modified during the audit.

