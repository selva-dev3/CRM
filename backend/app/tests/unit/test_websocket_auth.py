from unittest.mock import AsyncMock, MagicMock

import pytest

from app.api.v1.routers.websockets import _authenticate_websocket
from app.models import User


def _active_user() -> User:
    return User(
        id="u1",
        name="Alex",
        email="alex@crm.com",
        hashed_password="h",
        organization_id="org-1",
        is_active=True,
    )


def _db_execute_returning(user) -> AsyncMock:
    scalars = MagicMock()
    scalars.first.return_value = user
    result = MagicMock()
    result.scalars.return_value = scalars
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)
    return db


def _ws(**query) -> AsyncMock:
    ws = AsyncMock()
    ws.query_params = query
    return ws


@pytest.mark.asyncio
async def test_websocket_accepts_existing_active_user(monkeypatch):
    monkeypatch.setattr(
        "app.api.v1.routers.websockets.jwt.decode", lambda *a, **k: {"sub": "u1"}
    )
    db = _db_execute_returning(_active_user())
    ws = _ws(token="valid-token")

    assert await _authenticate_websocket(ws, db) is True
    ws.close.assert_not_awaited()


@pytest.mark.asyncio
async def test_websocket_rejects_missing_token():
    ws = _ws()
    db = AsyncMock()

    assert await _authenticate_websocket(ws, db) is False
    ws.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_websocket_rejects_invalid_jwt(monkeypatch):
    from jose import JWTError

    def _raise(*a, **k):
        raise JWTError

    monkeypatch.setattr("app.api.v1.routers.websockets.jwt.decode", _raise)
    ws = _ws(token="bad-token")
    db = AsyncMock()

    assert await _authenticate_websocket(ws, db) is False
    ws.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_websocket_rejects_payload_without_sub(monkeypatch):
    monkeypatch.setattr(
        "app.api.v1.routers.websockets.jwt.decode", lambda *a, **k: {}
    )
    ws = _ws(token="no-sub-token")
    db = AsyncMock()

    assert await _authenticate_websocket(ws, db) is False
    ws.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_websocket_rejects_unknown_user(monkeypatch):
    monkeypatch.setattr(
        "app.api.v1.routers.websockets.jwt.decode", lambda *a, **k: {"sub": "ghost"}
    )
    db = _db_execute_returning(None)
    ws = _ws(token="valid-token")

    assert await _authenticate_websocket(ws, db) is False
    ws.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_websocket_rejects_inactive_user(monkeypatch):
    monkeypatch.setattr(
        "app.api.v1.routers.websockets.jwt.decode", lambda *a, **k: {"sub": "u1"}
    )
    inactive = _active_user()
    inactive.is_active = False
    db = _db_execute_returning(inactive)
    ws = _ws(token="valid-token")

    assert await _authenticate_websocket(ws, db) is False
    ws.close.assert_awaited_once()