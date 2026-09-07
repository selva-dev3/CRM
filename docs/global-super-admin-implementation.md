# Global Super Admin implementation and verification

Date: September 7, 2026<br>
Branch: `fix/global-super-admin`<br>
Base: `da56005`<br>
Status: local implementation; production migration, credential provisioning, and production login verification are pending.

The original findings remain in [the complete RBAC audit](rbac-organization-audit.md). This document records the subsequent, explicitly approved global account implementation. It does not declare the entire RBAC audit resolved.

## Root causes and resulting behavior

| Problem | Implementation |
|---|---|
| Super Admin was stored as an organization member; normal organization checks blocked other tenants | `User.is_platform_admin` identifies the platform principal. Its stored `users.organization_id` is NULL. `apply_organization_context` validates an optional `X-Organization-ID` using the authenticated identity and active organization. |
| No database singleton protection | Migration `r1a2b3c4d5e6` adds a partial unique platform-user index, account scope/active checks, and triggers protecting deletion, demotion, raw role changes, and role mappings. |
| Organization deletion cascaded to the platform user | Migration detaches the intended platform user from the organization FK while preserving its ID and password hash. |
| Role assignment could create another Super Admin | Shared assignment protection rejects the platform role through tenant user, role, and invitation operations, even when the caller is the platform administrator. |
| Email-based protections missed member-removal and other paths | Platform identity checks protect user updates, deletion, deactivation, bulk deactivation, member removal, ownership transfer, and invitation acceptance. |
| Case variants of an email could refer to different users | A unique normalized-email index makes database uniqueness agree with case-insensitive login. Existing collisions stop migration for review. |
| Database reset recreated an administrator with fallback credentials | The reset service returns 501 and directs operators to offline recovery. The route requires platform identity plus the standard permission dependency. No fallback password remains in this path. |
| Global settings and permission definition writes used tenant permissions alone | These routes now require platform identity in addition to their standard permission gates. Organization settings remain under organization endpoints. |
| Frontend organization list/switching did not provide real platform access | `/organizations/all` lists organizations with pagination and member counts. Platform UI validates the target, cancels requests, clears query caches, saves a tab-local selection, and loads the selected organization using the same authentication cookies. |

## Identity and organization context

The database membership column remains NULL for the platform account. A SQLAlchemy hybrid property exposes a temporary request selection to existing organization services; its SQL expression still refers to the actual database membership column. Selecting an organization never updates the account's membership.

The backend validates each selection. A normal user cannot select a different organization with a forged header. A platform session can list organizations without selecting one; tenant resource operations require a valid active selection. Missing/deleted/inactive selections are rejected. Each new context resolution clears any previous transient selection.

Login and `/auth/me` include `is_platform_admin`. Global login can succeed without an organization. Permission resolution gives this identity all defined permission keys, while platform-only routes additionally require the identity flag. JWT subject and server-side session revocation checks remain in use; no token is minted merely to switch organizations.

The tab-local organization ID is a request preference, never proof of access. Logout/new login clears it. Switching loads a fresh document so previous tenant forms, caches, and UI state cannot carry into the next organization.

## Migration safeguards

Migration file: `backend/alembic/versions/r1a2b3c4d5e6_global_platform_admin.py`<br>
Parent: `q0f1a2b3c4d5`

The migration locks the relevant tables and finds existing candidates through the legacy user role and role mappings. A single candidate keeps its ID, email, and password hash. The migration changes its platform flag, membership, and canonical role label only. Credential changes belong to the separate provisioning operation.

Migration stops rather than guessing when it finds multiple candidate identities, tenant-role mappings on the candidate, conflicting normalized emails, duplicate global Super Admin roles, or rows incompatible with the new checks. It does not merge users or delete role records. The existing RBAC duplicate constraints remain in force.

At most one platform user can exist. Once created, the database rejects deleting, disabling, demoting, or attaching that account to an organization. If the database has no existing candidate, explicit provisioning creates the initial account; the migration does not invent credentials. Platform role records must be global and system-managed. Tenant user-role mappings cannot assign the platform role.

Automatic downgrade is intentionally refused: restoring a global account to a tenant-owned identity requires an audited recovery decision. Use a coordinated application/migration deployment; the previous application assumes every user has an organization and must not continue serving requests after the account is detached.

## Secure production provisioning

Provisioning code:

- `backend/scripts/provision_platform_admin.py`
- `backend/app/services/platform_admin_service.py`
- `backend/app/repositories/auth_repository.py`

The intended production email is `superadmin@mycrm.com`. The initial password supplied privately in the task is deliberately absent from this document, source, migration, and test fixtures.

Use the existing application runtime's database and application settings. The provisioning command disables dotenv loading. Supply the initial password through the secret manager as `PLATFORM_ADMIN_INITIAL_PASSWORD`, or enter it at the command's hidden interactive prompt. Never place it in command arguments, shell history, deployment logs, or a migration.

