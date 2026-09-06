# Stripe-free invoice and manual-payment implementation

> Scope correction: the user subsequently confirmed that organization subscription
> upgrades must keep Stripe. The subscription-removal findings below describe the
> earlier implementation checkpoint, not the final required architecture. Customer
> Invoice/Payment workflows remain manual and Stripe-independent. Subscription
> restoration is documented separately in `organization-subscription-stripe-restoration.md`.

## 1. Executive summary

Implemented on `feat/manual-invoice-payments`. The former customer invoice checkout
and webhook flow has been replaced with explicit invoice finalization, secure
customer acceptance, and internal manual payment records. Quote generation and
acceptance, document totals, PDF rendering, S3/MinIO storage, Brevo email delivery,
Celery jobs, receipt delivery, and existing payment numbers are reused.

Subscription checkout is also removed. Existing subscription entitlements are
preserved; plan upgrades require administrator coordination rather than an
unverified self-service upgrade. No new payment gateway or simulated transactions
are introduced.

This report distinguishes implemented code, automated verification, and deployment
work. No production database migration, production email, commit, push, or PR has
been performed as part of this implementation.

## 2. Old workflow

Accepted quote → Pending invoice and queued delivery → provider checkout → invoice
email containing a checkout link → signed provider event → one full payment → Paid.

Invoice generation and delivery were coupled. Invoice payment state and document
state shared one status. `payments.invoice_id` was unique, preventing partial or
multiple payments.

## 3. New workflow

Accepted quote → Draft invoice → internal review → Finalized → queued PDF/email
delivery → secure customer review → Accepted → Add Payment → Partially Paid / Paid.

| Concept | Stored state / evidence |
| --- | --- |
| Generated / reviewed internally | Draft; existing invoice items and billing snapshot |
| Finalized | Finalized, `finalized_at`, `finalized_by` |
| Delivery | Existing Pending / Processing / Sent / Failed / Unknown tracking |
| Customer accepted | Accepted, `accepted_at`; idempotent public acceptance |
| Collection progress | Separate Pending / Partially Paid / Paid `payment_status` |
| Money received | Individual manual Payment records, date/type/amount/notes/actor |

`Succeeded` remains the existing payment-record status for compatibility. In this
workflow it denotes a successfully saved manual record, not gateway verification.
Customer acceptance never creates a payment or marks an invoice Paid. Overdue is
derived from due date and outstanding balance, not a document lifecycle status.

## 4. Dependency removal

- Removed the backend invoice checkout service and payment webhook router.
- Removed quote checkout, invoice checkout, subscription checkout/verification/
  webhook routes, and their frontend calls.
- Removed the Python Stripe dependency and settings fields. Frontend had no Stripe
  SDK dependency to remove.
- Removed the three Stripe entries from the example environment configuration.
  Actual environment/credential files and deployed secrets were not edited.
- Removed checkout links, payment-provider messaging, and the integration catalog
  entry from the UI. Invoice email links now open `/public/invoice#<token>`.
- Historical migration files are unchanged. New migration SQL, migration tests,
  historical-preservation tests, and audit documentation necessarily retain names
  of the fields/provider they migrate.

## 5. Changed files and risks

Paths below are relative to the repository root. The existing change to
`backend/celerybeat-schedule` is unrelated and was not part of this work.

