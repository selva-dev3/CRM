"""Fake adapter boundary only: never import or contact the real Stripe SDK."""

import secrets
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.core.errors import APIException
from app.services import subscription_stripe_provider as module
from app.services.subscription_stripe_provider import SCOPE, SubscriptionStripeProvider


@pytest.fixture
def provider(monkeypatch):
    monkeypatch.setattr(
        module, "settings", SimpleNamespace(STRIPE_SECRET_KEY=None, STRIPE_WEBHOOK_SECRET=None)
    )
    return SubscriptionStripeProvider()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "http_status,code,resource,retryable,message",
    [
        (401, None, "Subscription", False, "credentials or permissions"),
        (403, None, "Subscription", False, "credentials or permissions"),
        (404, "resource_missing", "Subscription", False, "test/live mode"),
        (400, None, "billing_portal.Session", False, "portal configuration"),
        (400, "parameter_invalid_integer", "Subscription", False, "administrator review"),
        (429, None, "Subscription", True, "retry the same operation"),
        (503, None, "Subscription", True, "retry the same operation"),
        (None, None, "Subscription", True, "retry the same operation"),
    ],
)
async def test_provider_errors_are_actionable_without_sensitive_data(
    provider, monkeypatch, caplog, http_status, code, resource, retryable, message
):
    class StripeError(Exception):
        pass

    failure = StripeError("credential-and-customer-data-must-not-appear")
    failure.http_status = http_status
    failure.code = code
    failure.request_id = "req_TestRequest123"
    endpoint = SimpleNamespace(retrieve=Mock(side_effect=failure))
    sdk = SimpleNamespace(
        StripeError=StripeError,
        Subscription=endpoint,
        billing_portal=SimpleNamespace(Session=endpoint),
    )
    monkeypatch.setattr(provider, "_sdk", lambda: sdk)
    test_key = secrets.token_hex(16)
    monkeypatch.setattr(module, "settings", SimpleNamespace(STRIPE_SECRET_KEY=test_key))
    with pytest.raises(APIException) as exc:
        await provider._call(resource, "retrieve", "private-customer-reference")
    assert exc.value.code == "SUBSCRIPTION_PROVIDER_ERROR"
    assert exc.value.status_code == 502
    assert message in exc.value.message
    assert exc.value.fields == {"retryable": retryable, "provider_request_id": "req_TestRequest123"}
    assert f"operation={resource}.retrieve" in caplog.text
    assert "req_TestRequest123" in caplog.text
    for sensitive in [str(failure), "private-customer-reference", test_key]:
        assert sensitive not in caplog.text
        assert sensitive not in str(exc.value.fields)


@pytest.mark.asyncio
async def test_provider_diagnostics_reject_untrusted_metadata(provider, monkeypatch, caplog):
    class StripeError(Exception):
        http_status = "unsafe-status"
        code = "unsafe-code\nsecret"
        request_id = "unsafe-request\nsecret"

    sdk = SimpleNamespace(
        StripeError=StripeError,
        Subscription=SimpleNamespace(retrieve=Mock(side_effect=StripeError("private-body"))),
    )
    monkeypatch.setattr(provider, "_sdk", lambda: sdk)
    monkeypatch.setattr(
        module, "settings", SimpleNamespace(STRIPE_SECRET_KEY=secrets.token_hex(16))
    )
    with pytest.raises(APIException) as exc:
        await provider.retrieve_subscription("private-reference")
    assert exc.value.fields["provider_request_id"] is None
    assert "code=unknown" in caplog.text
    assert "unsafe" not in caplog.text
    assert "secret" not in caplog.text


def test_missing_configuration_fails_before_sdk_import(provider, monkeypatch):
    importer = Mock()
    monkeypatch.setattr(module.importlib, "import_module", importer)
    with pytest.raises(APIException) as exc:
        provider._sdk()
    assert exc.value.status_code == 503
    importer.assert_not_called()


@pytest.mark.asyncio
async def test_existing_price_is_reused(provider, monkeypatch):
    call = AsyncMock(return_value={"data": [{"id": "price_existing"}]})
    monkeypatch.setattr(provider, "_call", call)
    result = await provider.ensure_price(
        plan_slug="professional", name="Professional", amount_minor=299900
    )
    assert result["id"] == "price_existing"
    call.assert_awaited_once_with(
        "Price",
        "list",
        lookup_keys=[f"{SCOPE}:professional:inr:month:299900"],
        active=True,
        limit=2,
    )


@pytest.mark.asyncio
async def test_new_price_uses_stable_scoped_idempotency(provider, monkeypatch):
    call = AsyncMock(side_effect=[{"data": []}, {"id": "prod_test"}, {"id": "price_test"}])
    monkeypatch.setattr(provider, "_call", call)
    await provider.ensure_price(plan_slug="professional", name="Professional", amount_minor=299900)
    product = call.await_args_list[1].kwargs
    price = call.await_args_list[2].kwargs
    assert product["metadata"] == {"scope": SCOPE, "plan_slug": "professional"}
    assert price["unit_amount"] == 299900
    assert price["recurring"] == {"interval": "month"}
    assert price["lookup_key"] == price["idempotency_key"]
    assert price["currency"] == "inr"


