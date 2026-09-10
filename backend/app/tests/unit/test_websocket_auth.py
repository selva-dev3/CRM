from datetime import UTC, datetime, timedelta
from hashlib import sha256
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.api.v1.routers.websockets import (
    ConnectionManager,
    _authenticate_websocket,
    _run_socket,
)
from app.core.security import create_access_token
from app.models import Organization, User, UserSession


def _active_user(**overrides) -> User:
    values = {
        "id": "u1",
        "name": "Alex",
        "email": "alex@crm.com",
        "hashed_password": "test-hash",  # noqa: S106 - inert model fixture
        "organization_id": "org-1",
        "is_active": True,
        "is_platform_admin": True,
    }
    values.update(overrides)
    return User(**values)


def _ws(token: str | None = None, organization_id: str = "org-1") -> AsyncMock:
    ws = AsyncMock()
    ws.cookies = {"token": token} if token else {}
    ws.headers = {"Origin": "http://localhost:3000"}
    ws.query_params = {"organization_id": organization_id}
    ws.url.scheme = "ws"
    ws.url.netloc = "localhost:8000"
    return ws


def _db(
    user: User | None, session: UserSession | None, organization: Organization | None
) -> AsyncMock:
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
async def test_live_websocket_accepts_whatsapp_read_permission(monkeypatch):
    user = _active_user()
    token = create_access_token(user.id)
    session = UserSession(id=sha256(token.encode()).hexdigest(), user_id=user.id, is_current=True)
    monkeypatch.setattr(
        "app.api.v1.routers.websockets.auth_service.get_user_permissions",
        AsyncMock(return_value=["whatsapp:read_assigned"]),
    )

    result = await _authenticate_websocket(
        _ws(token),
        _db(user, session, Organization(id="org-1", is_active=True, status="active")),
        frozenset({"notifications:read", "whatsapp:read_all", "whatsapp:read_assigned"}),
    )

    assert result is not None


@pytest.mark.asyncio
async def test_websocket_platform_admin_uses_explicit_organization_context():
    user = _active_user(organization_id=None)
    token = create_access_token(user.id)
    session = UserSession(id=sha256(token.encode()).hexdigest(), user_id=user.id, is_current=True)

    result = await _authenticate_websocket(
        _ws(token, organization_id="org-1"),
        _db(user, session, Organization(id="org-1", is_active=True, status="active")),
    )

    assert result is not None
    assert result[2] == "org-1"
    assert user._organization_id is None


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
async def test_websocket_rejects_cross_site_cookie_session():
    ws = _ws("unused-token")
    ws.headers = {"Origin": "https://attacker.example"}

    assert await _authenticate_websocket(ws, AsyncMock()) is None
    ws.close.assert_awaited_once_with(code=1008, reason="Origin denied")


@pytest.mark.asyncio
async def test_websocket_rejects_revoked_session():
    user = _active_user()
    token = create_access_token(user.id)
    session = UserSession(id=sha256(token.encode()).hexdigest(), user_id=user.id, is_current=False)
    ws = _ws(token)
    assert (
        await _authenticate_websocket(
            ws, _db(user, session, Organization(id="org-1", is_active=True, status="active"))
        )
        is None
    )
    ws.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_websocket_rejects_inactive_user():
    user = _active_user(is_active=False)
    token = create_access_token(user.id)
    session = UserSession(id=sha256(token.encode()).hexdigest(), user_id=user.id, is_current=True)
    ws = _ws(token)
    assert (
        await _authenticate_websocket(
            ws, _db(user, session, Organization(id="org-1", is_active=True, status="active"))
        )
        is None
    )
    ws.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_websocket_rejects_inactive_organization():
    user = _active_user()
    token = create_access_token(user.id)
    session = UserSession(id=sha256(token.encode()).hexdigest(), user_id=user.id, is_current=True)
    ws = _ws(token)
    assert (
        await _authenticate_websocket(
            ws, _db(user, session, Organization(id="org-1", is_active=False, status="inactive"))
        )
        is None
    )
    ws.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_subscription_socket_rejects_client_publish(monkeypatch):
    user = _active_user(is_platform_admin=False)
    session = UserSession(id="session-1", user_id=user.id, is_current=True)
    organization = Organization(id="org-1", is_active=True, status="active")
    websocket = _ws()
    websocket.receive_text = AsyncMock(return_value='{"type":"broadcast","message":"x"}')
    db = AsyncMock()

    async def get(model, _key, **_kwargs):
        return {User: user, UserSession: session, Organization: organization}[model]

    db.get.side_effect = get
    monkeypatch.setattr(
        "app.api.v1.routers.websockets._authenticate_websocket",
        AsyncMock(return_value=(user, session, "org-1")),
    )
    monkeypatch.setattr(
        "app.api.v1.routers.websockets.auth_service.get_user_permissions",
        AsyncMock(return_value=["notifications:read"]),
    )

    await _run_socket(websocket, db)

    websocket.close.assert_awaited_once_with(code=1008, reason="Client publishing is not permitted")
    websocket.send_text.assert_not_awaited()


