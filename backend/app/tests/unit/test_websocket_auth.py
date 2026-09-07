from hashlib import sha256
from unittest.mock import AsyncMock

import pytest

from app.api.v1.routers.websockets import _authenticate_websocket
from app.core.security import create_access_token
from app.models import Organization, User, UserSession


def _active_user(**overrides) -> User:
    values = dict(
        id="u1", name="Alex", email="alex@crm.com", hashed_password="h",
        organization_id="org-1", is_active=True, is_platform_admin=True,
    )
    values.update(overrides)
    return User(**values)


def _ws(token: str | None = None, organization_id: str = "org-1") -> AsyncMock:
    ws = AsyncMock()
    ws.cookies = {"token": token} if token else {}
    ws.headers = {}
    ws.query_params = {"organization_id": organization_id}
    return ws


def _db(user: User | None, session: UserSession | None, organization: Organization | None) -> AsyncMock:
    db = AsyncMock()
    async def get(model, key):
        if model is User:
            return user
        if model is UserSession:
            return session
        return organization
    db.get.side_effect = get
    return db


@pytest.mark.asyncio
async def test_websocket_accepts_active_cookie_session():
    user = _active_user()
    token = create_access_token(user.id)
    session = UserSession(id=sha256(token.encode()).hexdigest(), user_id=user.id, is_current=True)
    result = await _authenticate_websocket(
        _ws(token), _db(user, session, Organization(id="org-1", is_active=True, status="active"))
    )
    assert result is not None
    assert result[0] is user


@pytest.mark.asyncio
async def test_websocket_rejects_missing_token():
    ws = _ws()
    assert await _authenticate_websocket(ws, AsyncMock()) is None
    ws.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_websocket_rejects_invalid_jwt():
    ws = _ws("invalid")
    assert await _authenticate_websocket(ws, AsyncMock()) is None
    ws.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_websocket_rejects_revoked_session():
    user = _active_user()
    token = create_access_token(user.id)
    session = UserSession(id=sha256(token.encode()).hexdigest(), user_id=user.id, is_current=False)
    ws = _ws(token)
    assert await _authenticate_websocket(
        ws, _db(user, session, Organization(id="org-1", is_active=True, status="active"))
    ) is None
    ws.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_websocket_rejects_inactive_user():
    user = _active_user(is_active=False)
    token = create_access_token(user.id)
    session = UserSession(id=sha256(token.encode()).hexdigest(), user_id=user.id, is_current=True)
    ws = _ws(token)
    assert await _authenticate_websocket(
        ws, _db(user, session, Organization(id="org-1", is_active=True, status="active"))
    ) is None
    ws.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_websocket_rejects_inactive_organization():
    user = _active_user()
    token = create_access_token(user.id)
    session = UserSession(id=sha256(token.encode()).hexdigest(), user_id=user.id, is_current=True)
    ws = _ws(token)
    assert await _authenticate_websocket(
        ws, _db(user, session, Organization(id="org-1", is_active=False, status="inactive"))
    ) is None
    ws.close.assert_awaited_once()
