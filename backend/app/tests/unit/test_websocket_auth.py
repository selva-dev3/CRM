import hashlib
from unittest.mock import AsyncMock

import pytest

from app.api.v1.routers.websockets import ConnectionManager, _authenticate_websocket
from app.models import Organization, User, UserSession

TEST_TOKEN = "valid-token"  # noqa: S105


def _active_user() -> User:
    return User(
        id="u1",
        name="Alex",
        email="alex@crm.com",
        hashed_password="h",  # noqa: S106
        organization_id="org-1",
        is_active=True,
    )


def _ws(**cookies) -> AsyncMock:
    ws = AsyncMock()
    ws.cookies = cookies
    return ws


def _db_for(user: User | None, session: UserSession | None = None, organization=None) -> AsyncMock:
    db = AsyncMock()
    organization = organization or Organization(
        id="org-1", name="Acme", status="active", is_active=True
    )

    async def get(model, key):
        if model is User:
            return user
        if model is Organization:
            return organization
        if model is UserSession:
            return session
        return None

    db.get.side_effect = get
    return db


@pytest.mark.asyncio
async def test_websocket_accepts_active_cookie_session_with_permission(monkeypatch):
    user = _active_user()
    session = UserSession(
        id=hashlib.sha256(TEST_TOKEN.encode()).hexdigest(), user_id=user.id, is_current=True
    )
    monkeypatch.setattr(
        "app.api.v1.routers.websockets.jwt.decode", lambda *a, **k: {"sub": user.id}
    )
    monkeypatch.setattr(
        "app.api.v1.routers.websockets.auth_service.get_user_permissions",
        AsyncMock(return_value=["notifications:read"]),
    )

    ws = _ws(token=TEST_TOKEN)
    result = await _authenticate_websocket(ws, _db_for(user, session), "notifications:read")

    assert result is user
    ws.close.assert_not_awaited()


@pytest.mark.asyncio
async def test_websocket_rejects_query_only_token():
    ws = _ws()
    ws.query_params = {"token": TEST_TOKEN}

    result = await _authenticate_websocket(ws, AsyncMock(), "notifications:read")

    assert result is None
    ws.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_websocket_rejects_revoked_session(monkeypatch):
    user = _active_user()
    revoked = UserSession(
        id=hashlib.sha256(TEST_TOKEN.encode()).hexdigest(), user_id=user.id, is_current=False
    )
    monkeypatch.setattr(
        "app.api.v1.routers.websockets.jwt.decode", lambda *a, **k: {"sub": user.id}
    )
    ws = _ws(token=TEST_TOKEN)

    result = await _authenticate_websocket(ws, _db_for(user, revoked), "notifications:read")

    assert result is None
    ws.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_websocket_rejects_missing_permission(monkeypatch):
    user = _active_user()
    session = UserSession(
        id=hashlib.sha256(TEST_TOKEN.encode()).hexdigest(), user_id=user.id, is_current=True
    )
    monkeypatch.setattr(
        "app.api.v1.routers.websockets.jwt.decode", lambda *a, **k: {"sub": user.id}
    )
    monkeypatch.setattr(
        "app.api.v1.routers.websockets.auth_service.get_user_permissions",
        AsyncMock(return_value=[]),
    )
    ws = _ws(token=TEST_TOKEN)

    result = await _authenticate_websocket(ws, _db_for(user, session), "notifications:read")

    assert result is None
    ws.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_websocket_rejects_inactive_organization(monkeypatch):
    user = _active_user()
    session = UserSession(
        id=hashlib.sha256(TEST_TOKEN.encode()).hexdigest(), user_id=user.id, is_current=True
    )
    monkeypatch.setattr(
        "app.api.v1.routers.websockets.jwt.decode", lambda *a, **k: {"sub": user.id}
    )
    ws = _ws(token=TEST_TOKEN)
    organization = Organization(id="org-1", name="Acme", status="suspended", is_active=False)

    result = await _authenticate_websocket(
        ws, _db_for(user, session, organization), "notifications:read"
    )

    assert result is None
    ws.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_connection_manager_broadcasts_only_within_organization():
    manager = ConnectionManager()
    org_one = AsyncMock()
    org_two = AsyncMock()

    await manager.connect("org-1", org_one)
    await manager.connect("org-2", org_two)
    await manager.broadcast("org-1", "private event")

    org_one.send_text.assert_awaited_once_with("private event")
    org_two.send_text.assert_not_awaited()
