from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user
from app.core.auth_cookies import clear_auth_cookie, set_auth_cookie
from app.core.config import settings
from app.core.security import create_access_token
from app.main import validate_cookie_authenticated_origin
from app.models import User


def test_auth_cookie_is_httponly_secure_and_cross_site_in_production(monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    response = Response()

    set_auth_cookie(response, "jwt-token")

    header = response.headers["set-cookie"]
    assert "HttpOnly" in header
    assert "Secure" in header
    assert "SameSite=none" in header
    assert "Max-Age=" in header


def test_session_cookie_omits_persistent_expiration(monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "test")
    response = Response()

    set_auth_cookie(response, "jwt-token", persistent=False)

    header = response.headers["set-cookie"]
    assert "HttpOnly" in header
    assert "Max-Age=" not in header


def test_clear_auth_cookie_expires_server_cookie(monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    response = Response()

    clear_auth_cookie(response)

    header = response.headers["set-cookie"]
    assert "HttpOnly" in header
    assert "Max-Age=0" in header
    assert "Secure" in header


@pytest.mark.asyncio
async def test_get_current_user_accepts_valid_auth_cookie():
    user = User(
        id="user-1",
        name="Alex",
        email="alex@crm.com",
        hashed_password="hash",  # noqa: S106 - synthetic test fixture
        role="Admin",
        organization_id="org-1",
        is_active=True,
    )
    token = create_access_token(user.id)
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/api/v1/auth/me",
            "headers": [(b"cookie", f"{settings.AUTH_COOKIE_NAME}={token}".encode())],
        }
    )
    result = Mock()
    result.scalars.return_value.first.return_value = user
    db = AsyncMock(spec=AsyncSession)
    db.execute = AsyncMock(return_value=result)

    current_user = await get_current_user(
        request=request,
        credentials=None,
        token_query=None,
        db=db,
    )

    assert current_user is user


@pytest.mark.asyncio
async def test_cookie_authenticated_mutation_rejects_untrusted_origin():
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/auth/change-password",
            "headers": [
                (b"cookie", f"{settings.AUTH_COOKIE_NAME}=jwt-token".encode()),
                (b"origin", b"https://attacker.example"),
            ],
        }
    )
    call_next = AsyncMock(return_value=Response())

    response = await validate_cookie_authenticated_origin(request, call_next)

    assert response.status_code == 403
    call_next.assert_not_awaited()


@pytest.mark.asyncio
async def test_cookie_authenticated_mutation_allows_configured_origin():
    allowed_origin = settings.cors_origins_list[0]
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/auth/change-password",
            "headers": [
                (b"cookie", f"{settings.AUTH_COOKIE_NAME}=jwt-token".encode()),
                (b"origin", allowed_origin.encode()),
            ],
        }
    )
    expected_response = Response(status_code=204)
    call_next = AsyncMock(return_value=expected_response)

    response = await validate_cookie_authenticated_origin(request, call_next)

    assert response is expected_response
    call_next.assert_awaited_once_with(request)
