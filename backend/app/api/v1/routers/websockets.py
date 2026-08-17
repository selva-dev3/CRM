from typing import List

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, status
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import ALGORITHM
from app.db.session import get_db
from app.models import User

router = APIRouter()

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                disconnected.append(connection)
        for conn in disconnected:
            self.disconnect(conn)

manager = ConnectionManager()


async def _authenticate_websocket(websocket: WebSocket, db: AsyncSession) -> bool:
    """Validate the JWT access token on the websocket connection.

    Accepts the token via the ``token`` query parameter (e.g. /ws/notifications?token=...).
    Returns True only when the token decodes to an existing, active user account;
    otherwise closes the socket with 4401.
    """
    raw_token = websocket.query_params.get("token")
    if not raw_token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Missing token")
        return False
    try:
        payload = jwt.decode(raw_token, settings.SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid or expired token")
        return False
    user_id = payload.get("sub")
    if not user_id:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token payload")
        return False
    res = await db.execute(select(User).where(User.id == user_id))
    user = res.scalars().first()
    if not user or not user.is_active:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="User account is missing or inactive")
        return False
    return True

@router.websocket("/notifications")
async def websocket_notifications(websocket: WebSocket, db: AsyncSession = Depends(get_db)):
    if not await _authenticate_websocket(websocket, db):
        return
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            if not data or len(data.strip()) == 0:
                await websocket.send_json({"error": "Empty message received"})
                continue
            await manager.broadcast(f"Real-time update: {data}")
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        manager.disconnect(websocket)
        try:
            await websocket.close(code=status.WS_1011_INTERNAL_ERROR, reason=str(e))
        except Exception:
            pass

@router.websocket("/live-events")
async def websocket_live_events(websocket: WebSocket, db: AsyncSession = Depends(get_db)):
    if not await _authenticate_websocket(websocket, db):
        return
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            await manager.broadcast(f"Event: {data}")
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)
