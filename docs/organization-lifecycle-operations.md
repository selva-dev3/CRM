# Organization lifecycle operations

## Scope and existing architecture

Platform operations preserve the existing JWT/cookie session, `is_platform_admin`
identity, tab-local `X-Organization-ID` selection and fresh-document switching.
The protected account remains `superadmin@mycrm.com`, with no organization and no
tenant role mappings. Existing PostgreSQL singleton/protection constraints and
triggers remain authoritative. No existing roles, users or credentials are repaired
or rewritten by this feature.

Creation is centralized in `OrganizationLifecycleService`. Public registration is
disabled; the legacy new-organization invitation endpoint delegates to provisioning.
Invitation acceptance may only join an existing organization. It cannot create an
organization or replace an existing account/password.

POST `/api/v1/organizations` accepts a trimmed name (1–255 characters) and optional
`initial_admin: {name, email}`. One transaction creates the organization, settings,
free subscription, exactly six scoped roles with `SYSTEM_ROLE_PERMISSIONS`, optional
initial Admin invitation, and platform audit event. Email delivery follows commit;
a delivery failure is reported without pretending provisioning failed.

DELETE `/api/v1/organizations/{id}` is explicitly platform-only. It locks the parent
and owned rows, checks dependencies, records the durable cleanup manifest/audit,
deletes restrictive children and then the organization in one transaction. Tenant
users and sessions cascade; the platform identity survives. Zero organizations is
supported. Further requests from deleted tenant accounts are unauthorized.

GET `/api/v1/organizations/deletions/{operation_id}` reports file cleanup; POST to
that path plus `/retry` requeues failed items. Both require the platform account.
Database records are deleted immediately at commit. Stored files are removed by a
durable worker afterwards. Foreground document, lead attachment, avatar, branding
and report uploads hold a parent KEY SHARE lock through the metadata commit;
deletion holds FOR UPDATE. Existing delivery workers advertise persisted active
work/leases that block deletion. Cleanup inventories retained references once per
bounded 50-item batch, retaining only matches to those batch keys. Recovery or manual object-reference reassignment requires
pausing cleanup first: reference checks cannot be atomic with external storage. Deletion operation/audit records and external backups
remain. Previously issued storage links may work until cleanup completes.

## Dependency analysis

The pre-implementation read-only production audit found 164 public foreign keys at
revision `r1a2b3c4d5e6`. Model metadata supplies the complete direct organization
scope; the explicit `INDIRECT_OWNERS` registry covers dependent records without an
organization column. Every FK referencing owned data is checked for non-owned
references before deletion, including SET NULL relationships. Such references block
rather than silently modify another tenant.

Direct scope includes organizations/settings/subscriptions, users/roles, CRM leads,
contacts, companies, deals/stages/history, activities, tasks, meetings, calls,
emails, documents, products/categories, quotes/delivery attempts, invoices/payments,
reports/exports/schedules, notifications, notes, projects, integrations, API keys,
AI conversations/runs/actions, invitations, quotas, and tenant configuration.
The exact model-derived table/FK inventory is in `organization-lifecycle-dependencies.md`.

Indirect scope includes user profiles/sessions/refresh tokens/password resets,
email/OTP verifications/magic links/calendar events/user-role mappings, role grants,
lead scores/tags/activities/notes/attachments, contact addresses/tags, company contacts,
deal products/activities, document versions, email logs, quote/invoice items,
meeting attendees, task comments/attachments, AI prompts/scores/summaries.

Restrictive relationships: converted lead company/contact/deal, quote automatic
 deal/company/contact, deal-product product. Delete leads, quotes, then deal products
before the parent cascade. Payments and provider-linked/unreconciled subscriptions
block deletion. Processing or unresolved external work blocks deletion. Unrecognized
or shared object keys block deletion. Unscoped file upload records are retained and
included in shared-file checks. Scheduled report object prefixes are inventoried
before deletion. Storage inventory has limits of 10,000 objects and 64 owner prefixes per deleted
tenant, with a 60-second preparation deadline before commit. Larger tenants require
a separately reviewed maintenance deletion. The browser allows two minutes and
refreshes the list on failure. Shared-reference
checks stream surviving references without imposing a platform-wide file limit.
Prefix collisions use four target-driven database existence checks rather than
transferring every platform owner.
Known organization, user, lead and scheduled-export prefixes also capture orphaned
uploads and previous branding/avatar files. Safe legacy string IDs are supported; overlapping or unsafe owner prefixes require
manual storage-ownership review.