After reviewing the existing intended identity, run from `backend`:

```bash
python -m scripts.provision_platform_admin \
  --email superadmin@mycrm.com \
  --existing-user-id <reviewed-existing-user-id>
```

The audit identified candidate ID `3214b610-dfd5-46fb-83e1-3cbe9d3afc55`. Revalidate it in the deployment database before using it; this is a historical observation, not automatic authorization to select an identity in another environment.

If no intended account exists, omit `--existing-user-id`. If an existing platform account or requested email owner exists, the command requires its explicit matching ID. An email collision with another account aborts; no accounts are merged. Provisioning serializes concurrent attempts, uses the project's bcrypt hasher, revokes existing sessions/reset links/magic links, and commits atomically. Existing two-factor configuration is preserved. Rollback failures cannot replace the original provisioning failure.

This command is not called from startup, organization registration, invitations, or role seeding. Remove the one-time secret from the runtime after provisioning.

## Automated verification

Focused backend suite: **260 tests passed** across authentication, roles, users, organizations, invitations, permissions, settings, migration graph, and platform account unit tests.

Focused frontend suite: **37 tests passed** across the API client, organization API, auth provider, organization detail page, and platform organization selector. Tests cover loading, retry, empty results, failed selection, cache disposal, and organization headers with an unchanged cookie session.

The PostgreSQL workflow test runs only against a loopback database named `crm_workflow_test`. It creates a uniquely named disposable database because historical migration `p9e0f1a2b3c4` explicitly addresses the `public` schema. It applies the real migration history, seeds a legacy intended account, and exercises:

- ID/hash preservation and conversion to an organization-independent platform identity.
- Secure provisioning of the intended email without changing its user ID.
- Duplicate provisioning rejection and exactly one platform account.
- Real registration of organizations A and B without another platform account.
- Password verification and a single authenticated session across organizations.
- Organization listing/opening, users/members/roles listing, user creation, role creation/editing, and permission assignment in both organizations.
- Normal Admin denial for global listing, cross-organization context, platform creation/assignment/deletion/demotion/deactivation.
- Database rejection of duplicate platform users, case-variant credential collisions, invalid role mapping, disabling, demotion, and deletion.
- Platform account and session survival after deleting its former organization.

Test: `backend/app/tests/integration/test_platform_admin_workflow.py`. External production systems are not invoked. Test passwords are generated locally and do not use the requested production password.

The final focused rerun passed **105 tests**, including the real PostgreSQL workflow using an unchanged authentication cookie and the global profile endpoint without organization selection. This overlaps the 260-test suite; the numbers are not additive. Python type checking passed for all **19 changed application files**, frontend TypeScript passed, changed-file Python and frontend lint passed, and `git diff --check` passed. Upstream `origin/main` remained at `da56005` when rechecked before the commit proposal.

The first regression run found two routes missing the conventional permission dependency. Both now retain that dependency alongside the platform identity guard. The first integration attempt failed because the historical migration targets `public`; isolation was changed from a schema to a whole disposable database. The selector test's browser mock was corrected. These failures are not being reported as passing initial runs.

## Release and production verification still required

1. Review and approve the scoped commit on `fix/global-super-admin`; no commit/push/PR has occurred as part of this document.
2. Review production candidates, role mappings, normalized email collisions, migration head, and recovery backup without changing data.
3. Deploy the reviewed backend, migration, and frontend together with a controlled transition for old application instances.
4. Run explicit secure provisioning against the reviewed identity.
5. Authenticate through the production login endpoint with the requested email and securely supplied initial password; complete preserved two-factor verification if enabled.
6. Keep the same browser session while listing organizations and managing users, roles, and permissions in multiple organizations. Verify context changes do not change `users.organization_id`.
7. Confirm singleton count, protected-account denials, no new platform user during organization creation, and organization deletion behavior using disposable production-verification tenants or an equivalent staging environment.
8. Verify logs/responses contain no secret or password hash and remove the initial provisioning secret.

No production login with the requested credential has been claimed or performed. No production roles, grants, users, or credentials were deleted or updated during local implementation/testing.

## Remaining audit findings and limitations

This change addresses the global platform account request. The earlier audit's missing per-organization default-role provisioning, legacy global Admin/custom roles, complete cross-organization relationship constraints, and system-role permission display remain separate work. No historical duplicate-role cleanup was performed.

Platform organization selection is implemented for JWT/cookie HTTP sessions. Organization-bound developer API keys and WebSocket organization switching are not covered by this flow. In particular, old API keys whose owner is detached from organization membership need a separate ownership review; this change does not silently transfer them.

The complete backend unit suite was not used as the final passing evidence; an earlier baseline run progressed unusually slowly. The relevant focused suites and isolated database workflow provide the verification stated above. Production deployment, browser-level end-to-end verification, and credentials remain pending.
