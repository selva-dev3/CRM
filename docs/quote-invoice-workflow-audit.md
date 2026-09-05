# Quote → Invoice Workflow Audit

Audited the current repository at commit `66fe2cb` on branch `feature/crm-reports-workflow-integration`. This report is based on repository evidence. No application files were modified for the audit.

## Overall verdict

The quote-to-payment workflow is substantially implemented and connected, but it is **PARTIALLY IMPLEMENTED** for production use.

The core path exists:

```text
Deal Closed Won
    ↓
Automatic Quote
    ↓
Quote Items
    ↓
Internal Approval
    ↓
Approved
    ↓
PDF
    ↓
Secure Customer Link
    ↓
Customer Email
    ↓
Customer View
    ↓
Customer Accept
    ↓
Automatic Invoice
    ↓
Invoice Items
    ↓
Invoice Email
    ↓
Stripe Checkout
    ↓
Stripe Webhook
    ↓
Payment
    ↓
Invoice Paid
    ↓
Reports
```

## Deal Won

**Status: ✅ Working**

`POST /deals/{deal_id}/win` calls `DealService.mark_deal_won()`.

The backend:

- Locks the deal.
- Verifies organization ownership.
- Requires a linked company and contact.
- Verifies the company, contact, and contact-company relationship.
- Requires deal products.
- Validates products against the organization.
- Calculates totals server-side.
- Sets the stage to `Closed Won`.
- Creates a deal activity.
- Creates the automatic quote in the same transaction.
- Returns the generated `quote_id`.

Relevant files:

- [deal_service.py](../backend/app/services/deal_service.py)
- [deals.py](../backend/app/api/v1/routers/deals.py)
- [deals/[id]/page.tsx](../frontend/src/app/(dashboard)/deals/[id]/page.tsx)

`final_amount` is accepted by the endpoint but is not authoritative. The amount is recalculated from persisted deal products.

## Automatic Quote Creation

**Status: ✅ Fully implemented**

`DealService._apply_won()` directly calls `quote_service.create_from_won_deal()`.

The quote is created synchronously within the deal transaction. There is no separate event bus or outbox required for this step.

Automatic quote creation is idempotent because `quotes.automatic_deal_id` is unique and the service checks for an existing quote first.

Relevant files:

- [deal_service.py](../backend/app/services/deal_service.py)
- [quote_service.py](../backend/app/services/quote_service.py)
- [quote.py](../backend/app/models/quote.py)
- [automatic_deal_quotes migration](../backend/alembic/versions/c3d4e5f6a7b8_automatic_deal_quotes.py)

## Quote and Quote Items

**Status: ✅ Fully implemented**

The quote stores organization, deal, automatic deal, company, contact, quote number, currency, total, status, approval fields, delivery fields, acceptance fields, expiry, public token hash, and PDF storage key.

Quote items store:

- Product ID
- Product name snapshot
- Quantity
- Unit price
- Discount percentage
- Tax percentage
- Subtotal
- Discount total
- Tax total
- Total

Deal products are copied into quote items by `create_from_won_deal()`. Totals are calculated by the backend using `calculate_line()`.

Frontend values do not determine the final quote total.

## Quote Review

**Status: ⚠️ Partial**

The quote detail page exists at [quotes/[id]/page.tsx](../frontend/src/app/(dashboard)/quotes/[id]/page.tsx).

It displays quote number, status, items, quantity, unit price, discounts, taxes, line totals, total, delivery state, PDF availability, and invoice reference.

The review is incomplete because the API/UI does not expose all expected company, contact, payment-term, and due-date information. The quote model has no dedicated payment-terms field.

## Internal Approval

**Status: ✅ Implemented separately from customer acceptance**

Approval endpoint:

```text
POST /api/v1/quotes/{quote_id}/approve
```

Required permission:

```text
quotes:approve
```

Approval stores `approved_at`, `approved_by`, `status = "Approved"`, and quote expiry. It validates items, currency, totals, company, contact, and contact email.

Customer acceptance uses separate public token endpoints. Approval is not the same action as acceptance.

The exact business role with `quotes:approve` is data-driven through RBAC records. The code enforces the permission key rather than hardcoding Sales Manager or Finance.

## Quote State Machine

