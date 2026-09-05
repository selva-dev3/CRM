# Automated CRM workflow — implementation checkpoint

Status: IN PROGRESS — not ready to merge or deploy as a complete production workflow.

Worktree: `/tmp/crm-automated-sales-workflow`
Branch: `feat/automated-crm-sales-workflow`
The workflow and organization build fix were committed separately and pushed with user approval (`f0933f3` and `6567f9f`). This document records the remaining verification gaps for review. No production migration or production provider request has been performed.

## Implemented and locally verified

- Real qualified-lead conversion persists company/contact/deal links in one transaction. Concurrent conversion returns the same records.
- Deal product upserts persist price/name/discount/tax snapshots. Decimal calculations normalize to the stored precision.
- Closed Won automation creates one persisted Draft quote and its items in the deal transaction. Missing products roll back the stage change.
- Internal quote approval is separate from customer acceptance.
- Quote sending queues durable work in the existing Celery architecture. The worker generates an actual PDF, uploads through existing storage, and calls the existing Brevo provider.
- Sent is recorded only with a provider receipt; it does not mean inbox delivery. Storage failure is Failed; uncertain email outcomes are Unknown and cannot be blindly resent. Attempts are bounded.
- Public capability endpoints validate a hashed, expiring quote token, expose the quote, accept/reject it, and initiate checkout for its invoice.
- Acceptance and invoice/item creation are atomic. Repeated/concurrent acceptance returns one invoice protected by a database uniqueness constraint.
- Organization-specific invoice numbering uses a locked organization sequence.
- Invoice items copy quote snapshots, not current catalog prices.
- Stripe Checkout uses the SDK and database amount, currency and identity. Only the provider's returned URL is used.
- Signed Stripe webhook processing validates session identity, tenant metadata, amount, currency and payment status before recording a Payment and marking Paid.
- Duplicate signed webhook events produce one Payment. Invoice/payment audit records and same-organization staff notifications are persisted.
- Ordinary manual mark-paid is disabled. Generated and Paid invoices cannot use the general edit/delete paths.
- Staff quote UI uses Approve, reports actual delivery state, and links to the generated invoice. Public customer UI accepts/rejects, starts checkout, and refreshes actual payment state.
- Fake quote PDF URLs, fabricated invoice conversions and fabricated revision records were removed from the quote service. Unsupported revision creation returns an error.

Provider calls in the tests are mocked. These checks do NOT establish actual email delivery, storage access or a real Stripe test payment.

## Database changes

All five migrations upgraded successfully against a dedicated local PostgreSQL 18 test database:

1. `b2c3d4e5f6a7`: lead conversion references and timestamp; follows existing `b2c3d4e5f6a8`.
2. `c3d4e5f6a7b8`: quote/deal-product snapshots, Decimal document money, automatic-deal quote uniqueness, product foreign keys.
3. `d4e5f6a7b8c9`: approval/acceptance capability fields, invoice billing snapshot, organization invoice sequence, unique organization/quote and organization/number.
4. `e5f6a7b8c9d1`: Stripe session identity/generation and Payment records with payment/session uniqueness.
5. `f6a7b8c9d1e2`: durable quote delivery state/claims, provider receipt, storage identity and rejection timestamp.

Migration downgrade and representative legacy-data upgrade tests remain outstanding. Legacy orphan product references can make the new FK migration fail safely; no automatic destructive cleanup was added. Payment-table downgrade refuses to destroy existing payment evidence.

## Verification results

