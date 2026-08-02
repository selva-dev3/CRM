from fastapi import APIRouter
from app.api.v1.endpoints import auth, leads, ai, websockets

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(leads.router, prefix="/leads", tags=["Lead Management"])
api_router.include_router(ai.router, prefix="/ai", tags=["AI Integrations"])
api_router.include_router(websockets.router, prefix="/ws", tags=["Real-time WebSockets"])
