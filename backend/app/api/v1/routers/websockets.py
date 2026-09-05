import hashlib
from collections import defaultdict

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, status
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_db
from app.core.config import settings
from app.core.logging import get_logger
from app.core.security import ALGORITHM
from app.models import Organization, User, UserSession
from app.services.auth_service import auth_service

router = APIRouter()
logger = get_logger(__name__)


class ConnectionManager:
    """Keep realtime connections isolated by organization."""

    def __init__(self):
        self.connections_by_org: defaultdict[str, set[WebSocket]] = defaultdict(set)

    async def connect(self, organization_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self.connections_by_org[organization_id].add(websocket)

    def disconnect(self, organization_id: str, websocket: WebSocket) -> None:
        connections = self.connections_by_org.get(organization_id)
        if not connections:
            return
        connections.discard(websocket)
        if not connections:
            self.connections_by_org.pop(organization_id, None)

    async def broadcast(self, organization_id: str, message: str) -> None:
        disconnected: list[WebSocket] = []
        for connection in tuple(self.connections_by_org.get(organization_id, ())):
            try:
                await connection.send_text(message)
            except Exception:
                disconnected.append(connection)
        for connection in disconnected:
            self.disconnect(organization_id, connection)


manager = ConnectionManager()


async def _reject(websocket: WebSocket, reason: str) -> None:
    await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason=reason)


async def _authenticate_websocket(
    websocket: WebSocket, db: AsyncSession, required_permission: str
) -> User | None:
    """Authenticate using the HttpOnly access cookie and current DB session."""
    raw_token = websocket.cookies.get(settings.AUTH_COOKIE_NAME)
    if not raw_token:
        await _reject(websocket, "Missing authentication cookie")
        return None

    try:
        payload = jwt.decode(raw_token, settings.SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        await _reject(websocket, "Invalid or expired token")
        return None

    user_id = payload.get("sub")
    if not user_id:
        await _reject(websocket, "Invalid token payload")
        return None

    user = await db.get(User, user_id)
    if not user or not user.is_active or not user.organization_id:
        await _reject(websocket, "User account is missing or inactive")
        return None

    organization = await db.get(Organization, user.organization_id)
    if not organization or not organization.is_active or organization.status != "active":
        await _reject(websocket, "User organization is inactive or unavailable")
        return None

    session = await db.get(UserSession, hashlib.sha256(raw_token.encode("utf-8")).hexdigest())
    if not session or not session.is_current or session.user_id != user.id:
        await _reject(websocket, "Session has been revoked")
        return None

    permissions = await auth_service.get_user_permissions(db, user)
    if required_permission not in permissions:
        await _reject(websocket, "Missing required permission")
        return None

    return user


async def _handle_client_message(websocket: WebSocket, *, channel: str) -> None:
    """Do not allow clients to publish arbitrary server-wide events."""
    data = await websocket.receive_text()
    if not data or not data.strip():
        await websocket.send_json({"error": "Empty message received"})
        return
    await websocket.send_json(
        {"error": "Client event publishing is not permitted", "channel": channel}
    )


@router.websocket("/notifications")
async def websocket_notifications(websocket: WebSocket, db: AsyncSession = Depends(get_db)):
    user = await _authenticate_websocket(websocket, db, "notifications:read")
    if not user:
        return
    organization_id = user.organization_id
    await manager.connect(organization_id, websocket)
    try:
        while True:
            await _handle_client_message(websocket, channel="notifications")
    except WebSocketDisconnect:
        manager.disconnect(organization_id, websocket)
    except Exception:
        manager.disconnect(organization_id, websocket)
        logger.warning("Notification websocket failed", exc_info=True)


@router.websocket("/live-events")
async def websocket_live_events(websocket: WebSocket, db: AsyncSession = Depends(get_db)):
    user = await _authenticate_websocket(websocket, db, "notifications:read")
    if not user:
        return
    organization_id = user.organization_id
    await manager.connect(organization_id, websocket)
    try:
        while True:
            await _handle_client_message(websocket, channel="live-events")
    except WebSocketDisconnect:
        manager.disconnect(organization_id, websocket)
    except Exception:
        manager.disconnect(organization_id, websocket)
        logger.warning("Live-events websocket failed", exc_info=True)