- Combined focused backend unit, router, HTTP-contract and PostgreSQL integration suite: **177 passed**, 25 warnings.
- Real database checks include concurrent conversion, concurrent win, concurrent acceptance, competing delivery workers, concurrent signed webhooks, same-organization checks, rollback, missing billing data, invalid signatures and payment mismatches.
- Public quote HTTP tests validate 422 malformed requests, 404 invalid tokens, 403 missing approval permission, cross-organization 404, and replayed acceptance responses.
- Actual quote PDF generated, rendered with Poppler, and visually inspected. Subtotal, discount, tax and total are present. This is a QA fixture document, not a customer document.
- Ruff on every changed/new Python file: passed.
- Targeted frontend ESLint: passed.
- Selected frontend run: **24 passed, 1 failed**. The four new customer-page tests and new cookie-omission/no-auth-refresh test pass.
- Existing API-client tests disagree with existing URL configuration: without an environment override the local fallback omits `/api/v1`; with an override a separate test expecting missing production configuration fails. No unrelated default-URL change was made.
- Organization-page build blocker fixed with user approval: the existing reusable component moved to `components/features/organization/OrganizationDetail.tsx`, and the by-ID route now exports a prop-free wrapper. Current-organization and by-ID behavior are preserved.
- Organization tests: **20 passed** across four files, including both organization detail modes. Targeted ESLint and `tsc --noEmit --incremental false` passed.
- Production webpack build: **passed**, including Next page-contract type checks and all 38 static pages. Verified with a non-secret local API URL supplied to the build command; no environment file was changed.
- Browser discovery returned no available browser. Browser E2E has NOT run.
- Full repository backend/frontend suites have NOT run. This checkpoint reports focused tests, not an all-tests-pass result.
- `git diff --check`: passed.

The local database and test dependencies are isolated under /tmp; no deployed database or provider credentials were used. Local Python is 3.14; production Python 3.11 compatibility must also be checked.

## Remaining implementation and security work

These are not merely external-verification blockers:

1. Complete atomic organization initialization, default roles/settings, tax/billing configuration, and onboarding verification. Registration was inspected but has not been changed.
2. Finish the wider tenant audit. Several legacy lead/deal CRUD/assignment/read paths still use unscoped lookups. New transaction paths are scoped, but this is not proof of whole-CRM isolation.
3. Harden general deal edits and state transitions around generated quotes. Mixed edits plus Closed Won are explicitly rejected instead of silently dropping fields; other legacy edit/assignment paths still need review.
4. Update legacy deal product display to use snapshots consistently, including zero-price handling; remove remaining manual invoice controls from deal pages.
5. Complete legacy invoice PDF, email, reminder and credit-memo flows or explicitly disable their success-only placeholders. Those old routes are not yet migrated to real delivery.
6. Complete financial lifecycle/immutability coverage across all alternative endpoints, billing snapshots and historical records. Deal header amount still uses its legacy Float column.
7. Add customer payment-confirmation delivery and recoverable provider reconciliation tooling. CRM notifications are not email delivery confirmation.
8. Restore/verify external deal-won integrations through a safe durable dispatch path; the new transactional quote notification is not a verified replacement for Slack delivery.
9. Add full organization-to-payment happy-path coverage, all permission/tenant negative cases, and complete browser acceptance/payment flow.
10. Run migration downgrade/legacy-data checks, complete suites and production Python checks.

Additional operational limitations:

- Checkout currently explicitly supports reviewed two-decimal currencies: INR, USD, EUR, GBP, CAD, AUD and SGD. Other minor-unit rules are rejected, not guessed.
- Quote validity currently defaults to 30 days, and quote numbers use unique document identifiers rather than an organization-configurable sequence.
- Capability expiry also limits public payment access; renewal/revocation/reissue UX needs completion.
- A quote email receipt does not prove customer identity beyond possession of the secure email capability. Stronger identity requirements need an explicit business decision.
- Email claims with uncertain provider outcomes deliberately stop in Unknown. Reconciliation is required; automatic retry would risk duplicate delivery.
- The current PDF needs broader multi-page/unicode and document-terms testing.
- Quote delivery requires both the existing Celery worker and beat scheduler. The new task is explicitly included in worker imports.

## External verification requirements

Use isolated test-provider configuration supplied through an approved runtime/secret manager; never paste secrets into chat or commit them.

