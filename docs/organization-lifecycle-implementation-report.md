# Organization lifecycle implementation report

Implementation is uncommitted on `feature/super-admin-organization-lifecycle`.
No production migration, organization deletion, user/credential modification,
worker deployment, commit or push was performed. Production deletion defaults off.

## APIs and flows

- POST `/api/v1/organizations`: explicit authenticated platform admin, validated
  name and optional Admin invite, centralized atomic provisioning, 201 response.
- DELETE `/api/v1/organizations/{id}`: explicit platform admin, recovery gate,
  dependency/work/billing/storage checks, atomic tenant database deletion and
  durable file-cleanup manifest. Global account, global roles and audit survive.
- GET `/api/v1/organizations/deletions/{operation_id}` and POST same path plus
  `/retry`: platform-only cleanup status and failed-item retry.
- POST `/api/v1/organizations/invitations/new-organization`: platform-only adapter
  to centralized provisioning. POST `/api/v1/auth/register`: controlled 403.
- Public invitation acceptance joins only its existing active organization and
  cannot change organization details or existing account credentials. Additional
  invitations cannot take over another tenant's pending initial Admin invitation.

Every newly provisioned tenant gets exactly Admin, Sales Manager, Sales Executive,
Marketing Executive, Customer Support and Read Only. All role IDs are new records
scoped to the new organization, with exactly the approved existing matrix grants.
There is no new Super Admin or immediate duplicate onboarding user. Acceptance
creates one user and assigns the invitation's scoped role in both role mappings.

## Database and recovery

Forward migration `s2b3c4d5e6f7`, based on the current upstream authentication
hardening revision `s3c4d5e6f7a8`, adds normalized-name uniqueness, the three missing
organization FKs and two cleanup/audit-operation tables. Duplicate names/orphans
abort migration without modifying them. The migration was exercised on disposable
local PostgreSQL, including duplicate-preflight rollback. Historical migrations
and production data remain unchanged.

See [complete dependency inventory](organization-lifecycle-dependencies.md) and
[recovery, rollout and existing-role remediation plan](organization-lifecycle-operations.md).
The inventory covers 91 tables and 78 direct/indirect tenant-owned tables. Production
was audited read-only at the previous revision; three payments, provider billing,
and missing default roles require separate operational review, not automatic cleanup.

## Frontend and caches

The existing Organizations list/Open/switch flow now has a platform-only create
modal and explicit permanent-delete confirmation. Name validation, loading/errors,
optional Admin invitation delivery status, cleanup polling/retry, and list refresh
use the existing form/UI/query conventions. Tenant invite/delete/bulk-delete
controls were removed. Registration explains invitation-only onboarding.

Selected-organization deletion cancels requests, clears tenant caches/context and
returns to the global list. Other tabs receive deletion notifications. Deleted
account sessions are rejected by the backend; the frontend clears invalid auth.
Stale requests from an old organization cannot clear a newer valid selection.
The latest deletion operation survives the selected-context redirect in tab storage.

## Review and validation

The different-model review identified invitation metadata mutation, cross-tenant
invitation takeover, upload/deletion concurrency and cleanup inventory repetition.
Those findings were addressed with tests. The review also led to scoped role-name
responses, serialized invitation capacity and status transitions, complete provider
linkage guards, orphan-file prefix inventory with collision checks, bounded deletion
preparation, a dedicated cleanup queue/scheduler, complete accepted-user authorization
state, inactive-account conflict handling, legacy global-role ID remapping and
distinct-key storage inventory accounting. After upstream authentication hardening
was integrated, the review also identified and drove fixes for invitation token-family
expiry metadata, password byte limits, tenant deletion/deactivation invitation races,
and stale expired-token validation writes. The final independent review reported no
remaining blocking or actionable issues.

Completed checks include 1,150 passing backend unit tests, 391 frontend tests,
frontend lint, the production build, lifecycle mypy checks and 37 fresh PostgreSQL
lifecycle/platform integration tests after integrating the current `origin/main`.
The backend unit run has six order-dependent subscription-test failures; an isolated
run of those tests passes, and unchanged `origin/main` produces the identical six
failures (with 1,128 passing tests). The lifecycle change therefore adds 22 passing
unit tests and no new full-suite failures.

The broader existing CRM suite returned 37 failed / 22 passed both on the feature
and on unchanged HEAD in a second isolated database; the failing test names match
exactly. Those failures include pre-existing deal-stage fixture assumptions and a
startup harness hard-coded to a different database/role. No sales/billing business
logic was changed to hide those failures. The shared test fixture now uses unique
organization names to respect the new uniqueness constraint.

