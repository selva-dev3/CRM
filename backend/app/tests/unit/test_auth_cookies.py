from hashlib import sha256
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import HTTPException, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user
from app.core.auth_cookies import (
    clear_auth_cookie,
    clear_refresh_cookie,
    set_auth_cookie,
    set_refresh_cookie,
)
from app.core.config import settings
from app.core.security import create_access_token
from app.main import validate_cookie_authenticated_origin
from app.models import Organization, User, UserSession


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


def test_refresh_cookie_is_httponly_secure_and_scoped_to_auth(monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    response = Response()

    set_refresh_cookie(response, "refresh-token")

    header = response.headers["set-cookie"]
    assert f"{settings.AUTH_REFRESH_COOKIE_NAME}=refresh-token" in header
    assert "HttpOnly" in header
    assert "Secure" in header
    assert "SameSite=none" in header
    assert f"Path={settings.API_V1_STR}/auth" in header
    assert f"Max-Age={settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400}" in header


def test_session_refresh_cookie_omits_persistent_expiration(monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "test")
    response = Response()

    set_refresh_cookie(response, "refresh-token", persistent=False)

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


def test_clear_refresh_cookie_uses_matching_path(monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    response = Response()

    clear_refresh_cookie(response)

    header = response.headers["set-cookie"]
    assert f"{settings.AUTH_REFRESH_COOKIE_NAME}=" in header
    assert "Max-Age=0" in header
    assert f"Path={settings.API_V1_STR}/auth" in header


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
    db.get = AsyncMock(
        side_effect=[
            Organization(id="org-1", name="Acme", status="active", is_active=True),
            UserSession(
                id=sha256(token.encode("utf-8")).hexdigest(),
                user_id=user.id,
                is_current=True,
            ),
        ]
    )

    current_user = await get_current_user(
        request=request,
        credentials=None,
        db=db,
    )

    assert current_user is user


@pytest.mark.asyncio
async def test_get_current_user_rejects_revoked_access_session():
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
    db.get = AsyncMock(
        side_effect=[
            Organization(id="org-1", name="Acme", status="active", is_active=True),
            UserSession(id="session-1", user_id=user.id, is_current=False),
        ]
    )

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(request=request, credentials=None, db=db)

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user_rejects_jwt_without_active_session():
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
    db.get = AsyncMock(
        side_effect=[
            Organization(id="org-1", name="Acme", status="active", is_active=True),
            None,
        ]
    )

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(request=request, credentials=None, db=db)

    assert exc_info.value.status_code == 401


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
async def test_refresh_cookie_mutation_rejects_untrusted_origin():
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": f"{settings.API_V1_STR}/auth/refresh-token",
            "headers": [
                (
                    b"cookie",
                    f"{settings.AUTH_REFRESH_COOKIE_NAME}=refresh-token".encode(),
                ),
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


@pytest.mark.asyncio
async def test_cookie_authenticated_mutation_allows_same_origin_request():
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "scheme": "https",
            "server": ("crm-bjza.onrender.com", 443),
            "path": "/api/v1/auth/login",
            "headers": [
                (b"host", b"crm-bjza.onrender.com"),
                (b"cookie", f"{settings.AUTH_COOKIE_NAME}=jwt-token".encode()),
                (b"origin", b"https://crm-bjza.onrender.com"),
            ],
        }
    )
    expected_response = Response(status_code=200)
    call_next = AsyncMock(return_value=expected_response)

    response = await validate_cookie_authenticated_origin(request, call_next)

    assert response is expected_response
    call_next.assert_awaited_once_with(request)
