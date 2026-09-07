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
from app.models import User, UserSession
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
        for connection, (_, connection_org) in self.active_connections.items():
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
    websocket: WebSocket, db: AsyncSession
) -> tuple[User, UserSession, str] | None:
    """Authenticate cookie/header JWT with the same session and tenant rules as HTTP."""
    raw_token = websocket.cookies.get(settings.AUTH_COOKIE_NAME)
    authorization = websocket.headers.get("Authorization", "")
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
    organization_id = user.organization_id
    if not organization_id:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Organization required")
        return None
    permissions = await auth_service.get_user_permissions(db, user)
    if "notifications:read" not in permissions and not getattr(user, "is_platform_admin", False):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Permission denied")
        return None
    session.last_used_at = now
    return user, session, organization_id


async def _run_socket(websocket: WebSocket, db: AsyncSession, prefix: str) -> None:
    authenticated = await _authenticate_websocket(websocket, db)
    if not authenticated:
        return
    user, session, organization_id = authenticated
    await manager.connect(websocket, user.id, organization_id)
    try:
        while True:
            data = await websocket.receive_text()
            current = await db.get(UserSession, session.id)
            if current is None or not current.is_current or current.revoked_at is not None:
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Session revoked")
                return
            if not data.strip():
                await websocket.send_json({"error": "Empty message received"})
                continue
            await manager.broadcast(f"{prefix}: {data}", organization_id)
    except WebSocketDisconnect:
        return
    except Exception:
        logger.exception("WebSocket session failed")
        try:
            await websocket.close(code=status.WS_1011_INTERNAL_ERROR, reason="Connection failed")
        except Exception:
            pass
    finally:
        manager.disconnect(websocket)


@router.websocket("/notifications")
async def websocket_notifications(websocket: WebSocket, db: AsyncSession = Depends(get_db)) -> None:
    await _run_socket(websocket, db, "Real-time update")


@router.websocket("/live-events")
async def websocket_live_events(websocket: WebSocket, db: AsyncSession = Depends(get_db)) -> None:
    await _run_socket(websocket, db, "Event")