Browser discovery returned no available browser. Responsive visual and live UI
end-to-end verification therefore remain unverified. Production verification is
also outstanding: a verified backup/restore drill and approved paid worker rollout
are required. Render blueprint validation reports `need_payment_info` for both
workers; no resources were created. The default production delete gate stays off.

## Acceptance status

| Requirement | Status |
| --- | --- |
| Super Admin Create Organization | PASS |
| Super Admin Delete Organization | PASS (controlled local PostgreSQL; production gate remains off) |
| Six default roles created | PASS |
| Organization-scoped roles | PASS |
| No duplicate Super Admin | PASS |
| Super Admin survives deletion | PASS |
| Organization switcher works | PASS |
| Normal users blocked | PASS |
| Cross-org isolation | PASS |
| Transaction safety | PASS |
| Cache refresh | PASS |
| Tests passing | PASS (feature/relevant suites) |

Production verification: NOT PERFORMED. It requires the recovery drill, worker
rollout and explicit authorization described in the operations guide. Browser visual
verification: NOT PERFORMED because no browser runtime was available.

## Files changed

- `backend/alembic/versions/s2b3c4d5e6f7_organization_lifecycle.py`
- `backend/app/api/v1/deps.py`
- `backend/app/api/v1/routers/auth.py`
- `backend/app/api/v1/routers/invitations.py`
- `backend/app/api/v1/routers/organizations.py`
- `backend/app/core/config.py`
- `backend/app/models/__init__.py`
- `backend/app/models/auth.py`
- `backend/app/models/organization.py`
- `backend/app/models/organization_deletion.py`
- `backend/app/models/system.py`
- `backend/app/repositories/organization_lifecycle_repository.py`
- `backend/app/repositories/organization_repository.py`
- `backend/app/repositories/role_repository.py`
- `backend/app/schemas/crm_schemas.py`
- `backend/app/schemas/organization_invitation_schemas.py`
- `backend/app/schemas/organization_lifecycle.py`
- `backend/app/services/auth_service.py`
- `backend/app/services/document_service.py`
- `backend/app/services/invitation_service.py`
- `backend/app/services/lead_service.py`
- `backend/app/services/organization_cleanup_service.py`
- `backend/app/services/organization_lifecycle_service.py`
- `backend/app/services/organization_service.py`
- `backend/app/services/organization_storage_service.py`
- `backend/app/services/report_service.py`
- `backend/app/services/role_service.py`
- `backend/app/services/s3_service.py`
- `backend/app/services/user_service.py`
- `backend/app/tests/integration/test_organization_lifecycle.py`
- `backend/app/tests/integration/test_platform_admin_workflow.py`
- `backend/app/tests/integration/test_sales_quote_workflow.py`
- `backend/app/tests/unit/test_alembic_revision_graph.py`
- `backend/app/tests/unit/test_auth_service.py`
- `backend/app/tests/unit/test_invitation_service.py`
- `backend/app/tests/unit/test_organization_lifecycle_guards.py`
- `backend/app/tests/unit/test_rbac_permissions.py`
- `backend/app/tests/unit/test_role_service.py`
- `backend/app/workers/celery_app.py`
- `backend/app/workers/tasks.py`
- `deploy/render-organization-workers.yaml`
- `docs/organization-lifecycle-dependencies.md`
- `docs/organization-lifecycle-implementation-report.md`
- `docs/organization-lifecycle-operations.md`
- `frontend/src/app/(auth)/register/page.tsx`
- `frontend/src/app/(dashboard)/organization/page.tsx`
- `frontend/src/app/accept-invite/organization/[token]/page.test.tsx`
- `frontend/src/app/accept-invite/organization/[token]/page.tsx`
- `frontend/src/components/features/auth/login-form.tsx`
- `frontend/src/components/features/organizations/create-organization-dialog.tsx`
- `frontend/src/components/features/organizations/platform-organizations.test.tsx`
- `frontend/src/components/features/organizations/platform-organizations.tsx`
- `frontend/src/lib/api/client.test.ts`
- `frontend/src/lib/api/client.ts`
- `frontend/src/lib/api/organization-lifecycle.test.ts`
- `frontend/src/lib/api/organizations.ts`
- `frontend/src/lib/organization-context.ts`
- `frontend/src/providers/auth-provider.test.tsx`
- `frontend/src/providers/auth-provider.tsx`
