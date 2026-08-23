import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import APIException, NotFoundError
from app.models import Organization, OrganizationSubscription, ProcessedWebhookEvent, SubscriptionPlan, User
from app.repositories.organization_repository import OrganizationRepository
from app.services.organization_service import OrganizationDomainService


@pytest.fixture
def mock_db():
    db = AsyncMock(spec=AsyncSession)
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    db.refresh = AsyncMock()
    db.add = MagicMock()
    return db


@pytest.fixture
def mock_repo():
    repo = MagicMock(spec=OrganizationRepository)
    return repo


@pytest.fixture
def org_service(mock_repo):
    return OrganizationDomainService(repository=mock_repo)


# ==============================================================================
# 1. CHECKOUT CREATION & VALIDATION TESTS
# ==============================================================================

@pytest.mark.asyncio
async def test_create_checkout_invalid_plan(org_service, mock_db):
    """Test 4: Invalid plan_slug is rejected with HTTP 400."""
    mock_repo = org_service.repository
    mock_repo.get_by_id = AsyncMock(return_value=Organization(id="org-1", name="Acme Corp"))
    mock_repo.get_plan_by_slug = AsyncMock(return_value=None)

    with pytest.raises(APIException) as exc_info:
        await org_service.create_subscription_checkout(
            mock_db, plan_slug="non_existent_plan_xyz", org_id="org-1"
        )
    assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
    assert "does not exist" in exc_info.value.message


@pytest.mark.asyncio
async def test_create_checkout_inactive_plan(org_service, mock_db):
    """Test 5: Inactive plan is rejected with HTTP 400."""
    mock_repo = org_service.repository
    mock_repo.get_by_id = AsyncMock(return_value=Organization(id="org-1", name="Acme Corp"))
    inactive_plan = SubscriptionPlan(
        id="plan-legacy", name="Legacy", slug="legacy", price_monthly=500.0, is_active=False
    )
    mock_repo.get_plan_by_slug = AsyncMock(return_value=inactive_plan)

    with pytest.raises(APIException) as exc_info:
        await org_service.create_subscription_checkout(
            mock_db, plan_slug="legacy", org_id="org-1"
        )
    assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
    assert "inactive" in exc_info.value.message


@pytest.mark.asyncio
async def test_create_checkout_unauthorized_organization_access(org_service, mock_db):
    """Test 3: User cannot create checkout for an organization they don't belong to."""
    mock_repo = org_service.repository
    mock_repo.get_by_id = AsyncMock(return_value=Organization(id="org-2", name="Victim Org"))
    unauthorized_user = User(
        id="user-attacker",
        email="attacker@test.com",
        organization_id="org-1",
        role="Member",
    )

    with pytest.raises(APIException) as exc_info:
        await org_service.create_subscription_checkout(
            mock_db, plan_slug="starter", org_id="org-2", current_user=unauthorized_user
        )
    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio
async def test_create_checkout_server_side_pricing_and_metadata(org_service, mock_db):
    """
    Tests 6, 7, 8, 9, 10:
    - Server resolves trusted price (Starter -> 99900 paise).
    - Metadata contains organization_id and plan_slug.
    - Creating checkout session DOES NOT update the subscription in the database.
    """
    mock_repo = org_service.repository
    org = Organization(id="org-1", name="Acme Corp", plan="Free")
    mock_repo.get_by_id = AsyncMock(return_value=org)
    starter_plan = SubscriptionPlan(
        id="plan-starter-id",
        name="Starter",
        slug="starter",
        price_monthly=999.0,
        max_users=10,
        max_storage_gb=20,
        ai_credits=500,
        is_active=True,
    )
    mock_repo.get_plan_by_slug = AsyncMock(return_value=starter_plan)

    user = User(id="user-1", email="admin@acme.com", organization_id="org-1", role="Admin")

    # Mock stripe.checkout.Session.create
    mock_stripe_session = MagicMock()
    mock_stripe_session.id = "cs_test_12345"
    mock_stripe_session.url = "https://checkout.stripe.com/pay/cs_test_12345"

    with patch("app.core.config.settings.STRIPE_SECRET_KEY", "sk_test_mock_key"), \
         patch("stripe.checkout.Session.create", return_value=mock_stripe_session) as mock_create:

        result = await org_service.create_subscription_checkout(
            mock_db, plan_slug="starter", org_id="org-1", current_user=user
        )

        assert result["session_id"] == "cs_test_12345"
        assert result["checkout_url"] == "https://checkout.stripe.com/pay/cs_test_12345"
        assert result["status"] == "success"

        # Verify Stripe parameters
        mock_create.assert_called_once()
        kwargs = mock_create.call_args.kwargs
        line_item = kwargs["line_items"][0]
        assert line_item["price_data"]["unit_amount"] == 99900  # 999 INR * 100
        assert line_item["price_data"]["currency"] == "inr"

        # Verify metadata
        assert kwargs["metadata"]["organization_id"] == "org-1"
        assert kwargs["metadata"]["plan_slug"] == "starter"
        assert kwargs["metadata"]["type"] == "subscription_upgrade"

        # Verify DB subscription was NOT updated at checkout creation time
        assert org.plan == "Free"
        mock_db.commit.assert_not_called()