| Current Status | Next Status | Actor | API or Trigger | Permission | Exists |
|---|---|---|---|---|---|
| Draft | Pending Approval | Internal user | Quote update | `quotes:update` | ✅ |
| Draft | Approved | Internal approver | `/quotes/{id}/approve` | `quotes:approve` | ✅ |
| Pending Approval | Approved | Internal approver | `/quotes/{id}/approve` | `quotes:approve` | ✅ |
| Approved | Sent | Delivery worker | Celery delivery task | None | ✅ |
| Sent | Accepted | Customer | Public accept endpoint | Secure token | ✅ |
| Sent | Rejected | Customer | Public reject endpoint | Secure token | ✅ |
| Accepted | Invoice created | Backend | Acceptance transaction | None | ✅ |
| Approved | Failed/Unknown | Delivery worker | Delivery result | None | ✅ |

The lifecycle is represented by strings rather than a database enum or complete database transition constraint.

## Quote PDF

**Status: ✅ Real asynchronous generation**

Relevant files:

- [quote_pdf_service.py](../backend/app/services/quote_pdf_service.py)
- [quote_delivery_service.py](../backend/app/services/quote_delivery_service.py)
- [s3_service.py](../backend/app/services/s3_service.py)

The delivery worker loads the persisted quote and items, renders a ReportLab PDF, uploads it to MinIO/S3, creates a presigned URL, stores the object key, and includes the URL in the email.

The PDF includes organization text, customer information, quote number, currency, expiry, line items, discounts, taxes, subtotals, and total.

Organization branding is limited to text fields; logo branding is not evidenced.

## Secure Customer Link

**Status: ✅ Implemented**

The acceptance token is generated with HMAC using the application secret and the quote/delivery identifiers. Only a SHA-256 token hash is stored.

Public endpoints:

- `POST /api/v1/public/quotes/view`
- `POST /api/v1/public/quotes/accept`
- `POST /api/v1/public/quotes/reject`
- `POST /api/v1/public/quotes/checkout`

The public quote page does not require CRM authentication. The backend validates the token, quote approval, send state, expiry, status, and organization-scoped customer records.

## Quote Email

**Status: ✅ Real provider integration**

The delivery worker calls `send_tracked_email()` in [email_service.py](../backend/app/services/email_service.py), which submits through Brevo at `https://api.brevo.com/v3/smtp/email`.

The recipient is the linked Deal Contact email. The manual send endpoint accepts an email input but validates it against the linked contact email.

The message includes the quote number, amount, expiry, secure acceptance link, and quote PDF URL. Delivery status and provider message ID are persisted.

Provider acceptance confirms submission to Brevo, not final inbox delivery.

## Customer Acceptance

**Status: ✅ Implemented**

The customer page at [public/quote/page.tsx](../frontend/src/app/public/quote/page.tsx) allows the customer to view, accept, reject, refresh, and pay after invoice creation.

The backend rejects invalid, expired, unapproved, unsent, or invalid-customer links. Acceptance stores `accepted_at`, `accepted_by`, and `status = "Accepted"`.

`accepted_by` is stored as an email string rather than a structured customer identity.

## Automatic Invoice Creation

**Status: ✅ Fully implemented**

`QuoteService.accept_public_quote()` calls `InvoiceService.create_from_accepted_quote()` in the same transaction.

Invoice creation validates approval, acceptance, Closed Won deal state, customer relationships, billing address, quote items, quote totals, and organization invoice configuration.

The invoice is linked to the quote, deal, company, contact, and organization.

Duplicate invoices are prevented by existing-record checks and database constraints for one invoice per quote and one invoice per deal.

## Invoice Items

**Status: ✅ Fully implemented**

Quote items are copied into invoice items as historical snapshots. Totals are recalculated server-side from the quote item values, so later product-price changes do not rewrite the invoice.

## Invoice Email

**Status: ✅ Implemented asynchronously**

Invoice creation queues delivery. The invoice worker creates a Stripe Checkout session, renders an invoice PDF, uploads it to S3/MinIO, generates a presigned URL, and sends the email through Brevo.

The recipient comes from the invoice billing snapshot created from the linked contact.

Relevant files:

- [invoice_delivery_service.py](../backend/app/services/invoice_delivery_service.py)
- [invoice_pdf_service.py](../backend/app/services/invoice_pdf_service.py)
- [workers/tasks.py](../backend/app/workers/tasks.py)

## Stripe Checkout

**Status: ✅ Real integration**

[invoice_payment_service.py](../backend/app/services/invoice_payment_service.py) uses the configured Stripe secret key and creates real Checkout Sessions.

Checkout metadata includes invoice ID and organization ID. Amount and currency are calculated from the persisted invoice. Checkout creation uses an idempotency key.

