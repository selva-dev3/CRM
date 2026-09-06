"""Organization Stripe subscriptions; only signed webhooks grant paid entitlements."""

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import urlencode

from sqlalchemy.exc import MultipleResultsFound
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import APIException, ConflictError, ForbiddenError, NotFoundError
from app.models import Organization, OrganizationSubscription, User
from app.repositories.organization_repository import OrganizationRepository
from app.services.subscription_stripe_provider import SCOPE, SubscriptionStripeProvider


def _id(value: Any) -> str | None:
    return (
        value if isinstance(value, str) else value.get("id") if isinstance(value, Mapping) else None
    )


def _time(value: Any) -> datetime | None:
    return datetime.fromtimestamp(value, UTC) if isinstance(value, (int, float)) else None


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


def _invoice_subscription(invoice: Mapping) -> str | None:
    return _id(invoice.get("subscription")) or _id(
        ((invoice.get("parent") or {}).get("subscription_details") or {}).get("subscription")
    )


@dataclass(frozen=True)
class BillingPlan:
    slug: str
    name: str
    amount: Decimal
    currency: str
    billing_cycle: str
    plan_id: str | None
    max_users: int
    storage: int
    ai_credits: int

    @property
    def amount_minor(self) -> int:
        return int(self.amount * 100)


