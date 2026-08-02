from fastapi import APIRouter
from app.schemas.crm_schemas import SystemSettings

router = APIRouter()

@router.get("/", response_model=SystemSettings, summary="Get organization system settings")
async def get_settings():
    return {
        "organization_name": "Acme Global",
        "currency": "USD",
        "timezone": "UTC",
        "smtp_enabled": True,
        "ai_features_enabled": True
    }

@router.put("/", response_model=SystemSettings, summary="Update system settings")
async def update_settings(payload: SystemSettings):
    return payload