## Stripe Webhook and Payment

**Status: ✅ Implemented**

Webhook endpoint:

```text
POST /api/v1/payments/webhooks/stripe
```

The webhook verifies the Stripe signature and validates event type, payment status, invoice ID, organization ID, currency, amount, and payment intent.

It persists a `Payment` record and marks the invoice `Paid`.

Duplicate handling uses provider event ID, provider payment ID, checkout session ID, existing payment lookup, and one payment per invoice.

Manual mark-paid is disabled for generated invoices.

## Reports

**Status: ✅ Connected to persisted financial data**

The financial overview uses:

- Deals for pipeline and booked value
- Quotes for quoted and accepted quote value
- Invoices for invoiced, paid, outstanding, and overdue values
- Verified payment records for collected revenue

Collected revenue is based on `Payment.status == "Succeeded"`, not merely `Deal.amount`.

## End-to-End Connection Matrix

| Step | Frontend | API | Backend/DB | Automation/Provider | Status |
|---|---|---|---|---|---|
| Deal Won | Deal detail page | `/deals/{id}/win` | Deal locked and persisted | Synchronous | ✅ |
| Automatic Quote | Quote reference | Internal service call | Quote inserted | Same transaction | ✅ |
| Quote Items | Quote detail | Quote GET | Snapshot items persisted | Same transaction | ✅ |
| Review | Quote detail page | Quote GET | Scoped quote read | None | ⚠️ |
| Approval | Approve button | `/quotes/{id}/approve` | Approval fields stored | Delivery queued | ✅ |
| PDF | Download link | Quote PDF endpoint | S3 key stored | Celery + ReportLab | ✅ |
| Secure Link | Public quote page | Public quote endpoints | Token hash stored | HMAC | ✅ |
| Quote Email | Delivery state | Queue endpoint | Delivery state stored | Celery + Brevo | ✅ |
| Customer View | `/public/quote` | Public view endpoint | Token-scoped read | None | ✅ |
| Customer Accept | Accept button | Public accept endpoint | Quote accepted | Same transaction | ✅ |
| Automatic Invoice | Invoice reference | Internal service call | Invoice inserted | Same transaction | ✅ |
| Invoice Items | Invoice detail | Invoice GET | Historical snapshots | Same transaction | ✅ |
| Invoice Email | Delivery state | Invoice delivery | Delivery state stored | Celery + Brevo | ✅ |
| Stripe Checkout | Pay button | Checkout endpoint | Session stored | Stripe | ✅ |
| Stripe Webhook | None | Webhook endpoint | Payment persisted | Stripe | ✅ |
| Payment | Customer status | Webhook result | Payment record | Stripe | ✅ |
| Invoice Paid | Invoice status | Webhook result | Invoice marked Paid | Webhook | ✅ |
| Reports | Reports page | Report APIs | Aggregated queries | None | ✅ |

## Role-Wise Verification

The backend checks permission keys rather than hardcoded role names.

| Action | Sales Executive | Sales Manager | Admin | Finance | Customer |
|---|---|---|---|---|---|
| Create Deal | Permission-dependent | Permission-dependent | Permission-dependent | Permission-dependent | ❌ |
| Mark Won | `deals:update` | `deals:update` | `deals:update` | Permission-dependent | ❌ |
| Review Quote | `quotes:read` | `quotes:read` | `quotes:read` | `quotes:read` | Public after send |
| Approve Quote | `quotes:approve` required | `quotes:approve` required | `quotes:approve` required | `quotes:approve` required | ❌ |
| Send Quote | `quotes:send` required | `quotes:send` required | `quotes:send` required | `quotes:send` required | ❌ |
| View Customer Quote | ❌ | ❌ | ❌ | ❌ | Secure token |
| Accept Quote | ❌ | ❌ | ❌ | ❌ | Secure token |
| Create Invoice | Permission-dependent | Permission-dependent | Permission-dependent | Permission-dependent | Automatic after acceptance |
| Pay Invoice | ❌ | ❌ | ❌ | ❌ | Stripe Checkout |
| Mark Paid | Disabled for generated invoices | Disabled | Disabled | Disabled | ❌ |

The exact non-admin role assignment for `quotes:approve` is stored in RBAC data and cannot be proven from the endpoint code alone.

## Database Relationship Audit

```text
Organization
  └── Deal
        └── Quote
              └── QuoteItem
              └── Invoice
                    └── InvoiceItem
                    └── Payment
```

Important constraints:

