import json
from collections.abc import Iterator
from unittest.mock import AsyncMock

import pytest
from fastapi import Request, Response
from slowapi.errors import RateLimitExceeded
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.routers import auth as auth_router
from app.core.config import settings
from app.core.rate_limiter import limiter, rate_limit_exceeded_handler
from app.schemas.crm_schemas import AcceptInviteRequest

TEST_PASSWORD_VALUE = "synthetic-password"  # noqa: S105 - synthetic test credential
ANOTHER_INVITATION_VALUE = "another-token"
ACCEPTANCE_INVITATION_VALUE = "synthetic-invitation-value"
LIMITED_INVITATION_VALUE = "limited"
ALLOWED_INVITATION_VALUE = "allowed"


def _request(path: str, client_address: str) -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": path,
            "headers": [],
            "client": (client_address, 50000),
        }
    )


def _invitation_details() -> dict:
    return {
        "id": "inv-1",
        "email": "invite@crm.com",
        "role": "Sales Manager",
        "status": "pending",
        "organization_id": "org-1",
        "created_at": "2026-09-04T00:00:00+00:00",
    }


def _acceptance_result() -> dict:
    return {
        "message": "accepted",
        "access_token": "synthetic-access-value",
        "refresh_token": "synthetic-refresh-value",
        "token_type": "bearer",
        "user_id": "user-1",
        "email": "invite@crm.com",
        "name": "Invite User",
        "role": "Sales Manager",
        "status": "success",
        "user": {
            "id": "user-1",
            "name": "Invite User",
            "email": "invite@crm.com",
            "role": "Sales Manager",
            "organization_id": "org-1",
            "permissions": ["dashboard:read"],
        },
    }


@pytest.fixture(autouse=True)
def reset_rate_limiter() -> Iterator[None]:
    limiter.reset()
    yield
    limiter.reset()


def test_production_rate_limits_use_shared_configured_storage(monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(settings, "RATE_LIMIT_STORAGE_URI", None)
    monkeypatch.setattr(settings, "CELERY_BROKER_URL", "redis://redis.internal:6379/0")

    assert settings.rate_limit_storage_uri == "redis://redis.internal:6379/0"


def test_rate_limiter_is_registered_on_application():
    from app.main import app

    assert app.state.limiter is limiter
    assert app.exception_handlers[RateLimitExceeded] is rate_limit_exceeded_handler


@pytest.mark.asyncio
async def test_invitation_lookup_limits_varying_tokens_by_endpoint(monkeypatch):
    get_details = AsyncMock(return_value=_invitation_details())
    monkeypatch.setattr(auth_router.auth_service, "get_auth_invitation_details", get_details)
    db = AsyncMock(spec=AsyncSession)

    for index in range(10):
        result = await auth_router.get_auth_invitation_details(
            request=_request(f"/auth/invitations/token-{index}", "192.0.2.10"),
            token=f"token-{index}",
            db=db,
        )
        assert result["id"] == "inv-1"

    limited_request = _request("/auth/invitations/another-token", "192.0.2.10")
    with pytest.raises(RateLimitExceeded) as exc_info:
        await auth_router.get_auth_invitation_details(
            request=limited_request,
            token=ANOTHER_INVITATION_VALUE,
            db=db,
        )

    response = await rate_limit_exceeded_handler(limited_request, exc_info.value)
    assert response.status_code == 429
    assert json.loads(response.body) == {
        "code": "RATE_LIMITED",
        "message": "Too many requests. Please try again later.",
        "fields": None,
    }
    assert response.headers["Retry-After"] == "60"
    assert get_details.await_count == 10


@pytest.mark.asyncio
async def test_invitation_acceptance_is_limited_before_service_work(monkeypatch):
    accept_invitation = AsyncMock(return_value=_acceptance_result())
    monkeypatch.setattr(auth_router.auth_service, "accept_auth_user_invitation", accept_invitation)
    db = AsyncMock(spec=AsyncSession)
    payload = AcceptInviteRequest(
        token=ACCEPTANCE_INVITATION_VALUE,
        name="Invite User",
        password=TEST_PASSWORD_VALUE,
    )

    for _ in range(5):
        result = await auth_router.accept_auth_user_invitation(
            request=_request("/auth/accept-invite", "192.0.2.20"),
            payload=payload,
            response=Response(),
            db=db,
        )
        assert result["status"] == "success"

    with pytest.raises(RateLimitExceeded):
        await auth_router.accept_auth_user_invitation(
            request=_request("/auth/accept-invite", "192.0.2.20"),
            payload=payload,
            response=Response(),
            db=db,
        )

    assert accept_invitation.await_count == 5


@pytest.mark.asyncio
async def test_invitation_limits_are_isolated_by_client_address(monkeypatch):
    get_details = AsyncMock(return_value=_invitation_details())
    monkeypatch.setattr(auth_router.auth_service, "get_auth_invitation_details", get_details)
    db = AsyncMock(spec=AsyncSession)

    for index in range(10):
        await auth_router.get_auth_invitation_details(
            request=_request(f"/auth/invitations/token-{index}", "192.0.2.30"),
            token=f"token-{index}",
            db=db,
        )

    with pytest.raises(RateLimitExceeded):
        await auth_router.get_auth_invitation_details(
            request=_request("/auth/invitations/limited", "192.0.2.30"),
            token=LIMITED_INVITATION_VALUE,
            db=db,
        )

    result = await auth_router.get_auth_invitation_details(
        request=_request("/auth/invitations/allowed", "192.0.2.31"),
        token=ALLOWED_INVITATION_VALUE,
        db=db,
    )
    assert result["id"] == "inv-1"


@pytest.mark.asyncio
async def test_lookup_and_acceptance_limits_use_independent_buckets(monkeypatch):
    get_details = AsyncMock(return_value=_invitation_details())
    accept_invitation = AsyncMock(return_value=_acceptance_result())
    monkeypatch.setattr(auth_router.auth_service, "get_auth_invitation_details", get_details)
    monkeypatch.setattr(auth_router.auth_service, "accept_auth_user_invitation", accept_invitation)
    db = AsyncMock(spec=AsyncSession)
    client_address = "192.0.2.40"

    for index in range(10):
        await auth_router.get_auth_invitation_details(
            request=_request(f"/auth/invitations/token-{index}", client_address),
            token=f"token-{index}",
            db=db,
        )

    result = await auth_router.accept_auth_user_invitation(
        request=_request("/auth/accept-invite", client_address),
        payload=AcceptInviteRequest(
            token=ACCEPTANCE_INVITATION_VALUE,
            name="Invite User",
            password=TEST_PASSWORD_VALUE,
        ),
        response=Response(),
        db=db,
    )

    assert result["status"] == "success"