| File | Change and reason | Risk |
| --- | --- | --- |
| `backend/alembic/versions/e8f1a2b3c4d5_manual_invoice_billing.py` | Forward migration, validation and evidence archives | High: coordinated migration required |
| `backend/app/models/invoice.py` | Lifecycle, acceptance, token and archive fields | High: schema compatibility |
| `backend/app/models/payment.py` | Manual fields, multiple payments, constraints and actor | High: financial persistence |
| `backend/app/models/organization.py` | Preserve archived subscription evidence; remove checkout mapping/default | Medium |
| `backend/app/models/integration.py` | Remove obsolete provider comment | Low |
| `backend/app/repositories/invoice_repository.py` | Scoped locks, token lookup/queueing, lifecycle-aware overdue/reminders | High: locking and delivery |
| `backend/app/repositories/payment_repository.py` | Actual payment sums, manual inserts, numbering, idempotency, audits/notifications | High: accounting/concurrency |
| `backend/app/repositories/report_repository.py` | Outstanding and overdue use new lifecycle | Medium: reporting semantics |
| `backend/app/repositories/organization_repository.py` | Remove provider-specific subscription lookups | Low |
| `backend/app/repositories/auth_repository.py` | Remove provider default on registration | Low |
| `backend/app/services/invoice_service.py` | Draft generation, validated finalization, guarded editing/sending/deletion | High: document lifecycle |
| `backend/app/services/invoice_state.py` | Separate document lifecycle from payment status | Medium |
| `backend/app/services/payment_service.py` | Transactional manual payment validation and safe retry handling | High: accounting |
| `backend/app/services/public_invoice_token.py` | Invoice-specific HMAC capability and stored digest | High: public access |
| `backend/app/services/public_invoice_service.py` | Scoped capability view/acceptance, expiry, safe public response and PDF link | High: public access |
| `backend/app/services/invoice_delivery_service.py` | Review links, balance reminders, partial-payment receipts; no checkout | High: external delivery |
| `backend/app/services/invoice_pdf_service.py` | Manual-payment receipt/document wording | Low |
| `backend/app/services/invoice_payment_service.py` | Deleted obsolete gateway implementation | Medium: removed API |
| `backend/app/services/quote_service.py` | Removed public checkout only | Low: quote acceptance retained |
| `backend/app/services/organization_service.py` | Remove subscription provider flow and prevent unpaid entitlement escalation | Medium: upgrade availability |
| `backend/app/services/integration_service.py` | Remove obsolete catalog entry and simulated webhook handler | Low |
| `backend/app/api/v1/api.py` | Register public invoices; unregister payment webhook | Medium |
| `backend/app/api/v1/routers/invoices.py` | Finalize/manual-payment APIs, updated guarded edits | High: API contract |
| `backend/app/api/v1/routers/payments.py` | Manual record descriptions and consistent not-found response | Low |
| `backend/app/api/v1/routers/public_invoices.py` | Rate-limited public view/acceptance; no-store responses | High: public access |
| `backend/app/api/v1/routers/public_quotes.py` | Remove checkout endpoint | Low |
| `backend/app/api/v1/routers/payment_webhooks.py` | Deleted unused gateway route | Medium |
| `backend/app/api/v1/routers/organizations.py` | Remove provider routes; administrative upgrade guidance | Medium |
| `backend/app/schemas/crm_schemas.py` | Typed lifecycle, manual payment and restricted public DTOs | Medium |
| `backend/app/core/config.py` | Remove gateway settings | Low |
| `backend/requirements.txt` | Remove gateway SDK requirement | Low |
| `backend/.env.example` | Remove gateway-only variables from example | Low |
| `frontend/src/app/(dashboard)/invoices/page.tsx` | Lifecycle filters and manual-payment wording | Medium |
| `frontend/src/app/(dashboard)/invoices/[id]/page.tsx` | Review, finalization, delivery, acceptance and payment history | Medium |
| `frontend/src/app/(dashboard)/payments/page.tsx` | Manual type/date/notes, no provider identifiers | Medium |
| `frontend/src/app/public/invoice/page.tsx` | Public customer invoice route | Medium |
| `frontend/src/components/features/invoices/InvoiceWorkflowActions.tsx` | Authorized finalize/Add Payment and retry-safe modal | High: payment UX |
| `frontend/src/components/features/invoices/PublicInvoiceView.tsx` | Customer review/confirmation and explicit errors | Medium |
| `frontend/src/components/features/invoices/InvoiceSummary.tsx` | Billing snapshot and separate totals/status evidence | Low |
| `frontend/src/components/features/invoices/InvoiceItemsTable.tsx` | Shared currency-aware server totals and tax/discount rates | Medium |
| `frontend/src/components/features/invoices/README.md` | Workflow and pending-operation behavior | Low |
| `frontend/src/lib/api/client.ts` | Public invoice requests do not refresh/clear CRM authentication | Medium |
| `frontend/src/lib/api/invoices.ts` | Finalization API and expanded invoice DTO | Medium |
| `frontend/src/lib/api/payments.ts` | Manual payment mutation, idempotency header, cache refresh | High |
| `frontend/src/lib/api/public-invoices.ts` | Public token body requests with cookies omitted | High |
| `frontend/src/lib/api/pending-payment.ts` | Persist uncertain operation in same-tab session storage | Medium |
| `frontend/src/lib/api/organizations.ts` | Remove subscription checkout calls | Low |
| `frontend/src/lib/api/quotes.ts` | Remove obsolete payment-link DTO field | Low |
| `frontend/src/lib/types/manual-payment.ts` | Controlled types, decimal/date/notes validation | Medium |
| `frontend/src/lib/types/public-invoice.ts` | Restricted customer invoice contract | Low |
| `frontend/src/lib/formatters/invoice.ts` | Shared financial/date presentation | Low |
| `frontend/src/app/(dashboard)/integrations/page.tsx` | Remove obsolete integration entry | Low |
| `frontend/src/app/(dashboard)/organization/subscription/plans/page.tsx` | Administrator-managed upgrades | Medium |
| `frontend/src/app/(dashboard)/organization/subscription/payment/success/page.tsx` | Legacy route guidance; no payment verification claim | Low |
| `frontend/src/app/(dashboard)/organization/subscription/payment/cancel/page.tsx` | Legacy route guidance; no checkout retry | Low |