@pytest.mark.asyncio
async def test_ambiguous_prices_fail_closed(provider, monkeypatch):
    call = AsyncMock(return_value={"data": [{"id": "one"}, {"id": "two"}]})
    monkeypatch.setattr(provider, "_call", call)
    with pytest.raises(APIException) as exc:
        await provider.ensure_price(
            plan_slug="professional", name="Professional", amount_minor=299900
        )
    assert exc.value.status_code == 409
    call.assert_awaited_once()


@pytest.mark.asyncio
async def test_checkout_scopes_subscription_metadata_and_retry_key(provider, monkeypatch):
    call = AsyncMock(return_value={"id": "cs_fake", "url": "https://checkout.example.com/fake"})
    monkeypatch.setattr(provider, "_call", call)
    kwargs = {
        "customer_id": "cus_fake",
        "price_id": "price_fake",
        "organization_id": "org",
        "plan_slug": "professional",
        "operation_id": "operation",
        "expires_at": 2000000000,
        "success_url": "http://test/success",
        "cancel_url": "http://test/cancel",
    }
    await provider.create_checkout(**kwargs)
    await provider.create_checkout(**kwargs)
    assert call.await_args_list[0] == call.await_args_list[1]
    assert call.await_args is not None
    data = call.await_args.kwargs
    assert data["mode"] == "subscription"
    assert data["metadata"] == data["subscription_data"]["metadata"]
    assert data["metadata"]["organization_id"] == "org"
    assert data["metadata"]["scope"] == SCOPE
    assert data["client_reference_id"] == "org"


@pytest.mark.asyncio
async def test_upgrade_portal_targets_existing_subscription(provider, monkeypatch):
    call = AsyncMock(return_value={"url": "https://billing.example.com/fake"})
    monkeypatch.setattr(provider, "_call", call)
    await provider.create_portal(
        customer_id="cus_fake",
        subscription_id="sub_existing",
        item_id="si_existing",
        price_id="price_new",
        return_url="http://test/return",
        operation_id="operation",
        organization_id="org",
    )
    assert call.await_args is not None
    assert call.await_args.args == ("billing_portal.Session", "create")
    flow = call.await_args.kwargs["flow_data"]
    assert flow["subscription_update_confirm"]["subscription"] == "sub_existing"
    assert flow["subscription_update_confirm"]["items"] == [
        {"id": "si_existing", "price": "price_new", "quantity": 1}
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("auto_renew", [False, True])
async def test_auto_renew_modifies_same_subscription(provider, monkeypatch, auto_renew):
    call = AsyncMock(return_value={"id": "sub_existing"})
    monkeypatch.setattr(provider, "_call", call)
    await provider.set_auto_renew("sub_existing", auto_renew=auto_renew)
    call.assert_awaited_once_with(
        "Subscription", "modify", "sub_existing", cancel_at_period_end=not auto_renew
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("signature", ["", "malformed"])
async def test_invalid_signature_never_produces_an_event(provider, monkeypatch, signature):
    monkeypatch.setattr(
        module, "settings", SimpleNamespace(STRIPE_WEBHOOK_SECRET=secrets.token_hex(16))
    )

    class SignatureError(Exception):
        pass

    sdk = SimpleNamespace(
        SignatureVerificationError=SignatureError,
        Webhook=SimpleNamespace(construct_event=Mock(side_effect=SignatureError("invalid"))),
    )
    monkeypatch.setattr(provider, "_sdk", lambda: sdk)
    with pytest.raises(APIException) as exc:
        await provider.construct_event(b"{}", signature)
    assert exc.value.status_code == 400
    if not signature:
        sdk.Webhook.construct_event.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["resource", "webhook"])
async def test_sdk_response_objects_are_converted_through_to_dict(provider, monkeypatch, operation):
    expected = {"id": "sub_fake", "items": {"data": [{"price": {"id": "price_fake"}}]}}

    class StripeResponse:
        def to_dict(self):
            return expected

    class StripeError(Exception):
        pass

    result = StripeResponse()
    sdk = SimpleNamespace(
        StripeError=StripeError,
        SignatureVerificationError=StripeError,
        Subscription=SimpleNamespace(retrieve=Mock(return_value=result)),
        Webhook=SimpleNamespace(construct_event=Mock(return_value=result)),
    )
    monkeypatch.setattr(provider, "_sdk", lambda: sdk)
    monkeypatch.setattr(
        module,
        "settings",
        SimpleNamespace(
            STRIPE_SECRET_KEY=secrets.token_hex(16), STRIPE_WEBHOOK_SECRET=secrets.token_hex(16)
        ),
    )
    if operation == "resource":
        actual = await provider.retrieve_subscription("sub_fake")
    else:
        actual = await provider.construct_event(b"fake", "fake-signature")
    assert actual == expected
    assert isinstance(actual["items"]["data"][0]["price"], dict)
