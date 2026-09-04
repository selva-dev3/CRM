from fastapi import APIRouter, Body, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user, get_current_user_optional, require_permission
from app.db.session import get_db
from app.models import User
from app.schemas.crm_schemas import CustomFieldResponse, MessageResponse, SystemSettings
from app.services.settings_service import settings_service

router = APIRouter()


class CreateWebhookPayload(BaseModel):
    target_url: str | None = None
    events: list[str] | None = []


class CreateCustomFieldPayload(BaseModel):
    entity_type: str | None = "Lead"
    field_name: str | None = None
    field_type: str | None = "text"
    label: str | None = None
    options: list[str] = Field(default_factory=list)


class CreateSlaPayload(BaseModel):
    name: str | None = None
    response_time_hours: int | None = 1
    resolution_time_hours: int | None = 24


@router.post(
    "/reset-database",
    response_model=MessageResponse,
    summary="Reset database - Delete all data except superadmin@gmail.com",
    dependencies=[Depends(require_permission("settings:update"))],
)
async def reset_database(confirm: bool = False, db: AsyncSession = Depends(get_db)):
    return await settings_service.reset_database(db, confirm)


@router.get(
    "",
    response_model=SystemSettings,
    summary="Get general system settings",
    dependencies=[Depends(require_permission("settings:read"))],
)
async def get_system_settings(
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
):
    return await settings_service.get_system_settings(db, current_user)


@router.put(
    "",
    response_model=SystemSettings,
    summary="Update general system settings",
    dependencies=[Depends(require_permission("settings:update"))],
)
async def update_system_settings(
    payload: SystemSettings,
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
):
    return await settings_service.update_system_settings(db, payload, current_user)


@router.get(
    "/audit-logs",
    summary="List security audit trail logs",
    dependencies=[Depends(require_permission("settings:security"))],
)
async def get_audit_logs(page: int = 1, limit: int = 20, db: AsyncSession = Depends(get_db)):
    return await settings_service.list_audit_logs(db, page=page, limit=limit)


@router.get(
    "/audit-logs/export",
    summary="Export security audit logs as CSV",
    dependencies=[Depends(require_permission("settings:security"))],
)
async def export_audit_logs_csv(db: AsyncSession = Depends(get_db)):
    return await settings_service.export_audit_logs_csv(db)


@router.get(
    "/custom-fields",
    response_model=list[CustomFieldResponse],
    summary="List custom metadata schema fields for entities",
    dependencies=[Depends(require_permission("settings:read"))],
)
async def list_custom_fields(
    entity_type: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await settings_service.list_custom_fields(db, entity_type, current_user)


@router.post(
    "/custom-fields",
    response_model=MessageResponse,
    summary="Create new custom field for Lead, Contact, Deal, or Company",
    dependencies=[Depends(require_permission("settings:update"))],
)
async def create_custom_field(
    payload: CreateCustomFieldPayload | None = Body(None),
    entity_type: str | None = Query(None),
    field_name: str | None = Query(None),
    field_type: str | None = Query(None),
    label: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ent = (payload and payload.entity_type) or entity_type or "Lead"
    fname = (payload and payload.field_name) or field_name or "custom_field"
    ftype = (payload and payload.field_type) or field_type or "text"
    lbl = (payload and payload.label) or label or fname
    options = payload.options if payload else []
    return await settings_service.create_custom_field(
        db,
        entity_type=ent,
        field_name=fname,
        field_type=ftype,
        label=lbl,
        options=options,
        current_user=current_user,
    )


@router.delete(
    "/custom-fields/{field_id}",
    response_model=MessageResponse,
    summary="Delete custom schema field",
    dependencies=[Depends(require_permission("settings:update"))],
)
async def delete_custom_field(
    field_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await settings_service.delete_custom_field(db, field_id, current_user)


@router.get(
    "/webhooks",
    summary="List outgoing event webhook subscriptions",
    dependencies=[Depends(require_permission("settings:read"))],
)
async def list_webhooks(
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
):
    return await settings_service.list_webhooks(db, current_user)


@router.post(
    "/webhooks",
    response_model=MessageResponse,
    summary="Create outgoing event webhook subscription",
    dependencies=[Depends(require_permission("settings:update"))],
)
async def create_webhook(
    payload: CreateWebhookPayload | None = Body(None),
    target_url: str | None = Query(None),
    events: list[str] | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
):
    url = (payload and payload.target_url) or target_url
    ev_list = (payload and payload.events) or events or []
    return await settings_service.create_webhook(
        db, target_url=url, events=ev_list, current_user=current_user
    )


@router.delete(
    "/webhooks/{webhook_id}",
    response_model=MessageResponse,
    summary="Delete webhook subscription",
    dependencies=[Depends(require_permission("settings:update"))],
)
async def delete_webhook(webhook_id: str, db: AsyncSession = Depends(get_db)):
    return await settings_service.delete_webhook(db, webhook_id)


@router.post(
    "/webhooks/{webhook_id}/test",
    response_model=MessageResponse,
    summary="Send test payload event ping to webhook URL",
    dependencies=[Depends(require_permission("settings:update"))],
)
async def test_webhook(webhook_id: str, db: AsyncSession = Depends(get_db)):
    return await settings_service.test_webhook(webhook_id)


@router.get(
    "/sla",
    summary="List SLA response & resolution policies",
    dependencies=[Depends(require_permission("settings:read"))],
)
async def get_sla_policies(
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
):
    return await settings_service.list_sla_policies(db, current_user)


@router.post(
    "/sla",
    response_model=MessageResponse,
    summary="Create SLA response policy",
    dependencies=[Depends(require_permission("settings:update"))],
)
async def create_sla_policy(
    payload: CreateSlaPayload | None = Body(None),
    name: str | None = Query(None),
    response_time_hours: int | None = Query(None),
    resolution_time_hours: int | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
):
    s_name = (payload and payload.name) or name or "Standard SLA Policy"
    resp_time = (payload and payload.response_time_hours) or response_time_hours or 1
    reso_time = (payload and payload.resolution_time_hours) or resolution_time_hours or 24
    return await settings_service.create_sla_policy(
        db,
        name=s_name,
        response_time_hours=resp_time,
        resolution_time_hours=reso_time,
        current_user=current_user,
    )


@router.get(
    "/backups",
    summary="List automated database backup snapshots",
    dependencies=[Depends(require_permission("settings:read"))],
)
async def list_backups(db: AsyncSession = Depends(get_db)):
    return await settings_service.list_backups()


@router.post(
    "/backups/trigger",
    response_model=MessageResponse,
    summary="Trigger immediate manual database backup",
    dependencies=[Depends(require_permission("settings:update"))],
)
async def trigger_manual_backup(db: AsyncSession = Depends(get_db)):
    return await settings_service.trigger_manual_backup()
