# Organization subscription Stripe restoration

## Scope and root cause

The user clarified that organization subscription purchases/upgrades require
Stripe, while customer Invoice/Payment workflows must remain manual. The earlier
implementation removed both integrations, disabling subscription checkout. This
report supersedes the subscription-removal portions of
`stripe-free-implementation-report.md`; its customer-billing architecture remains.

Work is on `feat/manual-invoice-payments`. No production migration, live payment,
credential change, commit, push, or PR is part of this correction.

## Required separation

| Domain | Workflow | Persistence |
| --- | --- | --- |
| Organization subscription | Plan selection → Stripe-hosted payment/upgrade confirmation → verified webhook → subscription and entitlement synchronization | Existing OrganizationSubscription and ProcessedWebhookEvent models |
| Customer sales billing | Quote acceptance → Draft invoice → Finalize → Email → Customer acceptance → Manual payment → Partial/Paid | Existing Invoice and Payment models |

Subscription webhooks do not create customer CRM invoices or payment records.
Stripe's own subscription invoices are provider billing evidence, not CRM sales
invoices. Frontend Stripe SDKs and publishable keys are unnecessary for the hosted
redirect flow implemented here.

## Implementation changes

| File/area | Change | Risk |
| --- | --- | --- |
| `backend/app/services/subscription_billing_service.py` | Subscription-only orchestration, tenant checks, checkout recovery, provider verification, webhook synchronization and renewal controls | High: entitlements and provider reconciliation |
| `backend/app/services/subscription_stripe_provider.py` | Lazy Stripe SDK adapter; hosted Checkout for initial purchase and portal confirmation for an existing subscription | High: external provider configuration and API compatibility |
| `backend/app/api/v1/routers/organizations.py` | Restore checkout, read-only verification and signed webhook endpoints | Medium: permission and API contracts |
| `backend/app/services/organization_service.py` | Delegate linked subscription cancellation/resumption to Stripe; continue blocking direct entitlement edits | Medium: recurring billing behavior |
| `backend/app/repositories/organization_repository.py` | Organization locking, exact provider identifiers and processed-event persistence without independent commits | High: concurrency and tenant isolation |
| `backend/app/models/organization.py` | Restore checkout-session tracking and add operation recovery/fingerprint fields | Medium: requires forward migrations |
| `backend/app/schemas/crm_schemas.py` | Restore typed subscription checkout/verification DTOs; validate plan and reject extra request fields | Low |
| `backend/app/core/config.py` | Optional subscription-only Stripe configuration | Low: startup must remain independent |
| `backend/requirements.txt` | Restore the installed Stripe SDK version, pinned to 15.6.0 | Medium: provider compatibility |
| `frontend/src/lib/api/organizations.ts` | Restore subscription API calls and query/mutation hooks | Medium: API compatibility |
| `frontend/src/lib/api/subscription-checkout.ts` | Persist retry operations per user/organization; verify completion and bound polling | Medium: uncertain outcomes and browser storage |
| `frontend/src/app/(dashboard)/organization/subscription/` | Restore plan upgrade and success/cancel UX using server verification | Medium: redirect/retry states |
| Subscription backend/frontend tests | Replace obsolete subscription-removal assertions and add security, recovery, migration and UI checks | Low: no live gateway operations |
| `backend/app/tests/unit/test_billing_domain_boundary.py` | Assert optional configuration and no subscription-gateway imports in customer billing modules | Low |

The existing unrelated `backend/celerybeat-schedule` modification is preserved.
No `.env`, credentials, deployed secrets, or environment example files were edited
during this correction. The example file still has an earlier uncommitted change;
the subscription configuration requirements are documented below instead.

## APIs

All paths below are relative to `/api/v1`.

| Method/path | Contract |
| --- | --- |
| `POST /organizations/subscription/checkout` | Billing permission; body `plan_slug`, optional same-tenant `org_id`; required UUID `Idempotency-Key`. Returns hosted checkout/portal URL. |
| `GET /organizations/subscription/checkout/verify` | Billing permission; optional `session_id`, `plan_slug`, same-tenant `org_id`. Reads provider verification and local webhook synchronization; does not grant entitlements. |
| `POST /organizations/subscription/webhook` | Raw body validated against `Stripe-Signature`; subscription-specific processing only. No browser authentication dependency. |
| `POST /organizations/subscription/cancel` | Existing permission checks; linked Stripe subscription schedules cancellation at period end. |
| `POST /organizations/subscription/resume` | Existing permission checks; linked eligible Stripe subscription clears period-end cancellation. This is not a new subscription. |
| `POST /organizations/subscription/upgrade` | Direct unverified plan mutation remains disabled; use checkout. |