- One automatic quote per deal.
- One invoice per quote and per deal.
- One payment per invoice.
- Unique payment provider/payment ID.
- Unique Stripe checkout session.
- Unique public quote token hash.
- Quote and invoice item cascade behavior.
- Organization IDs on quote, invoice, and payment records.

Some upstream links use `SET NULL`, so historical invoices can survive without their original quote or deal link.

## Tenant Security

**Status: ⚠️ Mostly implemented**

The quote, invoice, payment, and public acceptance paths use organization-scoped lookups and validate company/contact relationships.

Risks remain in adjacent product and legacy endpoints where organization scoping is inconsistent. The public acceptance token is bearer access: anyone possessing a valid unexpired token can access that quote.

## Idempotency

**Status: ✅ Mostly implemented**

Idempotency is provided by:

- Unique automatic quote per deal.
- Locked deal and existing quote lookup.
- Existing invoice lookup.
- Unique invoice quote/deal constraints.
- Stripe checkout idempotency keys.
- Existing payment and webhook event checks.
- Delivery IDs and provider idempotency keys.
- Worker claim/recovery logic.

Completion still depends on Celery workers and external-provider reconciliation.

## Existing Tests

Relevant tests cover:

- Deal Won
- Automatic quote creation
- Quote items and totals
- Concurrent quote creation
- Public acceptance
- Automatic invoice creation
- Duplicate acceptance
- Tenant isolation
- Quote PDF rendering
- Invoice PDF rendering
- Invoice delivery
- Stripe Checkout
- Stripe webhook verification
- Reports
- Frontend quote and public quote pages

Provider tests mock Brevo, S3, and Stripe. They verify provider invocation and state transitions, but do not prove that production worker processes, credentials, webhooks, or external accounts are configured correctly.

## Critical Issues

- Quote review lacks complete company, contact, payment-term, and due-date presentation.
- Organization scoping is inconsistent in some product endpoints.
- `Sent` means provider submission, not inbox delivery.
- Celery worker and Beat deployment are required for delivery.
- Production provider configuration cannot be verified from source alone.
- `accepted_by` is stored as an email string rather than a structured customer identity.
- Quote and invoice lifecycle values are strings without complete database transition constraints.

## Missing Components

- Dedicated quote payment-term and customer-facing due-date fields.
- Complete customer/company data in the quote review API/UI.
- Database-enforced quote transition state machine.
- Static proof of role assignments for `quotes:approve`.
- Real staging end-to-end provider test.
- Operational monitoring for failed and unknown deliveries.

## Existing Working Components

- Closed Won validation.
- Automatic quote creation.
- Deal product snapshots.
- Server-side totals.
- Separate internal approval and customer acceptance.
- HMAC-secured public quote link.
- Public customer quote page.
- Customer accept/reject flow.
- Automatic invoice creation.
- Historical invoice snapshots.
- Real PDF generation.
- MinIO/S3 storage.
- Brevo email submission.
- Stripe Checkout.
- Signed Stripe webhook verification.
- Persisted payments.
- Verified payment-based collected revenue.
- Duplicate prevention.

## Placeholder/Fake Components

The core quote-to-payment components are real. Unrelated placeholders include:

- Quote CSV import/export.
- Invoice CSV import/export.
- Recurring invoice schedules.
- Other CRM export/import endpoints.

These do not block the quote-to-payment workflow itself.

## Security Issues

- Some product endpoints are not consistently organization-scoped.
- Public quote access is bearer-token access until expiry.
- Production provider configuration could not be verified from source.
- Payment webhook signature verification is implemented.
- Provider secrets are read from settings rather than hardcoded.

## Data Integrity Issues

- Quote and invoice totals are recalculated server-side.
- Historical item snapshots preserve prices.
- Quote, invoice, and payment uniqueness constraints exist.
- Some links use `SET NULL`, preserving invoices without upstream references.
- Status values are strings without complete database transition constraints.
- Both `Invoice.paid_amount` and `Payment.amount` are persisted and must remain synchronized through webhook logic.

## Recommended Implementation Order

1. Complete organization scoping for every product endpoint.
2. Expand quote review with company, contact, terms, and due-date data.
3. Document and verify production RBAC assignments for `quotes:approve`.
4. Add database constraints or a centralized quote transition validator.
5. Verify Celery worker and Beat deployment.
6. Verify Brevo, MinIO/S3, Stripe, and webhook configuration.
7. Add a staging end-to-end test using provider sandbox environments.
8. Add monitoring for failed and unknown quote, invoice, and receipt deliveries.