class SubscriptionBillingService:
    def __init__(
        self,
        repository: OrganizationRepository | None = None,
        provider: SubscriptionStripeProvider | None = None,
    ) -> None:
        self.repository = repository or OrganizationRepository()
        self.provider = provider or SubscriptionStripeProvider()

    def _tenant(self, current_user: User, org_id: str | None = None) -> str:
        tenant = getattr(current_user, "organization_id", None)
        if not tenant or (org_id is not None and org_id != tenant):
            raise ForbiddenError(message="Subscription billing is restricted to your organization")
        return tenant

    async def _plan(self, db: AsyncSession, slug: str) -> BillingPlan:
        row = await self.repository.get_plan_by_slug(db, slug)
        if not row:
            raise APIException(message="Unknown subscription plan", code="UNKNOWN_PLAN")
        if not row.is_active:
            raise APIException(message="Subscription plan is unavailable")
        try:
            amount = Decimal(str(row.price_monthly))
        except InvalidOperation as exc:
            raise APIException(message="Subscription plan price is invalid") from exc
        if (
            not amount.is_finite()
            or amount <= 0
            or amount * 100 != (amount * 100).to_integral_value()
        ):
            raise APIException(message="Checkout requires a valid paid monthly plan")
        currency = row.currency.strip().lower()
        billing_cycle = row.billing_cycle.strip().lower()
        if len(currency) != 3 or not currency.isalpha() or billing_cycle != "month":
            raise APIException(message="Subscription plan billing terms are invalid")
        return BillingPlan(
            row.slug,
            row.name,
            amount,
            currency,
            billing_cycle,
            row.id,
            row.max_users,
            row.max_storage_gb,
            row.ai_credits,
        )

    async def _locked(
        self, db: AsyncSession, org_id: str
    ) -> tuple[Organization, OrganizationSubscription | None]:
        org = await self.repository.get_by_id_for_update(db, org_id)
        if not org or not org.is_active:
            raise NotFoundError(message="Organization not found")
        try:
            sub = await self.repository.get_subscription(db, org_id)
        except MultipleResultsFound as exc:
            raise ConflictError(
                message="Subscription records require administrator reconciliation",
                code="SUBSCRIPTION_DATA_INTEGRITY_ERROR",
            ) from exc
        if sub:
            await db.refresh(sub, with_for_update=True)
        return org, sub

    async def _retrieve_subscription(self, subscription_id: str) -> dict:
        try:
            return await self.provider.retrieve_subscription(subscription_id)
        except APIException as exc:
            fields = exc.fields or {}
            if (
                exc.code == "SUBSCRIPTION_PROVIDER_ERROR"
                and fields.get("provider_code") == "resource_missing"
            ):
                raise ConflictError(
                    message="The stored Stripe subscription was not found; administrator reconciliation is required",
                    code="SUBSCRIPTION_RECONCILIATION_REQUIRED",
                    fields={
                        "provider_request_id": fields.get("provider_request_id"),
                        "provider_code": fields.get("provider_code"),
                        "resource_type": "subscription",
                        "retryable": False,
                    },
                ) from exc
            raise

    async def _mark_reconciliation(
        self, db: AsyncSession, organization_id: str, exc: APIException
    ) -> None:
        sub = await self.repository.get_subscription(db, organization_id)
        if not sub:
            return
        fields = exc.fields or {}
        sub.reconciliation_required = True
        sub.last_provider_check_at = datetime.now(UTC)
        sub.last_provider_error_code = str(fields.get("provider_code") or exc.code)[:80]
        request_id = fields.get("provider_request_id")
        sub.last_provider_request_id = request_id if isinstance(request_id, str) else None
        await db.commit()

    def _urls(self, plan_slug: str) -> tuple[str, str]:
        root = settings.frontend_base_url.rstrip("/")
        if not root.startswith(("https://", "http://localhost")):
            raise APIException(message="Subscription return URL is not configured", status_code=503)
        return (
            f"{root}/organization/subscription/payment/success?{urlencode({'plan_slug': plan_slug})}",
            f"{root}/organization/subscription/payment/cancel",
        )

    def _request_hash(self, plan: BillingPlan, subscription_id: str | None) -> str:
        return hashlib.sha256(
            json.dumps(
                {
                    "plan": plan.slug,
                    "amount_minor": plan.amount_minor,
                    "currency": plan.currency,
                    "interval": plan.billing_cycle,
                    "urls": self._urls(plan.slug),
                    "subscription_id": subscription_id,
                    "configuration": getattr(
                        settings, "STRIPE_SUBSCRIPTION_PORTAL_CONFIGURATION_ID", None
                    ),
                },
                sort_keys=True,
            ).encode()
        ).hexdigest()

    def _item(self, remote: Mapping, customer_id: str | None) -> Mapping:
        if not customer_id or _id(remote.get("customer")) != customer_id:
            raise ConflictError(message="Subscription customer does not match this organization")
        items = remote.get("items") or {}
        rows = items.get("data") or []
        if items.get("has_more") or len(rows) != 1 or rows[0].get("quantity") != 1:
            raise ConflictError(message="Only single-item organization subscriptions are supported")
        return rows[0]

    def _validate_remote_identity(
        self,
        remote: Mapping,
        *,
        subscription_id: str,
        customer_id: str | None,
        organization_id: str,
    ) -> None:
        metadata = remote.get("metadata") or {}
        if (
            remote.get("id") != subscription_id
            or not customer_id
            or _id(remote.get("customer")) != customer_id
            or metadata.get("scope") != SCOPE
            or metadata.get("organization_id") != organization_id
        ):
            raise ConflictError(
                message="The provider subscription does not belong to this organization",
                code="SUBSCRIPTION_DATA_INTEGRITY_ERROR",
            )

    def _validate_price(self, price: Mapping, plan: BillingPlan, *, legacy: bool = False) -> None:
        metadata = price.get("metadata") or {}
        recurring = price.get("recurring") or {}
        if (
            (
                not legacy
                and (metadata.get("scope") != SCOPE or metadata.get("plan_slug") != plan.slug)
            )
            or price.get("currency") != plan.currency
            or price.get("unit_amount") != plan.amount_minor
            or recurring.get("interval") != plan.billing_cycle
            or recurring.get("interval_count", 1) != 1
            or recurring.get("usage_type", "licensed") != "licensed"
            or price.get("billing_scheme", "per_unit") != "per_unit"
        ):
            raise ConflictError(
                message="Subscription price does not match the current organization plan"
            )

    def _check_session(self, session: Mapping, sub: OrganizationSubscription, org_id: str) -> None:
        metadata = session.get("metadata") or {}
        if (
            session.get("mode") != "subscription"
            or metadata.get("scope") != SCOPE
            or metadata.get("organization_id") != org_id
            or metadata.get("operation_id") != sub.checkout_operation_id
            or metadata.get("plan_slug") != sub.checkout_plan_slug
            or session.get("client_reference_id") != org_id
            or _id(session.get("customer")) != sub.customer_id
        ):
            raise ConflictError(
                message="Checkout does not match this organization billing operation"
            )

    async def create_checkout(
        self,
        db: AsyncSession,
        *,
        plan_slug: str,
        org_id: str | None,
        current_user: User,
        idempotency_key: str,
    ) -> dict:
        tenant = self._tenant(current_user, org_id)
        if not idempotency_key or not idempotency_key.strip() or len(idempotency_key) > 128:
            raise APIException(
                message="A non-empty Idempotency-Key of at most 128 characters is required"
            )
        operation = hashlib.sha256(f"{tenant}:{idempotency_key}".encode()).hexdigest()
        try:
            plan = await self._plan(db, plan_slug)
            org, sub = await self._locked(db, tenant)
            if not sub:
                sub = await self.repository.create_subscription(
                    db,
                    data={
                        "organization_id": tenant,
                        "status": "pending",
                        "amount": 0,
                        "currency": plan.currency.upper(),
                        "billing_cycle": plan.billing_cycle,
                        "auto_renew": False,
                    },
                )
                await db.flush()
            if sub.checkout_operation_id == operation and sub.checkout_plan_slug != plan.slug:
                raise ConflictError(message="Idempotency-Key was used for another plan")
            if (
                sub.subscription_id
                and sub.checkout_session_id
                and sub.checkout_operation_id == operation
                and sub.checkout_request_hash == self._request_hash(plan, None)
            ):
                completed = await self.provider.retrieve_checkout(sub.checkout_session_id)
                self._check_session(completed, sub, tenant)
                if (
                    completed.get("status") == "complete"
                    and _id(completed.get("subscription")) == sub.subscription_id
                ):
                    raise ConflictError(
                        message="Checkout completed; verify the existing subscription",
                        code="SUBSCRIPTION_CHECKOUT_COMPLETED",
                        fields={
                            "session_id": sub.checkout_session_id,
                            "plan_slug": sub.checkout_plan_slug,
                        },
                    )
                raise ConflictError(
                    message="Checkout needs provider reconciliation",
                    code="SUBSCRIPTION_CHECKOUT_CONFLICT",
                )
            fingerprint = self._request_hash(plan, sub.subscription_id)
            if sub.checkout_operation_id == operation and sub.checkout_request_hash != fingerprint:
                raise ConflictError(
                    message="Checkout parameters changed; reconcile the existing operation",
                    code="SUBSCRIPTION_CHECKOUT_CONFLICT",
                )
            if sub.subscription_id:
                remote = await self._retrieve_subscription(sub.subscription_id)
                self._validate_remote_identity(
                    remote,
                    subscription_id=sub.subscription_id,
                    customer_id=sub.customer_id,
                    organization_id=tenant,
                )
                item = self._item(remote, sub.customer_id)
                if remote.get("status") != "active":
                    raise ConflictError(
                        message="Resolve the existing subscription before changing plans"
                    )
                if (
                    await self._paid_plan(db, remote, sub.customer_id, local=sub, organization=org)
                    is None
                ):
                    raise ConflictError(
                        message="Resolve the existing subscription payment before changing plans"
                    )
                # A portal flow always updates the existing item, never creates a second subscription.
                sub.checkout_operation_id = operation
                sub.checkout_plan_slug = plan.slug
                sub.checkout_request_hash = fingerprint
                await db.commit()
                org, sub = await self._locked(db, tenant)
                if (
                    not sub
                    or sub.checkout_operation_id != operation
                    or not sub.subscription_id
                    or not sub.customer_id
                ):
                    raise ConflictError(message="Another subscription operation is in progress")
                remote = await self._retrieve_subscription(sub.subscription_id)
                self._validate_remote_identity(
                    remote,
                    subscription_id=sub.subscription_id,
                    customer_id=sub.customer_id,
                    organization_id=tenant,
                )
                item = self._item(remote, sub.customer_id)
                if (
                    await self._paid_plan(db, remote, sub.customer_id, local=sub, organization=org)
                    is None
                ):
                    raise ConflictError(message="Subscription no longer has a settled payment")
                price = await self.provider.ensure_price(
                    plan_slug=plan.slug,
                    name=plan.name,
                    amount_minor=plan.amount_minor,
                    currency=plan.currency,
                    billing_cycle=plan.billing_cycle,
                )
                self._validate_price(price, plan)
                success, _ = self._urls(plan.slug)
                portal = await self.provider.create_portal(
                    customer_id=sub.customer_id,
                    subscription_id=sub.subscription_id,
                    item_id=item["id"],
                    price_id=price["id"],
                    return_url=success,
                    operation_id=operation,
                    organization_id=tenant,
                )
                await db.commit()
                return {"checkout_url": portal["url"], "session_id": None, "status": "success"}
            if sub.checkout_session_id:
                session = await self.provider.retrieve_checkout(sub.checkout_session_id)
                self._check_session(session, sub, tenant)
                if session.get("status") == "open":
                    if sub.checkout_plan_slug != plan.slug:
                        raise ConflictError(
                            message="An open checkout already exists for another plan"
                        )
                    await db.commit()
                    return {
                        "checkout_url": session["url"],
                        "session_id": session["id"],
                        "status": "success",
                    }
                if session.get("status") != "expired":
                    raise ConflictError(message="Checkout awaits webhook reconciliation")
                sub.checkout_session_id = None
                sub.checkout_operation_id = None
                sub.checkout_plan_slug = None
                sub.checkout_request_hash = None
                sub.checkout_expires_at = None
                await db.commit()
                raise ConflictError(
                    message="Checkout expired; use a new Idempotency-Key",
                    code="SUBSCRIPTION_CHECKOUT_EXPIRED",
                )
            if sub.checkout_operation_id:
                if sub.checkout_plan_slug != plan.slug or sub.checkout_operation_id != operation:
                    raise ConflictError(
                        message="Retry the existing checkout operation before starting another",
                        code="SUBSCRIPTION_CHECKOUT_CONFLICT",
                    )
                if not sub.checkout_expires_at or datetime.now(UTC) >= _utc(
                    sub.checkout_expires_at
                ) + timedelta(hours=22):
                    raise ConflictError(
                        message="Unknown checkout outcome requires provider reconciliation",
                        code="SUBSCRIPTION_CHECKOUT_UNKNOWN",
                    )
            else:
                sub.checkout_operation_id = operation
                sub.checkout_plan_slug = plan.slug
                sub.checkout_request_hash = fingerprint
                sub.checkout_expires_at = datetime.now(UTC).replace(microsecond=0) + timedelta(
                    hours=1
                )
            # Commit the operation before remote side effects so a timeout remains recoverable.
            await db.commit()
            org, sub = await self._locked(db, tenant)
            if not sub or sub.checkout_operation_id != operation or sub.subscription_id:
                raise ConflictError(
                    message="Subscription operation changed; refresh billing status"
                )
            if sub.checkout_session_id:
                session = await self.provider.retrieve_checkout(sub.checkout_session_id)
            else:
                if not sub.customer_id:
                    customer = await self.provider.create_customer(
                        organization_id=tenant, operation_id=operation
                    )
                    sub.customer_id = customer["id"]
                    await db.commit()
                    org, sub = await self._locked(db, tenant)
                    if not sub or sub.checkout_operation_id != operation or sub.subscription_id:
                        raise ConflictError(message="Subscription operation changed")
                price = await self.provider.ensure_price(
                    plan_slug=plan.slug,
                    name=plan.name,
                    amount_minor=plan.amount_minor,
                    currency=plan.currency,
                    billing_cycle=plan.billing_cycle,
                )
                self._validate_price(price, plan)
                success, cancel = self._urls(plan.slug)
                if not sub.customer_id or not sub.checkout_expires_at:
                    raise ConflictError(message="Checkout operation is incomplete")
                session = await self.provider.create_checkout(
                    customer_id=sub.customer_id,
                    price_id=price["id"],
                    organization_id=tenant,
                    plan_slug=plan.slug,
                    operation_id=operation,
                    expires_at=int(_utc(sub.checkout_expires_at).timestamp()),
                    success_url=success + "&session_id={CHECKOUT_SESSION_ID}",
                    cancel_url=cancel,
                )
                self._check_session(session, sub, tenant)
                sub.checkout_session_id = session["id"]
            await db.commit()
            if session.get("status") != "open" or not session.get("url"):
                raise ConflictError(message="Checkout awaits webhook reconciliation or has expired")
            return {
                "checkout_url": session["url"],
                "session_id": session["id"],
                "status": "success",
            }
        except APIException as exc:
            await db.rollback()
            if exc.code == "SUBSCRIPTION_RECONCILIATION_REQUIRED":
                await self._mark_reconciliation(db, tenant, exc)
            raise
        except Exception:
            await db.rollback()
            raise

    async def _paid_plan(
        self,
        db: AsyncSession,
        remote: Mapping,
        customer_id: str | None,
        *,
        local: OrganizationSubscription | None = None,
        organization: Organization | None = None,
    ) -> tuple[BillingPlan, Mapping, Mapping] | None:
        if not customer_id:
            raise ConflictError(message="Subscription customer needs reconciliation")
        item = self._item(remote, customer_id)
        if remote.get("status") != "active" or remote.get("pending_update"):
            return None
        price = item.get("price") or {}
        metadata = price.get("metadata") or {}
        legacy = not metadata.get("scope")
        if legacy:
            if not local or not organization or local.subscription_id != remote.get("id"):
                raise ConflictError(message="Legacy subscription requires billing reconciliation")
            stored_plan = (
                await self.repository.get_plan_by_id(db, local.plan_id) if local.plan_id else None
            )
            slug = stored_plan.slug if stored_plan else organization.plan.lower()
            plan = await self._plan(db, slug)
            if metadata.get("plan_slug") and metadata["plan_slug"] != plan.slug:
                raise ConflictError(message="Legacy price plan does not match stored billing terms")
            archive = local.legacy_provider_data or {}
            if (
                (archive.get("subscription_id") and archive["subscription_id"] != remote.get("id"))
                or (archive.get("customer_id") and archive["customer_id"] != customer_id)
                or Decimal(str(local.amount)) != plan.amount
                or local.currency.lower() != plan.currency
                or local.billing_cycle.lower().removesuffix("ly") != plan.billing_cycle
            ):
                raise ConflictError(
                    message="Legacy subscription terms require billing reconciliation"
                )
        else:
            plan = await self._plan(db, metadata.get("plan_slug", ""))
        self._validate_price(price, plan, legacy=legacy)
        invoice = remote.get("latest_invoice")
        if isinstance(invoice, str):
            invoice = await self.provider.retrieve_invoice(invoice)
        if not isinstance(invoice, Mapping) or invoice.get("status") != "paid":
            return None
        if (
            _invoice_subscription(invoice) != remote.get("id")
            or _id(invoice.get("customer")) != customer_id
            or invoice.get("currency") != plan.currency
        ):
            raise ConflictError(message="Paid invoice does not match the organization subscription")
        lines = invoice.get("lines") or {}
        if lines.get("has_more"):
            raise ConflictError(message="Subscription invoice needs provider reconciliation")
        current_price = price.get("id")
        matching = [
            line
            for line in lines.get("data", [])
            if (
                _id(line.get("price"))
                or ((line.get("pricing") or {}).get("price_details") or {}).get("price")
            )
            == current_price
            and line.get("amount", 0) >= 0
        ]
        if not matching:
            raise ConflictError(
                message="Paid invoice does not contain the current subscription price"
            )
        return plan, invoice, item

    async def verify_checkout(
        self,
        db: AsyncSession,
        *,
        session_id: str | None,
        plan_slug: str | None,
        current_user: User,
        org_id: str | None = None,
    ) -> dict:
        tenant = self._tenant(current_user, org_id)
        org = await self.repository.get_by_id(db, tenant)
        sub = await self.repository.get_subscription(db, tenant)
        if not org or not sub:
            raise NotFoundError(message="Organization subscription not found")
        requested = plan_slug or sub.checkout_plan_slug
        if requested:
            await self._plan(db, requested)
        remote_id = sub.subscription_id
        if session_id:
            if session_id != sub.checkout_session_id:
                raise NotFoundError(message="Checkout session not found")
            session = await self.provider.retrieve_checkout(session_id)
            self._check_session(session, sub, tenant)
            remote_id = _id(session.get("subscription"))
            if sub.subscription_id and remote_id and sub.subscription_id != remote_id:
                raise ConflictError(message="Checkout subscription does not match local billing")
        verified = False
        paid = None
        if remote_id:
            remote = await self._retrieve_subscription(remote_id)
            self._validate_remote_identity(
                remote,
                subscription_id=remote_id,
                customer_id=sub.customer_id,
                organization_id=tenant,
            )
            paid = await self._paid_plan(db, remote, sub.customer_id, local=sub, organization=org)
            verified = paid is not None and (not requested or paid[0].slug == requested)
        synced = bool(
            verified
            and paid
            and sub.subscription_id == remote_id
            and sub.status == "active"
            and sub.invoice_id == paid[1].get("id")
            and org.plan == paid[0].name
            and sub.plan_id == paid[0].plan_id
        )
        return {
            "verified": verified,
            "db_synced": synced,
            "plan": paid[0].name if paid else org.plan,
            "plan_slug": paid[0].slug if paid else requested,
            "status": "completed" if synced else "pending",
            "message": (
                "Subscription confirmed"
                if synced
                else "Awaiting verified subscription payment and webhook processing"
            ),
        }

    async def handle_webhook(
        self, db: AsyncSession, *, payload_bytes: bytes, sig_header: str
    ) -> dict:
        event = await self.provider.construct_event(payload_bytes, sig_header)
        event_type, event_id = event.get("type"), event.get("id")
        supported = {
            "checkout.session.completed",
            "checkout.session.async_payment_succeeded",
            "invoice.paid",
            "invoice.payment_failed",
            "customer.subscription.updated",
            "customer.subscription.created",
            "customer.subscription.deleted",
        }
        if event_type not in supported:
            return {
                "status": "success",
                "message": "Event not applicable to organization subscriptions",
            }
        if not isinstance(event_id, str):
            raise APIException(message="Invalid subscription event", status_code=400)
        obj = (event.get("data") or {}).get("object") or {}
        tenant: str | None = None
        try:
            if event_type.startswith("checkout.session."):
                if (
                    obj.get("mode") != "subscription"
                    or (obj.get("metadata") or {}).get("scope") != SCOPE
                ):
                    return {"status": "success", "message": "Unrelated checkout ignored"}
                checkout_id = _id(obj)
                if not checkout_id:
                    raise APIException(message="Invalid checkout event", status_code=400)
                sub = await self.repository.get_subscription_by_checkout_session_id(db, checkout_id)
                if not sub:
                    raise ConflictError(
                        message="Checkout operation is not yet persisted; retry webhook"
                    )
                remote_id = _id(obj.get("subscription"))
            else:
                remote_id = (
                    _id(obj)
                    if event_type.startswith("customer.subscription.")
                    else _invoice_subscription(obj)
                )
                if not remote_id:
                    return {"status": "success", "message": "Unrelated invoice ignored"}
                sub = await self.repository.get_subscription_by_provider_id(db, remote_id)
                if not sub:
                    canonical = await self._retrieve_subscription(remote_id)
                    metadata = canonical.get("metadata") or {}
                    if metadata.get("scope") != SCOPE:
                        return {"status": "success", "message": "Unrelated subscription ignored"}
                    organization_id = metadata.get("organization_id")
                    if not isinstance(organization_id, str) or not organization_id:
                        raise APIException(
                            message="Subscription event has no organization", status_code=400
                        )
                    sub = await self.repository.get_subscription(db, organization_id)
            if not sub or not remote_id:
                raise ConflictError(message="Subscription event cannot yet be reconciled")
            tenant = sub.organization_id
            org, sub = await self._locked(db, tenant)
            if not sub:
                raise NotFoundError(message="Organization subscription not found")
            if await self.repository.get_processed_webhook_event(db, event_id):
                await db.commit()
                return {"status": "success", "message": "Event already processed"}
            if sub.subscription_id and sub.subscription_id != remote_id:
                raise ConflictError(message="Event refers to another subscription")
            if not sub.subscription_id:
                if not sub.checkout_session_id:
                    raise ConflictError(message="Initial checkout is not yet persisted")
                session = await self.provider.retrieve_checkout(sub.checkout_session_id)
                self._check_session(session, sub, tenant)
                if (
                    session.get("status") != "complete"
                    or _id(session.get("subscription")) != remote_id
                ):
                    raise ConflictError(
                        message="Initial checkout is not complete for this subscription"
                    )
            # Fetch after the tenant lock: event snapshots cannot roll billing state backwards.
            remote = await self._retrieve_subscription(remote_id)
            self._validate_remote_identity(
                remote,
                subscription_id=remote_id,
                customer_id=sub.customer_id,
                organization_id=tenant,
            )
            self._item(remote, sub.customer_id)
            paid = await self._paid_plan(db, remote, sub.customer_id, local=sub, organization=org)
            had_paid_access = bool(
                sub.subscription_id and sub.invoice_id and sub.status == "active"
            )
            sub.subscription_id = remote_id
            sub.payment_provider = "Stripe"
            sub.auto_renew = not bool(remote.get("cancel_at_period_end"))
            if paid:
                plan, invoice, item = paid
                org.plan, org.max_users = plan.name, plan.max_users
                sub.plan_id, sub.amount = plan.plan_id, float(plan.amount)
                sub.max_users, sub.storage_limit_gb = plan.max_users, plan.storage
                if sub.invoice_id != invoice["id"]:
                    sub.ai_credits = plan.ai_credits
                sub.currency, sub.billing_cycle, sub.status, sub.trial = (
                    plan.currency.upper(),
                    plan.billing_cycle,
                    "active",
                    False,
                )
                sub.invoice_id = invoice["id"]
                sub.current_period_start = _time(
                    item.get("current_period_start") or remote.get("current_period_start")
                )
                sub.current_period_end = _time(
                    item.get("current_period_end") or remote.get("current_period_end")
                )
                sub.next_billing = sub.current_period_end if sub.auto_renew else None
                sub.expires_at = sub.current_period_end
                sub.started_at = sub.started_at or _time(remote.get("start_date"))
                sub.reconciliation_required = False
                sub.last_provider_check_at = datetime.now(UTC)
                sub.last_provider_error_code = None
                sub.last_provider_request_id = None
            else:
                # Keep the last paid plan; never grant a pending or failed upgrade.
                pending_paid_upgrade = (
                    remote.get("status") == "active"
                    and remote.get("pending_update")
                    and had_paid_access
                )
                if not pending_paid_upgrade:
                    sub.status = "cancelled" if remote.get("status") == "canceled" else "past_due"
                if sub.status == "cancelled":
                    sub.auto_renew = False
                    sub.next_billing = None
            await self.repository.create_audit_log(
                db,
                organization_id=tenant,
                action="subscription.webhook",
                details=f"{event_id}:{event_type}",
            )
            await self.repository.record_processed_webhook_event(
                db, event_id=event_id, event_type=event_type
            )
            await db.commit()
            return {"status": "success", "message": "Subscription billing state synchronized"}
        except APIException as exc:
            await db.rollback()
            if exc.code == "SUBSCRIPTION_RECONCILIATION_REQUIRED" and tenant:
                await self._mark_reconciliation(db, tenant, exc)
            raise
        except Exception:
            await db.rollback()
            raise

    async def set_auto_renew(
        self, db: AsyncSession, *, current_user: User, auto_renew: bool
    ) -> dict:
        tenant = self._tenant(current_user)
        try:
            _, sub = await self._locked(db, tenant)
            if not sub or not sub.subscription_id:
                raise ConflictError(message="No provider subscription is linked")
            remote = await self._retrieve_subscription(sub.subscription_id)
            self._validate_remote_identity(
                remote,
                subscription_id=sub.subscription_id,
                customer_id=sub.customer_id,
                organization_id=tenant,
            )
            self._item(remote, sub.customer_id)
            if remote.get("status") not in {"active", "past_due"}:
                sub.reconciliation_required = True
                sub.last_provider_check_at = datetime.now(UTC)
                sub.last_provider_error_code = "provider_not_resumable"
                await db.commit()
                raise ConflictError(
                    message="The provider subscription is no longer resumable; administrator reconciliation is required",
                    code="SUBSCRIPTION_RECONCILIATION_REQUIRED",
                    fields={
                        "provider_code": "provider_not_resumable",
                        "resource_type": "subscription",
                        "retryable": False,
                    },
                )
            updated = await self.provider.set_auto_renew(sub.subscription_id, auto_renew=auto_renew)
            if (
                updated.get("id") != sub.subscription_id
                or _id(updated.get("customer")) != sub.customer_id
            ):
                raise ConflictError(
                    message="Provider subscription does not match this organization"
                )
            if bool(updated.get("cancel_at_period_end")) != (not auto_renew):
                raise ConflictError(message="Provider has not confirmed the renewal change")
            sub.auto_renew = auto_renew
            sub.reconciliation_required = False
            sub.last_provider_check_at = datetime.now(UTC)
            sub.last_provider_error_code = None
            sub.last_provider_request_id = None
            sub.next_billing = sub.current_period_end if auto_renew else None
            await self.repository.create_audit_log(
                db,
                organization_id=tenant,
                action="subscription.renewal_updated",
                details=f"auto_renew={auto_renew}",
            )
            await db.commit()
            return {
                "status": "success",
                "message": (
                    "Subscription renewal enabled"
                    if auto_renew
                    else "Subscription will cancel at the end of the paid period"
                ),
            }
        except APIException as exc:
            await db.rollback()
            if exc.code == "SUBSCRIPTION_RECONCILIATION_REQUIRED":
                await self._mark_reconciliation(db, tenant, exc)
            raise
        except Exception:
            await db.rollback()
            raise