# ==============================================================================
# 2. STRIPE WEBHOOK & TRANSACTIONAL UPGRADE TESTS
# ==============================================================================

@pytest.mark.asyncio
async def test_webhook_invalid_signature_rejected(org_service, mock_db):
    """Test 11: Invalid webhook signature is rejected with HTTP 400."""
    with patch("app.core.config.settings.STRIPE_WEBHOOK_SECRET", "whsec_mock_secret"):
        with patch("stripe.Webhook.construct_event", side_effect=Exception("Invalid signature")):
            with pytest.raises(APIException) as exc_info:
                await org_service.handle_stripe_subscription_webhook(
                    mock_db, payload_bytes=b"{}", sig_header="bad_sig"
                )
            assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
            assert "signature" in exc_info.value.message


@pytest.mark.asyncio
async def test_webhook_successful_payment_upgrades_subscription(org_service, mock_db):
    """
    Tests 12, 13, 14:
    - Valid webhook signature accepted.
    - Payment status must be 'paid'.
    - Subscription, Organization, Quotas, and ProcessedWebhookEvent updated in DB.
    """
    mock_repo = org_service.repository
    org = Organization(id="org-1", name="Acme Corp", plan="Free", max_users=3)
    subscription = OrganizationSubscription(
        id="sub-1", organization_id="org-1", plan_id=None, amount=0.0, status="active"
    )
    starter_plan = SubscriptionPlan(
        id="plan-starter-id",
        name="Starter",
        slug="starter",
        price_monthly=999.0,
        max_users=10,
        max_storage_gb=20,
        ai_credits=500,
        is_active=True,
    )

    mock_repo.get_by_id = AsyncMock(return_value=org)
    mock_repo.get_subscription = AsyncMock(return_value=subscription)
    mock_repo.get_plan_by_slug = AsyncMock(return_value=starter_plan)
    mock_repo.get_processed_webhook_event = AsyncMock(return_value=None)
    mock_repo.record_processed_webhook_event = AsyncMock()
    mock_repo.create_audit_log = AsyncMock()

    payload = {
        "id": "evt_test_success_1",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_test_session_99",
                "customer": "cus_123",
                "subscription": "sub_stripe_123",
                "payment_status": "paid",
                "metadata": {
                    "organization_id": "org-1",
                    "plan_slug": "starter",
                },
            }
        },
    }

    result = await org_service.handle_stripe_subscription_webhook(
        mock_db, payload_bytes=json.dumps(payload).encode("utf-8"), sig_header=None
    )

    assert result["status"] == "success"
    # Verify DB updates
    assert org.plan == "Starter"
    assert org.max_users == 10
    assert subscription.amount == 999.0
    assert subscription.plan_id == "plan-starter-id"
    assert subscription.payment_provider == "Stripe"
    assert subscription.customer_id == "cus_123"
    assert subscription.subscription_id == "sub_stripe_123"

    mock_repo.record_processed_webhook_event.assert_called_once_with(
        mock_db, event_id="evt_test_success_1", event_type="checkout.session.completed"
    )
    mock_db.commit.assert_called()


@pytest.mark.asyncio
async def test_webhook_unpaid_or_failed_status_does_not_upgrade(org_service, mock_db):
    """Test 15: Failed or unpaid payment status does NOT upgrade the subscription."""
    mock_repo = org_service.repository
    mock_repo.get_processed_webhook_event = AsyncMock(return_value=None)
    mock_repo.get_by_id = AsyncMock()

    payload = {
        "id": "evt_test_unpaid",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_test_failed",
                "payment_status": "unpaid",
                "metadata": {
                    "organization_id": "org-1",
                    "plan_slug": "starter",
                },
            }
        },
    }

    result = await org_service.handle_stripe_subscription_webhook(
        mock_db, payload_bytes=json.dumps(payload).encode("utf-8"), sig_header=None
    )

    assert result["status"] == "pending_or_unpaid"
    mock_repo.get_by_id.assert_not_called()
    mock_db.commit.assert_not_called()


@pytest.mark.asyncio
async def test_webhook_duplicate_event_is_idempotent(org_service, mock_db):
    """Test 17: Duplicate webhook event ID is detected and skipped safely."""
    mock_repo = org_service.repository
    existing_event = ProcessedWebhookEvent(
        id="p-1", event_id="evt_duplicate_1", event_type="checkout.session.completed"
    )
    mock_repo.get_processed_webhook_event = AsyncMock(return_value=existing_event)
    mock_repo.get_by_id = AsyncMock()

    payload = {
        "id": "evt_duplicate_1",
        "type": "checkout.session.completed",
        "data": {"object": {"payment_status": "paid"}},
    }

    result = await org_service.handle_stripe_subscription_webhook(
        mock_db, payload_bytes=json.dumps(payload).encode("utf-8"), sig_header=None
    )

    assert result["status"] == "ignored_duplicate"
    mock_repo.get_by_id.assert_not_called()
    mock_db.commit.assert_not_called()
