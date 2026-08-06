# Enterprise CRM - Subscription Module Roadmap

## Phase 1 - Database

### Step 1 - Create Models

Create the following models:

- SubscriptionPlan
- OrganizationSubscription

---

### Step 2 - Generate Migration

```bash
docker compose exec backend alembic revision --autogenerate -m "add subscription tables"
```

Review the generated migration file carefully.

Then run:

```bash
docker compose exec backend alembic upgrade head
```

---

## Phase 2 - Seed Default Plans

Seed the `subscription_plans` table with the default plans.

### Plans

| Plan | Monthly Price |
|------|---------------|
| Free | ₹0 |
| Starter | ₹999 |
| Professional | ₹2999 |
| Business | ₹6999 |
| Enterprise | Custom |

---

## Phase 3 - Organization Creation Flow

Whenever a new organization is created, automatically create:

- Organization
- Organization Settings
- Organization Subscription

### Flow

```
Organization
        │
        ▼
Organization Settings
        │
        ▼
Organization Subscription
```

Default values:

```text
Plan            : Free
Status          : Active
Billing Cycle   : Monthly
```

---

## Phase 4 - Subscription APIs

### Subscription Plans

```
GET /subscription-plans
GET /subscription-plans/{id}
```

---

### Organization Subscription

```
GET /organizations/{id}/subscription

PUT /organizations/{id}/subscription

POST /organizations/{id}/upgrade

POST /organizations/{id}/downgrade
```

---

## Phase 5 - Frontend

### Organization Page

```
Organization

├── General
├── Members
├── Billing & Subscription
└── API Keys
```

---

### Billing & Subscription Card

Display:

```
Current Plan

Status

Price

Billing Cycle

Next Billing Date

Storage Usage

Users

AI Credits

Upgrade Plan Button
```

Example:

```
Enterprise

Status
Active

Billing
Monthly

Price
₹299/month

Users
18 / Unlimited

Storage
126 GB / 5 TB

AI Credits
Unlimited

Support
Premium

Next Billing
02 Sep 2026
```

---

## Phase 6 - Feature Guard

Restrict features based on subscription plan.

### Free

```
AI                  ❌
Invoices            ❌
Custom Roles        ❌
API Access          ❌
Workflow            ❌
Automation          ❌
```

---

### Starter

```
Leads               ✔
Contacts            ✔
Companies           ✔
Tasks               ✔
Basic Reports       ✔
```

---

### Professional

```
Everything in Starter

Deals               ✔
Invoices            ✔
Reports             ✔
Automation          ✔
AI Email Writer     ✔
```

---

### Business

```
Everything in Professional

Advanced Reports    ✔
Forecasting         ✔
Integrations        ✔
Workflow            ✔
Audit Logs          ✔
```

---

### Enterprise

```
Everything

Unlimited Users

Unlimited AI

Unlimited Storage

Custom Roles

SSO

White Label

Priority Support

API Access

Advanced Security
```

---

## Phase 7 - Payment Integration (Later)

Integrate payment providers:

- Stripe
- Razorpay
- PayPal

Features:

- Subscription Renewal
- Upgrade
- Downgrade
- Cancel Subscription
- Payment History
- Invoice History
- Webhooks

---

# Implementation Order

```text
✅ SubscriptionPlan Model

✅ OrganizationSubscription Model

⬜ Alembic Migration

⬜ Seed Default Subscription Plans

⬜ Auto Create Subscription When Organization Is Created

⬜ Subscription APIs

⬜ Billing & Subscription UI

⬜ Upgrade / Downgrade APIs

⬜ Feature Guard

⬜ Stripe / Razorpay Integration

⬜ Invoice Management

⬜ Payment History
```

---

# Current Task

Complete the following in order:

1. Create Migration
2. Run Migration
3. Seed Default Subscription Plans
4. Auto-create Subscription when Organization is created
5. Build Subscription APIs
6. Build Billing & Subscription UI
7. Implement Feature Restrictions
8. Integrate Payment Gateway

This implementation order provides a scalable, production-ready subscription architecture for an Enterprise Multi-Tenant CRM.