Test/documentation changes:

| File | Change / reason | Risk |
| --- | --- | --- |
| `backend/app/tests/integration/test_sales_quote_workflow.py` | Preserve quote regressions; assert Draft invoice without automatic payment/delivery | Low |
| `backend/app/tests/integration/test_manual_invoice_workflow.py` | Real PostgreSQL lifecycle, HTTP permissions, concurrency, balances, startup and edge cases | Low |
| `backend/app/tests/integration/test_manual_invoice_migration.py` | Migrate populated history, reject inconsistent balances and preserve pytest logging | Medium: real forward migration in a disposable schema |
| `backend/app/tests/run_isolated_workflow.py` | Disposable localhost-only configuration, real env files disabled, SDK import blocker | Low; test-only credentials |
| `backend/app/tests/unit/test_alembic_revision_graph.py` | Assert new migration head | Low |
| `backend/app/tests/unit/test_invoice_service.py` | New lifecycle, sending/deletion guards | Low |
| `backend/app/tests/unit/test_invoices_router.py` | Updated route contract tests | Low |
| `backend/app/tests/unit/test_invoice_delivery_service.py` | Review link, partial balances and lifecycle-neutral reminders | Low |
| `backend/app/tests/unit/test_invoice_pdf_service.py` | Manual receipt snapshots | Low |
| `backend/app/tests/unit/test_invoice_payment_service.py` | Removed obsolete checkout tests | Low; replaced by manual payment tests |
| `backend/app/tests/unit/test_payment_service.py` | Manual validation, rollback, idempotency and error codes | Low |
| `backend/app/tests/unit/test_manual_payment_schema.py` | Payment fields and token boundary validation | Low |
| `backend/app/tests/unit/test_workflow_state.py` | Explicit invoice lifecycle transitions | Low |
| `backend/app/tests/unit/test_stripe_checkout.py` | Removed obsolete subscription gateway tests | Low; replacement removal tests added |
| `backend/app/tests/unit/test_subscription_runtime_removal.py` | Route removal, retained entitlements and upgrade restrictions | Low |
| `backend/app/tests/unit/test_organization_service.py` | Remove obsolete provider helper tests | Low |
| `backend/app/tests/unit/test_integration_service.py` | Remove provider placeholder expectations | Low |
| `frontend/src/app/(dashboard)/invoices/[id]/page.test.tsx` | Invoice currency, totals, send states and history | Low |
| `frontend/src/components/features/invoices/InvoiceWorkflowActions.test.tsx` | Eligibility, confirmation, validation and retry recovery | Low |
| `frontend/src/components/features/invoices/PublicInvoiceView.test.tsx` | Customer token, confirmation, errors and server totals | Low |
| `frontend/src/lib/api/manual-invoice-workflow.test.tsx` | API bodies, retry headers, cache invalidation and schema | Low |
| `frontend/src/lib/api/client.test.ts` | Public requests do not disturb CRM authentication | Low |
| `frontend/src/app/(dashboard)/organization/subscription/plans/page.test.tsx` | Administrator-managed upgrade UI | Low |
| `frontend/src/app/(dashboard)/organization/subscription/payment/success/page.test.tsx` | Legacy result page cannot claim verified payment | Low |
| `frontend/src/app/(dashboard)/organization/subscription/payment/cancel/page.test.tsx` | No checkout retry | Low |
| `docs/stripe-free-implementation-report.md` | Implementation, evidence, risk and handoff report | Low |