@pytest.mark.asyncio
async def test_subscription_socket_revalidates_revoked_permission(monkeypatch):
    user = _active_user(is_platform_admin=False)
    session = UserSession(id="session-1", user_id=user.id, is_current=True)
    organization = Organization(id="org-1", is_active=True, status="active")
    websocket = _ws()
    db = AsyncMock()

    async def get(model, _key, **_kwargs):
        return {User: user, UserSession: session, Organization: organization}[model]

    db.get.side_effect = get
    monkeypatch.setattr(
        "app.api.v1.routers.websockets._authenticate_websocket",
        AsyncMock(return_value=(user, session, "org-1")),
    )
    monkeypatch.setattr(
        "app.api.v1.routers.websockets.auth_service.get_user_permissions",
        AsyncMock(return_value=[]),
    )

    await _run_socket(websocket, db)

    websocket.close.assert_awaited_once_with(code=1008, reason="Permission revoked")
    websocket.receive_text.assert_not_awaited()


@pytest.mark.asyncio
async def test_subscription_socket_closes_when_session_expires(monkeypatch):
    user = _active_user(is_platform_admin=False)
    session = UserSession(
        id="session-1",
        user_id=user.id,
        is_current=True,
        expires_at=datetime.now(UTC) - timedelta(seconds=1),
    )
    organization = Organization(id="org-1", is_active=True, status="active")
    websocket = _ws()
    db = AsyncMock()

    async def get(model, _key, **_kwargs):
        return {User: user, UserSession: session, Organization: organization}[model]

    db.get.side_effect = get
    monkeypatch.setattr(
        "app.api.v1.routers.websockets._authenticate_websocket",
        AsyncMock(return_value=(user, session, "org-1")),
    )

    await _run_socket(websocket, db)

    websocket.close.assert_awaited_once_with(code=1008, reason="Authorization revoked")
    websocket.receive_text.assert_not_awaited()


@pytest.mark.asyncio
async def test_subscription_socket_keeps_identifiers_across_rollback(monkeypatch):
    user = SimpleNamespace(
        id="u1",
        is_active=True,
        is_platform_admin=False,
        organization_id="org-1",
    )
    session = SimpleNamespace(
        id="session-1",
        is_current=True,
        revoked_at=None,
        expires_at=None,
    )
    organization = SimpleNamespace(id="org-1", is_active=True, status="active")
    websocket = _ws()
    db = AsyncMock()
    lookup_keys: list[tuple[type, str | None]] = []

    async def get(model, key, **_kwargs):
        lookup_keys.append((model, key))
        return {User: user, UserSession: session, Organization: organization}[model]

    rollback_count = 0

    async def rollback():
        nonlocal rollback_count
        rollback_count += 1
        if rollback_count == 1:
            user.id = None
            session.id = None

    receive_count = 0

    async def wait_for(awaitable, *, timeout):
        nonlocal receive_count
        assert timeout == 30
        awaitable.close()
        receive_count += 1
        if receive_count == 1:
            raise TimeoutError
        return "publish"

    db.get.side_effect = get
    db.rollback.side_effect = rollback
    monkeypatch.setattr(
        "app.api.v1.routers.websockets._authenticate_websocket",
        AsyncMock(return_value=(user, session, "org-1")),
    )
    monkeypatch.setattr(
        "app.api.v1.routers.websockets.auth_service.get_user_permissions",
        AsyncMock(return_value=["notifications:read"]),
    )
    monkeypatch.setattr("app.api.v1.routers.websockets.asyncio.wait_for", wait_for)

    await _run_socket(websocket, db)

    assert [key for model, key in lookup_keys if model is User] == ["u1", "u1"]
    assert [key for model, key in lookup_keys if model is UserSession] == [
        "session-1",
        "session-1",
    ]
    websocket.close.assert_awaited_once_with(
        code=1008,
        reason="Client publishing is not permitted",
    )


@pytest.mark.asyncio
async def test_websocket_broadcast_is_tenant_isolated():
    manager = ConnectionManager()
    org_a = AsyncMock()
    org_b = AsyncMock()
    manager.active_connections = {
        org_a: ("user-a", "org-a"),
        org_b: ("user-b", "org-b"),
    }

    await manager.broadcast("update", "org-a")

    org_a.send_text.assert_awaited_once_with("update")
    org_b.send_text.assert_not_awaited()


@pytest.mark.asyncio
async def test_websocket_broadcast_tolerates_concurrent_disconnect():
    manager = ConnectionManager()
    org_a = AsyncMock()
    org_b = AsyncMock()
    manager.active_connections = {
        org_a: ("user-a", "org-a"),
        org_b: ("user-b", "org-a"),
    }
    org_a.send_text.side_effect = lambda _message: manager.disconnect(org_b)

    await manager.broadcast("update", "org-a")

    org_a.send_text.assert_awaited_once_with("update")