Customer `/invoices/{id}/payments` remains a manual payment endpoint. Customer
invoice checkout and customer payment webhook endpoints remain removed.

## Security and correctness

- Organization comes from the authenticated user. A caller-supplied organization
  must match; role-name strings cannot bypass tenant ownership.
- Plans and amounts are resolved server-side. Unknown, inactive, free or invalid
  paid prices do not create paid checkout. Existing monthly INR pricing is retained;
  annual billing is not newly introduced.
- Initial checkout records its operation before provider side effects. Retries use
  scoped provider idempotency and persisted state. Unknown outcomes fail closed
  rather than creating another subscription after the retry window.
- A request fingerprint detects changed prices, return configuration or target
  subscription while a request is being retried.
- Existing paid subscriptions use `subscription_update_confirm` for the same
  subscription item. The user reviews billing adjustments in Stripe before
  confirmation; the backend does not silently create a second recurring contract.
- Webhook processing retrieves current provider state rather than applying stale
  event snapshots. Entitlement updates and event deduplication share a database
  transaction. A browser success redirect alone is not payment evidence.
- Different events for the same paid invoice do not replenish spent AI credits.
  Subscription-row locking serializes billing changes with AI credit consumption.
  A pending upgrade preserves existing paid access without granting the new plan.
- Existing provider/customer associations and archived terms are checked when
  reconciling historical subscriptions that lack new price metadata.
- Renewal controls confirm the provider result before changing local renewal flags.
- Customer invoice finalization, acceptance, manual payment idempotency,
  organization isolation, partial payment and overpayment rules remain independent.

## Database migration and rollout

Historical migrations and the already exercised manual invoice migration are not
rewritten. Two additional forward migrations are used:

1. `f9a2b3c4d5e6_restore_subscription_checkout.py` follows `e8f1a2b3c4d5`.
   It restores `checkout_session_id` from the retained JSON archive, adds
   `checkout_operation_id`, `checkout_plan_slug`, `checkout_expires_at`, and indexes
   checkout/subscription identifiers. It does not change existing paid amounts,
   plan entitlements, customer/subscription IDs or archived evidence.
2. `g0b3c4d5e6f7_subscription_checkout_request_hash.py` follows the restoration
   revision and adds nullable `checkout_request_hash`. It is separate because the
   preceding revision had already been exercised in the test database.

Both revisions are forward-only to avoid discarding billing recovery evidence.
Before deployment, back up the database, inspect its actual Alembic revision, and
apply the complete migration chain in a maintenance window with old writers
stopped. Do not deploy subscription code against the intermediate schema.

For installations not yet on the manual workflow, the chain temporarily archives
and then restores the organization checkout-session field. The archive remains.
For installations already on the manual workflow, only subsequent revisions are
needed. The code has not inspected or migrated production.

## Deployment configuration

- Install backend requirements, including `stripe==15.6.0`.
- Set `STRIPE_SECRET_KEY` for organization subscription billing.
- Set `STRIPE_WEBHOOK_SECRET` to the signing secret for the organization
  `/api/v1/organizations/subscription/webhook` endpoint, not an old customer-payment
  endpoint. Register the endpoint in the appropriate test/live Stripe account.
- Optionally set `STRIPE_SUBSCRIPTION_PORTAL_CONFIGURATION_ID`; otherwise the
  account's default portal configuration is used. Configure the portal to support
  the intended subscription update flow and confirm its billing behavior in test mode.
- Check `FRONTEND_URL` so its canonical first URL points to the deployed frontend.
- No publishable key is needed. No actual keys are recorded in this document.
- Without Stripe configuration, subscription operations return an explicit error;
  normal CRM startup and manual customer invoice/payment processing must still work.

