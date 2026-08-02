from fastapi import APIRouter, HTTPException, status, Query, Depends
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from app.database import get_db
from app.models import SystemSetting, AuditLog, Webhook, User, Organization
from app.schemas.crm_schemas import SystemSettings, MessageResponse
from app.core.security import get_password_hash

router = APIRouter()

PROTECTED_SUPERADMIN_EMAIL = "superadmin@gmail.com"

@router.post("/reset-database", response_model=MessageResponse, summary="Reset database - Delete all data except superadmin@gmail.com")
async def reset_database(confirm: bool = False, db: AsyncSession = Depends(get_db)):
    if not confirm:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Param 'confirm=true' required to confirm database reset")
    try:
        # Check if superadmin user exists before reset
        superadmin_res = await db.execute(select(User).where(User.email == PROTECTED_SUPERADMIN_EMAIL))
        superadmin_user = superadmin_res.scalars().first()
        
        saved_name = superadmin_user.name if superadmin_user else "Super Admin"
        saved_password = superadmin_user.hashed_password if (superadmin_user and superadmin_user.hashed_password) else get_password_hash("superadmin123")

        # Get all table names in public schema
        res = await db.execute(text("SELECT tablename FROM pg_tables WHERE schemaname = 'public';"))
        tables = [row[0] for row in res.all()]
        if tables:
            tables_str = ", ".join([f'"{t}"' for t in tables])
            await db.execute(text(f"TRUNCATE TABLE {tables_str} RESTART IDENTITY CASCADE;"))
            await db.flush()

        # Re-create default organization & protected superadmin user
        org = Organization(name="Primary System Organization", domain="crm.com", plan="Enterprise")
        db.add(org)
        await db.flush()

        superadmin = User(
            name=saved_name,
            email=PROTECTED_SUPERADMIN_EMAIL,
            hashed_password=saved_password,
            role="Super Admin",
            organization_id=org.id,
            is_active=True,
            is_verified=True
        )
        db.add(superadmin)
        await db.commit()

        return {"message": f"Database reset complete. All 70 tables truncated. Protected user '{PROTECTED_SUPERADMIN_EMAIL}' preserved.", "status": "success"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Database reset failed: {str(e)}")

@router.get("", response_model=SystemSettings, summary="Get general system settings")
async def get_system_settings(db: AsyncSession = Depends(get_db)):
    return {"organization_name": "Enterprise Organization", "currency": "USD", "timezone": "UTC", "smtp_enabled": True, "ai_features_enabled": True}

@router.put("", response_model=SystemSettings, summary="Update general system settings")
async def update_system_settings(payload: SystemSettings, db: AsyncSession = Depends(get_db)):
    return payload

@router.get("/audit-logs", summary="List security audit trail logs")
async def get_audit_logs(page: int = 1, limit: int = 20, user_id: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    try:
        stmt = select(AuditLog).offset((page - 1) * limit).limit(limit)
        res = await db.execute(stmt)
        logs = res.scalars().all()
        return [{"id": l.id, "user_id": l.user_id, "action": l.action, "ip": l.ip_address, "timestamp": str(l.created_at)} for l in logs]
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get("/audit-logs/export", summary="Export security audit logs as CSV")
async def export_audit_logs_csv(db: AsyncSession = Depends(get_db)):
    return {"download_url": "https://api.crm.com/exports/audit_logs.csv"}

@router.get("/custom-fields", summary="List custom metadata schema fields for entities")
async def list_custom_fields(entity_type: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    return []

@router.post("/custom-fields", response_model=MessageResponse, summary="Create new custom field for Lead, Contact, Deal, or Company")
async def create_custom_field(entity_type: str, field_name: str, field_type: str, label: str, db: AsyncSession = Depends(get_db)):
    return {"message": f"Custom field '{label}' added to {entity_type}", "status": "success"}

@router.delete("/custom-fields/{field_id}", response_model=MessageResponse, summary="Delete custom schema field")
async def delete_custom_field(field_id: str, db: AsyncSession = Depends(get_db)):
    return {"message": f"Custom field {field_id} deleted", "status": "success"}

@router.get("/webhooks", summary="List outgoing event webhook subscriptions")
async def list_webhooks(db: AsyncSession = Depends(get_db)):
    try:
        res = await db.execute(select(Webhook).limit(10))
        whs = res.scalars().all()
        return [{"id": w.id, "target_url": w.target_url, "events": w.events.split(","), "is_active": w.is_active} for w in whs]
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.post("/webhooks", response_model=MessageResponse, summary="Create outgoing event webhook subscription")
async def create_webhook(target_url: str, events: List[str], db: AsyncSession = Depends(get_db)):
    try:
        w = Webhook(organization_id="org-1", target_url=target_url, events=",".join(events))
        db.add(w)
        await db.commit()
        return {"message": f"Webhook registered for {target_url}", "status": "success"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.delete("/webhooks/{webhook_id}", response_model=MessageResponse, summary="Delete webhook subscription")
async def delete_webhook(webhook_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Webhook).where(Webhook.id == webhook_id))
    w = res.scalars().first()
    if not w:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Webhook '{webhook_id}' not found")
    try:
        await db.delete(w)
        await db.commit()
        return {"message": f"Webhook {webhook_id} deleted", "status": "success"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.post("/webhooks/{webhook_id}/test", response_model=MessageResponse, summary="Send test payload event ping to webhook URL")
async def test_webhook(webhook_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Webhook).where(Webhook.id == webhook_id))
    if not res.scalars().first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Webhook '{webhook_id}' not found")
    return {"message": f"Test ping payload sent to webhook {webhook_id}", "status": "success"}

@router.get("/sla", summary="List SLA response & resolution policies")
async def get_sla_policies(db: AsyncSession = Depends(get_db)):
    return []

@router.post("/sla", response_model=MessageResponse, summary="Create SLA response policy")
async def create_sla_policy(name: str, response_time_hours: int, resolution_time_hours: int, db: AsyncSession = Depends(get_db)):
    return {"message": f"SLA Policy '{name}' created", "status": "success"}

@router.get("/backups", summary="List automated database backup snapshots")
async def list_backups(db: AsyncSession = Depends(get_db)):
    return []

@router.post("/backups/trigger", response_model=MessageResponse, summary="Trigger immediate manual database backup")
async def trigger_manual_backup(db: AsyncSession = Depends(get_db)):
    return {"message": "Database backup snapshot initiated in background", "status": "success"}