## 6. Database changes and transition safety

Migration `e8f1a2b3c4d5` follows `d7e8f9a0b1c2`; no historical revision is edited.

- Adds invoice `payment_status`, finalization actor/time, acceptance time, public
  token digest/expiry, and `legacy_provider_data`.
- Adds payment type/date/notes, idempotency key/request hash, recorded actor and
  historical evidence archive. Keeps numbers, original amounts/dates, receipt
  delivery bookkeeping, relationships and record identifiers.
- Removes the one-payment-per-invoice uniqueness constraint and obsolete provider
  uniqueness constraints/columns after archival. Adds scoped retry uniqueness and
  controlled type/positive finite amount constraints.
- Archives old subscription checkout identity, drops that checkout column, and
  removes the database provider default. Existing subscription metadata and
  processed historical webhook records remain evidence, not runtime dependencies.
- Preflight rejects unknown invoice states, invalid amounts, mismatched tenant or
  currency, and balances that disagree with actual succeeded payment records.
  These require operator reconciliation; the migration does not invent payments.
- Old invoices enter Draft review with their paid balance/payment status preserved.
  No historical finalized/accepted timestamp is fabricated. Historical payments are
  read-only type `Legacy`, with original provider evidence archived. Consequently,
  legacy unpaid invoices enter outstanding/overdue lifecycle reporting again only
  after actual finalization.
- Downgrade deliberately refuses to discard financial evidence. Rollback requires
  a tested database/application backup or a reviewed forward corrective migration.

### Deployment order

1. Back up and rehearse restoration of the production database and document objects.
2. Rehearse this migration against a restricted copy; reconcile any preflight failure.
3. Pause billing writes and stop old delivery/reminder/payment workers. Reconcile
   uncertain external deliveries before cutover. Do not run mixed old/new workers.
4. Apply the forward migration, deploy backend and frontend together, then start
   the updated Celery workers/beat.
5. Verify startup, permissions, historical balances and one controlled full workflow.
6. Remove obsolete deployed gateway secrets and webhook registrations through the
   deployment/provider administration tools. Removing application code does not
   cancel subscriptions or recurring charges in an external provider account;
   administrators must separately review those arrangements.

## 7. API changes

| Operation | Result |
| --- | --- |
| POST `/api/v1/invoices/{id}/finalize` | New; scoped Draft validation and finalization |
| POST `/api/v1/invoices/{id}/payments` | New; authenticated manual payment with `Idempotency-Key` |
| POST `/api/v1/public/invoices/view` | New; expiring token body; restricted response |
| POST `/api/v1/public/invoices/accept` | New; repeated acceptance is safe |
| POST `/api/v1/invoices/{id}/send` | Finalization required; queues secure review email |
| GET `/api/v1/payments` and `/{id}` | Existing scoped history with manual fields |
| POST invoice `stripe-checkout`, public quote `checkout`, payment `webhooks/stripe` | Removed |
| Subscription checkout, verify and webhook | Removed |
| Legacy invoice `mark-paid` | Fails explicitly and directs callers to manual payments |
| Subscription upgrade | Fails explicitly; requires administrator coordination |

Payment payload uses `payment_type`, decimal `amount`, ISO `payment_date`, optional
`notes`. Currency, tenant, paid balance and outstanding balance are server-owned.
The existing two-decimal money convention is preserved. Payment dates cannot be
future dates in UTC; the UI states that boundary.