Supported subscription events include `checkout.session.completed`,
`checkout.session.async_payment_succeeded`, `invoice.paid`, `invoice.payment_failed`,
`customer.subscription.updated`, and `customer.subscription.deleted`. Unrelated
events are not applied to customer sales billing.

Provider references:
[subscription webhook lifecycle](https://docs.stripe.com/billing/subscriptions/webhooks),
[hosted upgrade confirmation](https://docs.stripe.com/customer-management/portal-deep-links),
[webhook signatures and retries](https://docs.stripe.com/webhooks).

## Verification

| Check | Result | Evidence |
| --- | --- | --- |
| Focused subscription service/provider/workflow checks | PASS | 56 tests including 20 real PostgreSQL cases; provider calls are substituted |
| Migration, organization and manual-billing boundary checks | PASS | 42 tests; restored archived checkout data and current entitlements remain intact |
| Actual Stripe SDK contract | PASS | Five cases using installed 15.6.0 objects: checkout, subscription, price list, signed event conversion and tamper rejection; child processes inherit no credentials and reject network access |
| Full backend suite | FAIL — unchanged existing failures | 1,068 passed, eight failed, 77 warnings in 120.50 seconds |
| Frontend full suite | PASS | 57 test files, 320 tests |
| Frontend lint and TypeScript | PASS | `npm run lint`, `npx tsc --noEmit` |
| Frontend production build | PASS | 42 static pages, including subscription plans/success/cancel and public customer invoice |
| Scoped backend Ruff/Black/Mypy | PASS | Restored subscription modules, routes and tests checked |
| Full backend Ruff | FAIL — unchanged existing findings | One B904 in `call_service.py`; three unused imports in `quote_service.py` |
| Startup without Stripe | PASS | Actual application lifespan, `/health` HTTP 200, database `ok`, Stripe SDK imports blocked |
| Customer invoice/payment regressions | PASS | Included in full backend/frontend suites; manual partial/full payment and accepted-invoice restrictions remain enforced |
| Forward migrations | PASS on disposable PostgreSQL | Checkout restoration followed by request fingerprint; expected head `g0b3c4d5e6f7` |
| Real Stripe test-account checkout/webhook delivery | BLOCKED | No configured test-account verification was performed; no actual payment requested |
| Browser UI verification | BLOCKED | Browser skill connection/discovery returned no available browser (`[]`) |

The eight backend failures are the same independently reproduced pre-existing
failures: two call-service tests use invalid mocks, and six scheduled-report tests
expect delivery despite the isolated runner intentionally having no Brevo key.
These files were not modified. No new failing tests appeared in the full run.
The four previously reported repository-wide Ruff findings also remain unchanged.

The migration fixture initially omitted a historical required `is_active` field.
That new fixture was corrected; the subsequent populated-migration run passed.
Alembic tests use in-memory configuration and assert preservation of pytest logging.

Commands used from the appropriate project directory:

```sh
# Uses only the disposable localhost crm_workflow_test database; ignores dotenv.
.venv/bin/python -m app.tests.run_isolated_workflow --migrate
.venv/bin/python -m app.tests.run_isolated_workflow --startup
.venv/bin/python -m app.tests.run_isolated_workflow -q --tb=short

npm test
npm run lint
npx tsc --noEmit
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000/api/v1 npm run build
```

Live Stripe test-mode checkout and webhook delivery still require a configured
test account. Passing database and SDK-object tests does not prove that a deployed
Stripe account, portal configuration or webhook destination is correct.

## Remaining release checks

- Controlled Stripe test-mode initial purchase, hosted upgrade, failed payment,
  renewal and cancellation with real webhook delivery.
- Actual browser interaction and responsive checks when a browser is connected.
- Production migration/state review and deployment configuration.
- Previously isolated call-service and scheduled-report test fixture failures are
  outside this correction; no real Brevo key should be added merely to pass tests.
- Existing expired or otherwise ambiguous provider operations may require manual
  reconciliation; the code must not guess that a payment failed and issue another.

## Verdict

PARTIALLY COMPLETE — subscription-only restoration is implemented and automated
checks pass apart from the eight existing backend test failures. Release still
requires configured Stripe test-mode, browser, and production migration checks.
No live payment success is claimed.