Migration `s2b3c4d5e6f7` adds case-insensitive trimmed-name uniqueness; fills missing
CASCADE organization FKs on `user_invitations`, `custom_fields`, `sla_policies`; and
adds durable deletion/cleanup tables. It aborts on duplicate names or orphan IDs;
it never silently reconciles existing data. Historical migrations are unchanged.

## Production recovery and enablement gate

`ORGANIZATION_DELETION_ENABLED` defaults to false. Do not enable solely because the
migration or application deployed. A retained RBAC recovery schema is not a full
backup. Production deletion has not been authorized or performed by implementation.

Before any production deletion:

1. Stop writes and pause all workers for a coordinated backup window. Take a full
   PostgreSQL backup (all schemas, sequences, triggers, constraints and required
   roles) and an object-store backup/version snapshot with a shared timestamp.
   Record retention, access controls, backup IDs, checksums and owners in the
   operations change record, not in source control. Do not put credentials in shell
   arguments or logs.
2. Restore both into isolated infrastructure with outbound email, Stripe, webhooks
   and integration delivery disabled. Validate migration revision, row counts,
   constraints, singleton platform identity/login, tenant switching and sample file
   checksums. Record measured restore time and verified recovery point.
3. Review the exact migration and preflight names/orphans/FKs against the deployed
   schema. Apply the migration to staging first, then production in the approved
   maintenance window. Never edit historical migration files or manually patch schema.
4. Obtain separate approval for paid Render worker/scheduler resources. Configure
   the reviewed blueprint with the existing private database/broker/storage and
   all required service settings using Render secret inputs; never generate a new
   platform identity or replace the signing key. Run exactly one beat instance.
   The dedicated scheduler uses `ORGANIZATION_CLEANUP_ONLY=true` and the worker
   consumes only `organization_cleanup`; it must not consume delivery/provider
   backlog. Other production workers retain their existing schedules.
5. Verify worker heartbeat and beat scheduling, then use a controlled test org and
   test object to prove manifest processing, retry and status visibility. Enable
   deletion only after the recovery evidence and worker readiness are approved.
6. With explicit authorization, create/delete only the named controlled production
   test organization. Verify the platform can still login and open remaining
   organizations; tenant sessions fail, files disappear and audit/status persist.
   Compare existing organization/user counts and credentials checksums without
   displaying credentials. Do not delete pre-existing organizations for testing.

Recovery: disable deletion, pause writes and cleanup immediately. Restore the
coordinated database and object snapshot to an isolated environment, verify it,
then perform an approved cutover. Partial tenant restoration is not implemented;
full restoration can lose writes after the recovery point and must be coordinated.
Do not simply restore the organization row or retry old manifests after a restore.
The forward-only migration deliberately refuses automatic downgrade.

## Existing default-role gaps (read-only audit)

My CRM has five scoped default roles and lacks Admin. 12345, Susanoox and test have
no scoped default roles. These remain unchanged. A separately reviewed remediation
should inventory names, grants and assignments, preview only missing scoped roles,
then insert missing roles/grants transactionally. Do not replace custom roles or
reassign existing users automatically. Back up and test that migration separately.

## Deployment configuration

`deploy/render-organization-workers.yaml` is a reviewable, unapplied blueprint for
two paid Docker background workers. It intentionally does not manage the existing
web service or database. Confirm the deployment branch, region, costs, environment
values and backlog before approval. See [Render's Blueprint reference](https://render.com/docs/blueprint-spec)
for worker, Docker command and secret-input semantics.

Render validation: configuration was submitted without deployment. After adding
the repository URL, only `need_payment_info` remained for both paid workers.
Account billing setup and resource creation require separate approval.