## 8. UI changes

Draft shows finalization, not sending/payment controls. Finalized invoices expose
Send Invoice and delivery status. Accepted invoices with a positive balance expose
Add Payment, subject to permissions. Paid invoices hide Add Payment. Tables display
server-calculated item totals and actual invoice currency, including tax/discount.

Public links open invoice details, billing information, PDF and explicit acceptance
confirmation. No online payment control is present. The CRM history supports
multiple manual records and separate total/paid/outstanding summaries.

Uncertain payment submissions retain their operation key and payload across a
same-tab reload. Definitive validation/balance rejection allows correction;
ambiguous failures and idempotency conflicts do not silently start a new payment.
Clearing session storage or moving to a different browser/tab loses that local
retry context; check existing receipts before starting another operation.

## 9. Security and transaction guarantees

- Invoice/payment routes use existing authentication and granular invoice
  permissions. Organization is resolved from the current user, not the request body.
- Payment creation locks the scoped invoice, checks finalization and acceptance,
  sums actual payment rows, validates the amount and inserts/updates/audits in one
  transaction. Organization sequence locking preserves payment numbering.
- Retry keys are unique per organization/invoice; canonical request hashes reject
  a reused key with changed details. Replay is checked before fully-paid rejection.
- Finalization locks the document and validates scoped customer linkage, complete
  billing fields, email, currency, due date, item snapshots and all totals.
- Public capabilities use a distinct HMAC domain, stored SHA-256 digest and expiry.
  Tokens travel in the URL fragment and POST body, not server query logs. Public
  DTOs exclude internal IDs/archive fields. Endpoints are rate-limited and no-store.
- Finalized documents cannot be edited. Cancellation revokes access and is blocked
  for paid invoices or active/uncertain delivery; deletion locks before validation.

## 10. Tests and checks

| Check | Result | Evidence / boundary |
| --- | --- | --- |
| Focused backend billing/migration suite | PASS | 150 tests in the targeted run, including 33 real PostgreSQL integration cases |
| Latest backend edge-case regressions | PASS | 21 tests covering deletion lock, malformed billing data, expired reminder links and payment error codes |
| Entire backend suite after logging-isolation correction | FAIL | 1003 passed, 8 independently reproduced failures, 77 warnings in 47.33 seconds; no remaining AI/auth logging failures |
| Migration followed by AI/auth logging modules | PASS | 90 tests, including logging preservation after successful and rejected migrations |
| Earlier isolated rerun of failing modules | FAIL | 95 passed, 8 independently reproduced call/report failures |
| Migration-test Ruff and Black checks | PASS | Changed test passes lint and formatting checks |
| PDF/report regression suite | PASS | 67 tests |
| Frontend full suite after retry fixes | PASS | 56 files, 283 tests |
| Frontend focused retry/API tests | PASS | 22 tests |
| Frontend lint and TypeScript | PASS | Full lint and typecheck; final rerun recorded in handoff |
| Frontend production build | PASS | 42 static pages generated, including `/public/invoice`; local API URL override used |
| Scoped backend lint/type checks | PASS | Billing/subscription modules verified |
| Entire backend Ruff | FAIL | Four pre-existing findings, detailed below |
| Alembic head | PASS | Single head `e8f1a2b3c4d5` |
| Runtime dependency search | PASS | No Stripe/checkout-session/payment-intent references in backend/frontend runtime sources |
| Live Brevo/S3 delivery and actual worker transport | BLOCKED | Delivery providers substituted in integration tests |
| Browser UI E2E | BLOCKED | Browser skill discovered no connected browser |

Commands (from the relevant subdirectory):

```sh
# Backend: runner disables real dotenv files and inherited credentials.
.venv/bin/python -m app.tests.run_isolated_workflow --startup
.venv/bin/python -m app.tests.run_isolated_workflow -q
.venv/bin/ruff check app
REDIS_PORT=6379 .venv/bin/alembic heads

# Frontend
npm test
npm run lint
npx tsc --noEmit
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000/api/v1 npm run build
```

