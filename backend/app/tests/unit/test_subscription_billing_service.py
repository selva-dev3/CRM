from typing import Any
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.exc import MultipleResultsFound
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIException, ConflictError, ForbiddenError
from app.models import Organization, User
from app.repositories.organization_repository import OrganizationRepository
from app.services.subscription_billing_service import SubscriptionBillingService
from app.services.subscription_stripe_provider import SubscriptionStripeProvider


@pytest.mark.asyncio
@pytest.mark.parametrize("method", ["create_checkout", "verify_checkout", "set_auto_renew"])
async def test_missing_tenant_cannot_reach_provider_or_repository(method):
    repository = AsyncMock(spec=OrganizationRepository)
    provider = AsyncMock(spec=SubscriptionStripeProvider)
    db = AsyncMock(spec=AsyncSession)
    service = SubscriptionBillingService(repository=repository, provider=provider)
    arguments: dict[str, dict[str, Any]] = {
        "create_checkout": {"plan_slug": "professional", "org_id": None, "idempotency_key": "key"},
        "verify_checkout": {"session_id": None, "plan_slug": "professional"},
        "set_auto_renew": {"auto_renew": False},
    }
    with pytest.raises(ForbiddenError):
        await getattr(service, method)(db, current_user=User(id="user"), **arguments[method])
    assert not repository.mock_calls
    assert not provider.mock_calls
    assert not db.mock_calls


@pytest.mark.asyncio
async def test_unknown_plan_is_not_coerced_to_enterprise():
    repository = AsyncMock(spec=OrganizationRepository)
    repository.get_plan_by_slug.return_value = None
    provider = AsyncMock(spec=SubscriptionStripeProvider)
    service = SubscriptionBillingService(repository=repository, provider=provider)
    db = AsyncMock(spec=AsyncSession)
    with pytest.raises(APIException) as exc:
        await service.create_checkout(
            db,
            plan_slug="unknown",
            org_id="org",
            current_user=User(id="user", organization_id="org"),
            idempotency_key="key",
        )
    assert exc.value.code == "UNKNOWN_PLAN"
    repository.get_by_id_for_update.assert_not_awaited()
    assert not provider.mock_calls
    db.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_duplicate_subscription_rows_fail_before_provider_access():
    repository = AsyncMock(spec=OrganizationRepository)
    repository.get_plan_by_slug.return_value = None
    repository.get_by_id_for_update.return_value = Organization(id="org", is_active=True)
    repository.get_subscription.side_effect = MultipleResultsFound()
    provider = AsyncMock(spec=SubscriptionStripeProvider)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(ConflictError) as exc:
        await SubscriptionBillingService(repository=repository, provider=provider).create_checkout(
            db,
            plan_slug="professional",
            org_id="org",
            current_user=User(id="user", organization_id="org"),
            idempotency_key="key",
        )

    assert exc.value.code == "SUBSCRIPTION_DATA_INTEGRITY_ERROR"
    assert not provider.mock_calls
    db.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_missing_stored_subscription_requires_reconciliation():
    provider = AsyncMock(spec=SubscriptionStripeProvider)
    provider.retrieve_subscription.side_effect = APIException(
        message="Provider resource missing",
        code="SUBSCRIPTION_PROVIDER_ERROR",
        status_code=502,
        fields={
            "retryable": False,
            "provider_request_id": "req_safe123",
            "provider_code": "resource_missing",
        },
    )
    service = SubscriptionBillingService(
        repository=AsyncMock(spec=OrganizationRepository), provider=provider
    )

    with pytest.raises(ConflictError) as exc:
        await service._retrieve_subscription("sub_private")

    assert exc.value.code == "SUBSCRIPTION_RECONCILIATION_REQUIRED"
    assert exc.value.fields == {"provider_request_id": "req_safe123"}


@pytest.mark.asyncio
async def test_bad_signature_cannot_consume_webhook_event():
    repository = AsyncMock(spec=OrganizationRepository)
    provider = AsyncMock(spec=SubscriptionStripeProvider)
    provider.construct_event.side_effect = APIException(
        message="Invalid signature", status_code=400
    )
    db = AsyncMock(spec=AsyncSession)
    with pytest.raises(APIException) as exc:
        await SubscriptionBillingService(repository=repository, provider=provider).handle_webhook(
            db, payload_bytes=b"bad", sig_header="malformed"
        )
    assert exc.value.status_code == 400
    assert not repository.mock_calls
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "kind,obj",
    [
        ("checkout.session.completed", {"id": "cs_invoice", "mode": "payment"}),
        ("invoice.paid", {"id": "in_unrelated"}),
        ("payment_intent.succeeded", {"id": "pi_unrelated"}),
    ],
)
async def test_non_subscription_events_do_not_mutate_billing(kind, obj):
    repository = AsyncMock(spec=OrganizationRepository)
    provider = AsyncMock(spec=SubscriptionStripeProvider)
    provider.construct_event.return_value = {
        "id": "evt_unrelated",
        "type": kind,
        "data": {"object": obj},
    }
    db = AsyncMock(spec=AsyncSession)
    result = await SubscriptionBillingService(
        repository=repository, provider=provider
    ).handle_webhook(db, payload_bytes=b"fake-event", sig_header="fake-signature")
    assert result["status"] == "success"
    assert not repository.mock_calls
    db.commit.assert_not_awaited()
