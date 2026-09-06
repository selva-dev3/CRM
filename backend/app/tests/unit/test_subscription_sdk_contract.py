"""Exercise real Stripe response objects outside the runner's import blocker.

Only the child imports Stripe/application settings. It inherits no environment,
disables dotenv loading, and rejects network access before importing either.
"""

import subprocess
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[3]

SDK_CONTRACT = r"""
import asyncio
import hashlib
import hmac
import json
import os
import secrets
import sys
import time
from unittest.mock import patch


def forbid_network(event, args):
    if event in {"socket.connect", "socket.getaddrinfo", "socket.sendto"}:
        raise AssertionError("Network access is forbidden in the SDK contract test")


sys.addaudithook(forbid_network)
sys.path.insert(0, sys.argv[1])
os.environ.update({
    "DATABASE_URL": "postgresql+asyncpg://127.0.0.1/unused_sdk_contract",
    "SECRET_KEY": secrets.token_hex(32),
    "STRIPE_SECRET_KEY": secrets.token_hex(32),
    "STRIPE_WEBHOOK_SECRET": secrets.token_hex(32),
    "ENVIRONMENT": "test",
    "AWS_EC2_METADATA_DISABLED": "true",
})

from pydantic_settings import DotEnvSettingsSource

with patch.object(DotEnvSettingsSource, "_read_env_files", return_value={}):
    from app.services.subscription_stripe_provider import SCOPE, SubscriptionStripeProvider

import stripe

provider = SubscriptionStripeProvider()
case = sys.argv[2]
price = {
    "object": "price", "id": "price_contract", "currency": "inr",
    "unit_amount": 10000, "recurring": {"interval": "month", "interval_count": 1},
    "metadata": {"scope": SCOPE, "plan_slug": "contract"},
}


def assert_plain(value):
    assert not isinstance(value, stripe.StripeObject), type(value).__name__
    if isinstance(value, dict):
        for nested in value.values():
            assert_plain(nested)
    elif isinstance(value, list):
        for nested in value:
            assert_plain(nested)


async def check():
    if case == "checkout":
        expected = {
            "object": "checkout.session", "id": "cs_contract", "mode": "subscription",
            "metadata": {"scope": SCOPE, "organization_id": "org_contract"},
            "customer": {"object": "customer", "id": "cus_contract"},
        }
        response = stripe.checkout.Session.construct_from(expected, None)
        assert isinstance(response, stripe.StripeObject)
        with patch.object(stripe.checkout.Session, "retrieve", return_value=response) as retrieve:
            result = await provider.retrieve_checkout("cs_contract")
            retrieve.assert_called_once()
    elif case == "subscription":
        expected = {
            "object": "subscription", "id": "sub_contract", "status": "active",
            "items": {"object": "list", "has_more": False, "data": [{
                "object": "subscription_item", "id": "si_contract", "quantity": 1,
                "price": price,
            }]},
            "latest_invoice": {
                "object": "invoice", "id": "in_contract", "status": "paid",
                "lines": {"object": "list", "data": [{
                    "object": "line_item", "id": "il_contract",
                    "pricing": {"price_details": {"price": "price_contract"}},
                }]},
            },
        }
        response = stripe.Subscription.construct_from(expected, None)
        assert isinstance(response["items"]["data"][0]["price"], stripe.StripeObject)
        with patch.object(stripe.Subscription, "retrieve", return_value=response) as retrieve:
            result = await provider.retrieve_subscription("sub_contract")
            retrieve.assert_called_once()
    elif case == "price_list":
        expected = price
        response = stripe.ListObject.construct_from({
            "object": "list", "data": [price], "has_more": False,
        }, None)
        assert isinstance(response["data"][0], stripe.StripeObject)
        with patch.object(stripe.Price, "list", return_value=response) as list_prices:
            result = await provider.ensure_price(
                plan_slug="contract", name="Contract", amount_minor=10000,
            )
            list_prices.assert_called_once()
    else:
        expected = {
            "object": "event", "id": "evt_contract", "type": "customer.subscription.updated",
            "data": {"object": {
                "object": "subscription", "id": "sub_contract",
                "metadata": {"scope": SCOPE},
            }},
        }
        payload = json.dumps(expected).encode()
        timestamp = str(int(time.time()))
        digest = hmac.new(
            os.environ["STRIPE_WEBHOOK_SECRET"].encode(),
            timestamp.encode() + b"." + payload, hashlib.sha256,
        ).hexdigest()
        signature = f"t={timestamp},v1={digest}"
        if case == "invalid_signature":
            from app.core.errors import APIException
            try:
                await provider.construct_event(payload + b" ", signature)
            except APIException as error:
                assert error.status_code == 400
                return
            raise AssertionError("Tampered webhook payload was accepted")
        # Real local signature verification must also normalize the nested Event.
        result = await provider.construct_event(payload, signature)
    assert type(result) is dict, type(result).__name__
    assert_plain(result)
    assert result == expected


async def inline_mock_call(function, *args, **kwargs):
    # Dispatch is outside this conversion contract. Avoid executor shutdown in
    # restricted runners; the SDK resource methods above still return real objects.
    return function(*args, **kwargs)


with patch.object(asyncio, "to_thread", inline_mock_call):
    asyncio.run(check())
"""


@pytest.mark.parametrize(
    "case", ["checkout", "subscription", "price_list", "webhook", "invalid_signature"]
)
def test_subscription_provider_accepts_real_sdk_objects(case: str) -> None:
    result = subprocess.run(  # noqa: S603 -- fixed local code, no inherited secrets or network
        [sys.executable, "-I", "-B", "-c", SDK_CONTRACT, str(BACKEND_ROOT), case],
        cwd=BACKEND_ROOT,
        env={"PATH": "/usr/bin:/bin"},
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, f"SDK contract failed ({case}):\n{result.stderr}"