Sandboxed PDF/report tests stalled on socket restrictions; rerunning outside the
sandbox passed. The initial build likewise failed because Turbopack could not bind
its local worker port; the approved unsandboxed build passed. These were tooling
restrictions, not source-code build failures.

### Logging-isolation correction and remaining failures

The initial full run exposed seven logging assertion failures in AI/auth tests
after the new populated-history migration test. Loading `alembic.ini` caused
`alembic/env.py` to call `fileConfig`, changing process-wide logger state.
With user approval, the migration test now uses an in-memory Alembic configuration
with an explicit migration directory, bypassing CLI logging setup. It asserts that
root handlers and log capture survive the historical upgrade, rejected upgrade,
and successful manual-billing upgrade. Production logging and existing assertions
are unchanged. The migration test followed by the AI/auth modules passes: 90 tests.

The remaining eight failures also reproduce without the migration test:

- Two existing call-service tests have invalid mocks (`object()` has no `id`, and
  an unmocked function has no `assert_not_called`). Neither those source files nor
  their tests were changed by this implementation.
- Six scheduled-report tests expect email processing despite the deliberately
  absent Brevo key in the isolated runner. Their delivery setup mocks sending but
  does not configure the existing provider-availability guard. No real credentials
  should be added merely to make these tests pass.

The correction touches only the migration test and this report. The independently
reproduced call/report failures remain unchanged; no changes were reverted or discarded.

## 11. Runtime verification

Real PostgreSQL 15 ran in the disposable container `crm-manual-invoice-tests`,
bound only to `127.0.0.1:55439`, database `crm_workflow_test`. It remains available
for inspection/continued testing; no production database was used. Each workflow
test creates its own organization. Migration history tests use a private schema.

Verified against persisted records:

- Customer quote acceptance creates one Draft invoice, no payment, no invoice email
  job; concurrent quote acceptance does not duplicate it.
- Finalization validates review data and records actor/time. Draft sending and
  pre-acceptance payment creation are rejected.
- The invoice worker renders a real PDF and persists delivery bookkeeping. S3 upload,
  presigning and tracked email calls are substituted, so `Sent` in this test proves
  worker bookkeeping, not actual inbox delivery or storage access.
- Secure public HTTP view/accept succeeds; malformed/unknown/expired tokens fail.
  Repeated/concurrent acceptance records one event and no payment.
- `test_inr_10000_invoice_two_5000_bank_transfers` verifies an INR 10,000 invoice:
  first Bank Transfer 5,000 produces paid 5,000/outstanding 5,000/Partially Paid;
  second 5,000 produces paid 10,000/outstanding 0/Paid. Actual payment rows and
  financial report values are asserted.
- Concurrent identical requests create one payment; competing overpayments cannot
  exceed the invoice total. Reused keys with different payloads, foreign tenants
  and unauthorized requests are rejected.
- Populated migration preserves invoice/payment numbers, amounts, historical dates,
  original provider evidence and paid status, while leaving acceptance timestamps
  empty. Inconsistent paid balance aborts before destructive schema changes.
- A fresh process blocks imports of the gateway SDK, omits gateway configuration,
  starts the real application lifespan and receives HTTP 200 from `/health` with
  database status `ok`.

Browser skill discovery returned no available browser. Actual browser interaction,
live email/storage, and Celery broker transport were not verified. No real online
payment or simulated gateway success was used.

## 12. Remaining issues

- Production cutover, credentials cleanup and live Brevo/S3/Celery delivery still
  require controlled deployment verification; no customer emails have been sent.
- Browser-based verification requires a connected browser.
- The eight independently reproduced call/report test failures need a separate
  decision on fixing their test setup; they are not silently classified as passed.
- Full repository Ruff currently reports four pre-existing findings: one B904 in
  `call_service.py` and three unused imports in `quote_service.py`. These were
  present in HEAD and are not caused by manual billing changes.

## 13. Final verdict

PARTIALLY COMPLETE

The manual billing implementation passes controlled database/API workflow tests,
but the complete test suite is not green, and live delivery/browser verification
has not been established. Remaining test-setup failures and controlled deployment
verification must be resolved before claiming completion.
