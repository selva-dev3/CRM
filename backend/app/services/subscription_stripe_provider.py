"""Lazy, organization-subscription-only Stripe adapter."""

import asyncio
import importlib
import re
from typing import Any

from app.core.config import settings
from app.core.errors import APIException
from app.core.logging import get_logger

SCOPE = "crm_organization_subscription"
logger = get_logger(__name__)


class SubscriptionStripeProvider:
    def _validate_mode(self) -> None:
        key = getattr(settings, "STRIPE_SECRET_KEY", None)
        configured = getattr(settings, "STRIPE_MODE", None)
        if not key or not configured:
            return
        expected = (
            "test" if key.startswith("sk_test_") else "live" if key.startswith("sk_live_") else None
        )
        if expected and expected != configured:
            raise APIException(
                message="Subscription billing mode is misconfigured; administrator review is required.",
                code="SUBSCRIPTION_PROVIDER_CONFIGURATION_ERROR",
                status_code=503,
                fields={"retryable": False, "operation": "configuration"},
            )

    def _sdk(self) -> Any:
        if not getattr(settings, "STRIPE_SECRET_KEY", None):
            raise APIException(message="Subscription billing is not configured", status_code=503)
        self._validate_mode()
        try:
            return importlib.import_module("stripe")
        except ImportError as exc:
            raise APIException(
                message="Subscription billing is unavailable", status_code=503
            ) from exc

    async def _call(self, resource: str, method: str, *args: Any, **kwargs: Any) -> dict:
        sdk = self._sdk()
        target = sdk
        for component in resource.split("."):
            target = getattr(target, component)
        try:
            result = await asyncio.to_thread(
                getattr(target, method), *args, api_key=settings.STRIPE_SECRET_KEY, **kwargs
            )
            return result.to_dict() if hasattr(result, "to_dict") else dict(result)
        except sdk.StripeError as exc:
            # Never log the exception text, headers, arguments, or provider body:
            # they can contain credentials or customer data.
            raw_code = getattr(exc, "code", None)
            error_code = (
                raw_code
                if isinstance(raw_code, str) and re.fullmatch(r"[a-z_]{1,80}", raw_code)
                else "unknown"
            )
            raw_request = getattr(exc, "request_id", None)
            request_id = (
                raw_request
                if isinstance(raw_request, str)
                and re.fullmatch(r"req_[A-Za-z0-9]{1,100}", raw_request)
                else None
            )
            raw_status = getattr(exc, "http_status", None)
            http_status = (
                raw_status if type(raw_status) is int and 100 <= raw_status <= 599 else None
            )
            retryable = http_status is None or http_status == 429 or http_status >= 500
            message = "Subscription billing requires administrator review before retrying."
            if retryable:
                message = (
                    "Subscription billing is temporarily unavailable; retry the same operation."
                )
            elif http_status in {401, 403}:
                message = (
                    "Subscription billing credentials or permissions require administrator review."
                )
            elif error_code == "resource_missing":
                message = "A subscription billing resource was not found. Ask an administrator to verify the Stripe account and test/live mode."
            elif resource == "billing_portal.Session":
                message = "Subscription portal configuration or the requested plan change requires administrator review."
            logger.warning(
                "Subscription provider failure operation=%s.%s code=%s http_status=%s stripe_request_id=%s retryable=%s",
                resource,
                method,
                error_code,
                http_status,
                request_id,
                retryable,
            )
            raise APIException(
                message=message,
                code="SUBSCRIPTION_PROVIDER_ERROR",
                status_code=502,
                fields={
                    "retryable": retryable,
                    "provider_request_id": request_id,
                    "provider_code": error_code,
                },
            ) from exc

    async def ensure_price(
        self,
        *,
        plan_slug: str,
        name: str,
        amount_minor: int,
        currency: str = "inr",
        billing_cycle: str = "month",
    ) -> dict:
        key = f"{SCOPE}:{plan_slug}:{currency}:{billing_cycle}:{amount_minor}"
        result = await self._call("Price", "list", lookup_keys=[key], active=True, limit=2)
        prices = result.get("data", [])
        if len(prices) == 1:
            return dict(prices[0])
        if prices:
            raise APIException(
                message="Subscription price configuration is ambiguous", status_code=409
            )
        product = await self._call(
            "Product",
            "create",
            name=f"CRM {name}",
            metadata={"scope": SCOPE, "plan_slug": plan_slug},
            idempotency_key=f"{SCOPE}:product:{plan_slug}",
        )
        return await self._call(
            "Price",
            "create",
            product=product["id"],
            currency=currency,
            unit_amount=amount_minor,
            recurring={"interval": billing_cycle},
            metadata={"scope": SCOPE, "plan_slug": plan_slug},
            lookup_key=key,
            idempotency_key=key,
        )

    async def create_customer(self, *, organization_id: str, operation_id: str) -> dict:
        return await self._call(
            "Customer",
            "create",
            metadata={"scope": SCOPE, "organization_id": organization_id},
            idempotency_key=f"{SCOPE}:{organization_id}:{operation_id}:customer",
        )

    async def create_checkout(
        self,
        *,
        customer_id: str,
        price_id: str,
        organization_id: str,
        plan_slug: str,
        operation_id: str,
        expires_at: int,
        success_url: str,
        cancel_url: str,
    ) -> dict:
        metadata = {
            "scope": SCOPE,
            "organization_id": organization_id,
            "plan_slug": plan_slug,
            "operation_id": operation_id,
        }
        return await self._call(
            "checkout.Session",
            "create",
            mode="subscription",
            customer=customer_id,
            client_reference_id=organization_id,
            metadata=metadata,
            subscription_data={"metadata": metadata},
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=success_url,
            cancel_url=cancel_url,
            expires_at=expires_at,
            idempotency_key=f"{SCOPE}:{organization_id}:{operation_id}:checkout",
        )

    async def retrieve_checkout(self, session_id: str) -> dict:
        return await self._call("checkout.Session", "retrieve", session_id)

    async def retrieve_subscription(self, subscription_id: str) -> dict:
        return await self._call(
            "Subscription",
            "retrieve",
            subscription_id,
            expand=["items.data.price", "latest_invoice"],
        )

    async def retrieve_customer(self, customer_id: str) -> dict:
        return await self._call("Customer", "retrieve", customer_id)

    async def retrieve_invoice(self, invoice_id: str) -> dict:
        return await self._call("Invoice", "retrieve", invoice_id)

    async def create_portal(
        self,
        *,
        customer_id: str,
        subscription_id: str,
        item_id: str,
        price_id: str,
        return_url: str,
        operation_id: str,
        organization_id: str,
    ) -> dict:
        configuration = getattr(settings, "STRIPE_SUBSCRIPTION_PORTAL_CONFIGURATION_ID", None)
        options = {"configuration": configuration} if configuration else {}
        return await self._call(
            "billing_portal.Session",
            "create",
            customer=customer_id,
            return_url=return_url,
            flow_data={
                "type": "subscription_update_confirm",
                "subscription_update_confirm": {
                    "subscription": subscription_id,
                    "items": [{"id": item_id, "price": price_id, "quantity": 1}],
                },
                "after_completion": {"type": "redirect", "redirect": {"return_url": return_url}},
            },
            idempotency_key=f"{SCOPE}:{organization_id}:{operation_id}:portal",
            **options,
        )

    async def set_auto_renew(self, subscription_id: str, *, auto_renew: bool) -> dict:
        return await self._call(
            "Subscription", "modify", subscription_id, cancel_at_period_end=not auto_renew
        )

    async def construct_event(self, payload_bytes: bytes, sig_header: str) -> dict:
        secret = getattr(settings, "STRIPE_WEBHOOK_SECRET", None)
        if not secret:
            raise APIException(message="Subscription webhook is not configured", status_code=503)
        if not sig_header:
            raise APIException(message="Webhook signature is required", status_code=400)
        sdk = self._sdk()
        try:
            # Signature verification is local HMAC/JSON work, with no provider I/O.
            event = sdk.Webhook.construct_event(payload_bytes, sig_header, secret)
            return event.to_dict() if hasattr(event, "to_dict") else dict(event)
        except (ValueError, sdk.SignatureVerificationError) as exc:
            raise APIException(
                message="Invalid webhook signature or payload", status_code=400
            ) from exc