Required runtime settings use the existing names:
`BREVO_API_KEY`, sender settings, storage endpoint/bucket/access settings, `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `FRONTEND_URL`, database and Celery settings.

The public customer page is `/public/quote`; its capability is carried in the URL fragment and POST body, not in request query strings. Public API requests omit internal CRM cookies and do not trigger authentication refresh.

No secret or .env file was edited. Live provider configuration and an approved test email recipient have been requested but are not yet available.

## Remaining external verification

The organization-page build fix was approved and verified. Browser/provider access is still required for the requested final E2E verification. The remaining implementation work listed above is unchanged; a successful build is not proof of a complete sales-to-payment workflow.

## Changed and created files

- `frontend/src/components/features/organization/OrganizationDetail.tsx` (existing component moved out of a route)
- `frontend/src/app/(dashboard)/organization/[id]/page.tsx` (route wrapper)
- `frontend/src/app/(dashboard)/organization/[id]/page.test.tsx`
- `frontend/src/app/(dashboard)/organization/page.tsx` (shared-component import)

- `backend/alembic/versions/b2c3d4e5f6a7_lead_conversion_links.py`
- `backend/alembic/versions/c3d4e5f6a7b8_automatic_deal_quotes.py`
- `backend/alembic/versions/d4e5f6a7b8c9_quote_acceptance_invoices.py`
- `backend/alembic/versions/e5f6a7b8c9d1_verified_invoice_payments.py`
- `backend/alembic/versions/f6a7b8c9d1e2_quote_delivery_state.py`
- `backend/app/api/v1/api.py`
- `backend/app/api/v1/routers/deals.py`
- `backend/app/api/v1/routers/invoices.py`
- `backend/app/api/v1/routers/leads.py`
- `backend/app/api/v1/routers/payment_webhooks.py`
- `backend/app/api/v1/routers/public_quotes.py`
- `backend/app/api/v1/routers/quotes.py`
- `backend/app/models/__init__.py`
- `backend/app/models/deal.py`
- `backend/app/models/invoice.py`
- `backend/app/models/lead.py`
- `backend/app/models/organization.py`
- `backend/app/models/payment.py`
- `backend/app/models/quote.py`
- `backend/app/repositories/deal_repository.py`
- `backend/app/repositories/invoice_repository.py`
- `backend/app/repositories/lead_repository.py`
- `backend/app/repositories/notification_repository.py`
- `backend/app/repositories/payment_repository.py`
- `backend/app/repositories/quote_repository.py`
- `backend/app/schemas/crm_schemas.py`
- `backend/app/services/deal_service.py`
- `backend/app/services/email_service.py`
- `backend/app/services/invoice_payment_service.py`
- `backend/app/services/invoice_service.py`
- `backend/app/services/lead_service.py`
- `backend/app/services/quote_delivery_service.py`
- `backend/app/services/quote_pdf_service.py`
- `backend/app/services/quote_service.py`
- `backend/app/services/sales_totals.py`
- `backend/app/tests/integration/test_sales_quote_workflow.py`
- `backend/app/tests/unit/test_deal_service.py`
- `backend/app/tests/unit/test_invoice_payment_service.py`
- `backend/app/tests/unit/test_invoice_service.py`
- `backend/app/tests/unit/test_lead_conversion.py`
- `backend/app/tests/unit/test_quote_pdf_service.py`
- `backend/app/tests/unit/test_quote_service.py`
- `backend/app/tests/unit/test_sales_totals.py`
- `backend/app/workers/celery_app.py`
- `backend/app/workers/tasks.py`
- `backend/requirements.txt`
- `frontend/src/app/(dashboard)/deals/[id]/page.tsx`
- `frontend/src/app/(dashboard)/leads/[id]/page.tsx`
- `frontend/src/app/(dashboard)/quotes/[id]/page.tsx`
- `frontend/src/app/public/quote/page.test.tsx`
- `frontend/src/app/public/quote/page.tsx`
- `frontend/src/lib/api/client.test.ts`
- `frontend/src/lib/api/client.ts`
- `frontend/src/lib/api/deals.ts`
- `frontend/src/lib/api/leads.ts`
- `frontend/src/lib/api/quotes.ts`
- `docs/CRM_AUTOMATED_WORKFLOW_IMPLEMENTATION.md` (this checkpoint)

## Verdict

Partial implementation with verified transactional core paths; NOT production-ready and NOT complete against the requested acceptance checklist. Do not merge on the basis of the focused test count alone.
