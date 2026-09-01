from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import require_permission
from app.db.session import get_db
from app.schemas.crm_schemas import (
    BulkActionResponse,
    BulkDeleteRequest,
    CallLogBase,
    CallLogResponse,
    MessageResponse,
)
from app.services.call_service import call_service

router = APIRouter()


@router.get(
    "",
    response_model=list[CallLogResponse],
    summary="List all call logs",
    dependencies=[Depends(require_permission("calls:read"))],
)
async def list_calls(
    page: int = 1,
    limit: int = 20,
    search: str | None = Query(None),
    call_type: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    return await call_service.list_calls(
        db, page=page, limit=limit, search=search, call_type=call_type
    )


@router.post(
    "",
    response_model=CallLogResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Log a new call manually",
    dependencies=[Depends(require_permission("calls:create"))],
)
async def log_call(payload: CallLogBase, db: AsyncSession = Depends(get_db)):
    return await call_service.log_call(db, payload)


@router.post(
    "/trigger-outbound",
    summary="Trigger click-to-dial call via Twilio/telephony",
    dependencies=[Depends(require_permission("calls:create"))],
)
async def trigger_outbound_call(phone_number: str = "+1234567890", contact_id: str = "c-101"):
    return await call_service.trigger_outbound(phone_number, contact_id)


@router.get(
    "/dispositions",
    summary="Get call disposition outcome tags",
    dependencies=[Depends(require_permission("calls:read"))],
)
async def get_call_dispositions():
    return await call_service.get_dispositions()


@router.post(
    "/dispositions",
    response_model=MessageResponse,
    summary="Create call disposition outcome tag",
    dependencies=[Depends(require_permission("calls:create"))],
)
async def create_call_disposition(name: str):
    return await call_service.create_disposition(name)


@router.get(
    "/stats/rep-performance",
    summary="Get telephony statistics per sales rep",
    dependencies=[Depends(require_permission("calls:read"))],
)
async def get_call_stats():
    return await call_service.get_rep_stats()


@router.post(
    "/voicemail",
    response_model=MessageResponse,
    summary="Log voicemail drop execution",
    dependencies=[Depends(require_permission("calls:create"))],
)
async def log_voicemail_drop(contact_id: str = "c-101", voicemail_template_id: str = "vm-1"):
    return await call_service.log_voicemail_drop(contact_id, voicemail_template_id)


@router.post(
    "/bulk-delete",
    response_model=BulkActionResponse,
    summary="Bulk delete call logs",
    dependencies=[Depends(require_permission("calls:delete"))],
)
async def bulk_delete_calls(payload: BulkDeleteRequest, db: AsyncSession = Depends(get_db)):
    return await call_service.bulk_delete(db, payload.ids)


@router.get(
    "/{call_id}",
    response_model=CallLogResponse,
    summary="Get call log details by ID",
    dependencies=[Depends(require_permission("calls:read"))],
)
async def get_call(call_id: str, db: AsyncSession = Depends(get_db)):
    return await call_service.get_call(db, call_id)


@router.delete(
    "/{call_id}",
    response_model=MessageResponse,
    summary="Delete call log by ID",
    dependencies=[Depends(require_permission("calls:delete"))],
)
async def delete_call(call_id: str, db: AsyncSession = Depends(get_db)):
    return await call_service.delete_call(db, call_id)


@router.get(
    "/{call_id}/recording",
    summary="Get MinIO S3 audio recording presigned URL for call",
    dependencies=[Depends(require_permission("calls:recording"))],
)
async def get_call_recording(call_id: str, db: AsyncSession = Depends(get_db)):
    return await call_service.get_recording(db, call_id)


@router.get(
    "/{call_id}/sentiment",
    summary="Get AI voice sentiment analysis & emotion score",
    dependencies=[Depends(require_permission("calls:read"))],
)
async def get_call_sentiment(call_id: str, db: AsyncSession = Depends(get_db)):
    return await call_service.get_sentiment(db, call_id)
