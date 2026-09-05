from unittest.mock import AsyncMock

import pytest
from fastapi import BackgroundTasks, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.routers import auth as auth_router
from app.core.config import settings
from app.core.errors import APIException, _api_exception_handler
from app.schemas.crm_schemas import AcceptInviteRequest, LoginRequest

TEST_PASSWORD_VALUE = "synthetic-password"  # noqa: S105 - synthetic test credential
TEST_REFRESH_VALUE = "current-refresh"


def _request(*, refresh_token: str | None = None) -> Request:
    headers = []
    if refresh_token:
        headers.append(
            (
                b"cookie",
                f"{settings.AUTH_REFRESH_COOKIE_NAME}={refresh_token}".encode(),
            )
        )
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": f"{settings.API_V1_STR}/auth/refresh-token",
            "headers": headers,
        }
    )


def _token_result() -> dict:
    return {
        "access_token": "access-token",
        "refresh_token": "refresh-token",
        "token_type": "bearer",
        "expires_in": 86400,
    }


@pytest.mark.asyncio
async def test_login_sets_access_and_refresh_cookies_without_returning_refresh_token(monkeypatch):
    login_mock = AsyncMock(return_value=_token_result())
    monkeypatch.setattr(auth_router.auth_service, "login", login_mock)
    response = Response()
    db = AsyncMock(spec=AsyncSession)

    result = await auth_router.login(
        _request(),
        LoginRequest(email="alex@crm.com", password=TEST_PASSWORD_VALUE, remember_me=False),
        response,
        db,
    )

    cookies = response.headers.getlist("set-cookie")
    assert any(cookie.startswith(f"{settings.AUTH_COOKIE_NAME}=") for cookie in cookies)
    assert any(cookie.startswith(f"{settings.AUTH_REFRESH_COOKIE_NAME}=") for cookie in cookies)
    access_cookie = next(
        cookie for cookie in cookies if cookie.startswith(f"{settings.AUTH_COOKIE_NAME}=")
    )
    assert "Max-Age=" not in access_cookie
    assert "access_token" not in result
    assert "refresh_token" not in result


@pytest.mark.asyncio
async def test_refresh_reads_cookie_rotates_both_cookies_and_hides_token(monkeypatch):
    refresh_mock = AsyncMock(return_value=_token_result())
    monkeypatch.setattr(auth_router.auth_service, "refresh_token", refresh_mock)
    response = Response()
    db = AsyncMock(spec=AsyncSession)

    result = await auth_router.refresh_token(
        _request(refresh_token=TEST_REFRESH_VALUE), response, db
    )

    refresh_mock.assert_awaited_once_with(db, TEST_REFRESH_VALUE)
    cookies = response.headers.getlist("set-cookie")
    assert any(cookie.startswith(f"{settings.AUTH_COOKIE_NAME}=") for cookie in cookies)
    assert any(cookie.startswith(f"{settings.AUTH_REFRESH_COOKIE_NAME}=") for cookie in cookies)
    assert "access_token" not in result
    assert "refresh_token" not in result


@pytest.mark.asyncio
async def test_refresh_rejects_missing_cookie(monkeypatch):
    refresh_mock = AsyncMock()
    monkeypatch.setattr(auth_router.auth_service, "refresh_token", refresh_mock)

    with pytest.raises(APIException) as exc_info:
        await auth_router.refresh_token(_request(), Response(), AsyncMock(spec=AsyncSession))

    assert exc_info.value.status_code == 401
    refresh_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_logout_without_access_token_revokes_refresh_and_clears_both_cookies(monkeypatch):
    logout_mock = AsyncMock(
        return_value={"message": "Logged out successfully", "status": "success"}
    )
    monkeypatch.setattr(auth_router.auth_service, "logout", logout_mock)
    response = Response()
    db = AsyncMock(spec=AsyncSession)

    result = await auth_router.logout(_request(refresh_token=TEST_REFRESH_VALUE), response, db)

    assert result["status"] == "success"
    logout_mock.assert_awaited_once_with(db, TEST_REFRESH_VALUE)
    cookies = response.headers.getlist("set-cookie")
    assert len(cookies) == 2
    assert all("Max-Age=0" in cookie for cookie in cookies)


@pytest.mark.asyncio
async def test_accept_invitation_sets_access_and_refresh_cookies(monkeypatch):
    result = _token_result() | {
        "message": "accepted",
        "user_id": "user-1",
        "email": "invite@crm.com",
        "name": "Invite User",
        "role": "Sales Manager",
        "status": "success",
        "user": {"id": "user-1", "permissions": ["users:read"]},
    }
    accept_mock = AsyncMock(return_value=result)
    monkeypatch.setattr(auth_router.auth_service, "accept_auth_user_invitation", accept_mock)
    response = Response()
    db = AsyncMock(spec=AsyncSession)
    payload = AcceptInviteRequest(
        token=TEST_REFRESH_VALUE,
        name="Invite User",
        password=TEST_PASSWORD_VALUE,
    )

    background_tasks = BackgroundTasks()
    response_body = await auth_router.accept_auth_user_invitation(
        _request(), payload, response, background_tasks, db
    )

    accept_mock.assert_awaited_once_with(db, payload)
    cookies = response.headers.getlist("set-cookie")
    assert any(cookie.startswith(f"{settings.AUTH_COOKIE_NAME}=") for cookie in cookies)
    assert any(cookie.startswith(f"{settings.AUTH_REFRESH_COOKIE_NAME}=") for cookie in cookies)
    assert "access_token" not in response_body
    assert "refresh_token" not in response_body
    assert len(background_tasks.tasks) == 1
    task = background_tasks.tasks[0]
    assert task.func is auth_router.send_welcome_email
    assert task.kwargs == {
        "email_to": "invite@crm.com",
        "user_name": "Invite User",
        "role": "Sales Manager",
    }


@pytest.mark.asyncio
async def test_password_hashing_failure_keeps_standard_500_response_shape():
    error = APIException(
        status_code=500,
        code="PASSWORD_HASHING_FAILED",
        message="Unable to create account. Please try again later.",
    )

    response = await _api_exception_handler(_request(), error)

    assert response.status_code == 500
    assert response.body == (
        b'{"code":"PASSWORD_HASHING_FAILED","message":"Unable to create account. '
        b'Please try again later.","fields":null}'
    )
