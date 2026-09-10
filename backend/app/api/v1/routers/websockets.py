import asyncio
from datetime import UTC, datetime
from hashlib import sha256

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, status
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import apply_organization_context
from app.core.config import settings
from app.core.logging import get_logger
from app.core.security import ALGORITHM
from app.db.session import get_db
from app.models import Organization, User, UserSession
from app.services.auth_service import auth_service

router = APIRouter()
logger = get_logger(__name__)


class ConnectionManager:
    def __init__(self) -> None:
        self.active_connections: dict[WebSocket, tuple[str, str]] = {}

    async def connect(self, websocket: WebSocket, user_id: str, organization_id: str) -> None:
        await websocket.accept()
        self.active_connections[websocket] = (user_id, organization_id)

    def disconnect(self, websocket: WebSocket) -> None:
        self.active_connections.pop(websocket, None)

    async def broadcast(self, message: str, organization_id: str) -> None:
        disconnected: list[WebSocket] = []
        # Sending yields control, so disconnects may mutate the live mapping.
        # Iterate over a snapshot to keep the Redis subscriber alive.
        for connection, (_, connection_org) in list(self.active_connections.items()):
            if connection_org != organization_id:
                continue
            try:
                await connection.send_text(message)
            except Exception:
                disconnected.append(connection)
        for connection in disconnected:
            self.disconnect(connection)


manager = ConnectionManager()


async def _authenticate_websocket(
    websocket: WebSocket,
    db: AsyncSession,
    required_permissions: frozenset[str] = frozenset({"notifications:read"}),
) -> tuple[User, UserSession, str] | None:
    """Authenticate cookie/header JWT with the same session and tenant rules as HTTP."""
    raw_token = websocket.cookies.get(settings.AUTH_COOKIE_NAME)
    authorization = websocket.headers.get("Authorization", "")
    if raw_token:
        origin = websocket.headers.get("Origin")
        socket_scheme = "https" if websocket.url.scheme == "wss" else "http"
        same_origin = origin == f"{socket_scheme}://{websocket.url.netloc}"
        if not origin or (origin not in settings.cors_origins_list and not same_origin):
            await websocket.close(
                code=status.WS_1008_POLICY_VIOLATION, reason="Origin denied"
            )
            return None
    if not raw_token and authorization.lower().startswith("bearer "):
        raw_token = authorization[7:].strip()
    if not raw_token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Missing session")
        return None
    try:
        payload = jwt.decode(
            raw_token,
            settings.SECRET_KEY,
            algorithms=[ALGORITHM],
            issuer=settings.JWT_ISSUER,
            audience=settings.JWT_AUDIENCE,
            options={"require_sub": True, "require_exp": True, "require_iat": True, "require_jti": True},
        )
        if payload.get("token_type") != "access":
            raise JWTError("wrong token type")
    except JWTError:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid session")
        return None

    user = await db.get(User, payload["sub"])
    now = datetime.now(UTC)
    session = await db.get(UserSession, sha256(raw_token.encode()).hexdigest())
    if (
        user is None
        or not user.is_active
        or session is None
        or not session.is_current
        or session.revoked_at is not None
        or (session.expires_at is not None and session.expires_at <= now)
        or session.user_id != user.id
    ):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Session revoked")
        return None

    requested_org = websocket.headers.get("X-Organization-ID") or websocket.query_params.get(
        "organization_id"
    )
    try:
        await apply_organization_context(db, user, requested_org)
    except Exception:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Organization denied")
        return None
    organization_id = getattr(user, "_request_organization_id", None) or user.organization_id
    if not organization_id:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Organization required")
        return None
    permissions = await auth_service.get_user_permissions(db, user)
    if not required_permissions.intersection(permissions):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Permission denied")
        return None
    session.last_used_at = now
    await db.commit()
    return user, session, organization_id


async def _run_socket(
    websocket: WebSocket,
    db: AsyncSession,
    required_permissions: frozenset[str] = frozenset({"notifications:read"}),
) -> None:
    authenticated = await _authenticate_websocket(websocket, db, required_permissions)
    if not authenticated:
        return
    user, session, organization_id = authenticated
    # Keep scalar identifiers across rollback boundaries; rollback expires ORM
    # instances and accessing their attributes could otherwise trigger async IO.
    user_id = user.id
    session_id = session.id
    await manager.connect(websocket, user_id, organization_id)
    try:
        while True:
            current_session = await db.get(UserSession, session_id, populate_existing=True)
            current_user = await db.get(User, user_id, populate_existing=True)
            organization = await db.get(Organization, organization_id, populate_existing=True)
            if (
                current_session is None
                or not current_session.is_current
                or current_session.revoked_at is not None
                or (
                    current_session.expires_at is not None
                    and current_session.expires_at <= datetime.now(UTC)
                )
                or current_user is None
                or not current_user.is_active
                or organization is None
                or not organization.is_active
                or organization.status != "active"
                or (
                    not getattr(current_user, "is_platform_admin", False)
                    and current_user.organization_id != organization_id
                )
            ):
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Authorization revoked")
                return
            permissions = await auth_service.get_user_permissions(db, current_user)
            if not required_permissions.intersection(permissions):
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Permission revoked")
                return
            # End the read transaction before waiting on the network so each
            # long-lived socket does not reserve a pooled database connection.
            await db.rollback()
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30)
            except TimeoutError:
                continue
            if data.strip().lower() == "ping":
                await websocket.send_json({"type": "pong"})
                continue
            # These sockets are subscriptions. Client-originated publishing is
            # intentionally prohibited; system alerts use the permission-gated
            # HTTP endpoint instead.
            await websocket.close(
                code=status.WS_1008_POLICY_VIOLATION,
                reason="Client publishing is not permitted",
            )
            return
    except WebSocketDisconnect:
        return
    except Exception:
        logger.exception("WebSocket session failed")
        try:
            await websocket.close(code=status.WS_1011_INTERNAL_ERROR, reason="Connection failed")
        except Exception:
            logger.debug("WebSocket was already closed during error cleanup", exc_info=True)
    finally:
        manager.disconnect(websocket)


@router.websocket("/notifications")
async def websocket_notifications(websocket: WebSocket, db: AsyncSession = Depends(get_db)) -> None:
    await _run_socket(websocket, db)


@router.websocket("/live-events")
async def websocket_live_events(websocket: WebSocket, db: AsyncSession = Depends(get_db)) -> None:
    await _run_socket(
        websocket,
        db,
        frozenset({"notifications:read", "whatsapp:read_all", "whatsapp:read_assigned"}),
    )
