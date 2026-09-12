from fastapi import APIRouter, Depends, File, Header, Query, Request, Response, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user, require_permission
from app.core.errors import APIException
from app.db.session import get_db
from app.models import User
from app.schemas.crm_schemas import (
    BulkActionResponse,
    BulkDeleteRequest,
    CallLogBase,
    CallLogResponse,
    CustomFieldDefinition,
    DocumentResponse,
    EmailResponse,
    EmailSendRequest,
    LeadConvertRequest,
    LeadCreate,
    LeadDisqualificationRequest,
    LeadQualificationRequest,
    LeadResponse,
    LeadTimelineEvent,
    LeadUpdate,
    MessageResponse,
    NoteResponse,
    TaskCreate,
    TaskResponse,
)
from app.services.ai_domain_service import ai_domain_service
from app.services.call_service import call_service
from app.services.lead_service import (
    LEAD_SOURCES,
    LEAD_STATUSES,
    lead_service,
)
from app.services.org_service import organization_service


async def require_lead_record_access(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    lead_id = request.path_params.get("lead_id")
    if not lead_id:
        return
    organization_id = await organization_service.resolve_valid_org_id(db, current_user)
    await lead_service.require_lead(
        db,
        lead_id,
        organization_id=organization_id,
        current_user=current_user,
    )


router = APIRouter(dependencies=[Depends(require_lead_record_access)])


@router.get(
    "",
    response_model=list[LeadResponse],
    summary="List all leads with pagination & search",
    dependencies=[Depends(require_permission("leads:read"))],
)
async def list_leads(
    response: Response,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: str | None = Query(None),
    lead_status: str | None = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    organization_id = await organization_service.resolve_valid_org_id(db, current_user)
    leads = await lead_service.list_leads(
        db,
        page=page,
        limit=limit,
        organization_id=organization_id,
        search=search,
        lead_status=lead_status,
        current_user=current_user,
    )
    total = await lead_service.count_leads(
        db,
        organization_id=organization_id,
        search=search,
        lead_status=lead_status,
        current_user=current_user,
    )
    response.headers["X-Total-Count"] = str(total)
    return leads


@router.post(
    "/bulk/delete",
    response_model=BulkActionResponse,
    summary="Bulk delete leads",
    dependencies=[Depends(require_permission("leads:bulk_delete"))],
)
async def bulk_delete_leads(
    payload: BulkDeleteRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    organization_id = await organization_service.resolve_valid_org_id(db, current_user)
    return await lead_service.bulk_delete(
        db, payload.ids, organization_id=organization_id, current_user=current_user
    )


@router.post(
    "/bulk/archive",
    response_model=BulkActionResponse,
    summary="Bulk archive leads",
    dependencies=[Depends(require_permission("leads:bulk_update"))],
)
async def bulk_archive_leads(
    payload: BulkDeleteRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    organization_id = await organization_service.resolve_valid_org_id(db, current_user)
    return await lead_service.bulk_archive(
        db, payload.ids, organization_id=organization_id, actor_id=current_user.id,
        current_user=current_user,
    )


@router.post(
    "",
    response_model=LeadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new lead",
    dependencies=[Depends(require_permission("leads:create"))],
)
async def create_lead(
    payload: LeadCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await lead_service.create_lead(db, payload, current_user)


@router.get(
    "/custom-fields",
    response_model=list[CustomFieldDefinition],
    summary="List custom fields available for leads",
    dependencies=[Depends(require_permission("leads:read"))],
)
async def list_lead_custom_fields(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await lead_service.list_custom_fields(db, current_user)


@router.get(
    "/sources",
    summary="Get all lead sources",
    dependencies=[Depends(require_permission("leads:read"))],
)
async def get_lead_sources():
    return LEAD_SOURCES


@router.post(
    "/sources",
    response_model=MessageResponse,
    summary="Create new lead source",
    dependencies=[Depends(require_permission("leads:create"))],
)
async def create_lead_source(source_name: str):
    raise APIException(
        message="Custom lead sources are not supported",
        code="CUSTOM_LEAD_SOURCES_UNAVAILABLE",
        status_code=501,
    )


@router.get(
    "/statuses",
    summary="Get all lead status stages",
    dependencies=[Depends(require_permission("leads:read"))],
)
async def get_lead_statuses():
    return LEAD_STATUSES


@router.post(
    "/statuses",
    response_model=MessageResponse,
    summary="Create new lead status stage",
    dependencies=[Depends(require_permission("leads:create"))],
)
async def create_lead_status(status_name: str):
    raise APIException(
        message="Custom lead statuses are not supported",
        code="CUSTOM_LEAD_STATUSES_UNAVAILABLE",
        status_code=501,
    )


@router.post(
    "/check-duplicates",
    summary="Check duplicate lead by email or phone",
    dependencies=[Depends(require_permission("leads:read"))],
)
async def check_duplicate_lead(
    email: str,
    phone: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    organization_id = await organization_service.resolve_valid_org_id(db, current_user)
    return await lead_service.check_duplicate(db, email, organization_id=organization_id)


@router.get(
    "/analytics/by-source",
    summary="Get lead conversion analytics by source",
    dependencies=[Depends(require_permission("leads:read"))],
)
async def lead_analytics_by_source():
    raise APIException(
        message="Lead source analytics are not available from this endpoint",
        code="LEAD_SOURCE_ANALYTICS_UNAVAILABLE",
        status_code=501,
    )


@router.get(
    "/export/csv",
    summary="Export leads list as CSV",
    dependencies=[Depends(require_permission("leads:export"))],
)
async def export_leads_csv():
    raise APIException(message="Lead CSV export is not implemented", status_code=501)


@router.post(
    "/import/csv",
    response_model=MessageResponse,
    summary="Import leads from CSV file",
    dependencies=[Depends(require_permission("leads:import"))],
)
async def import_leads_csv():
    raise APIException(message="Lead CSV import is not implemented", status_code=501)


@router.post(
    "/bulk-update-status",
    response_model=BulkActionResponse,
    summary="Bulk update lead status",
    dependencies=[Depends(require_permission("leads:bulk_update"))],
)
async def bulk_update_lead_status(
    payload: BulkDeleteRequest,
    status_value: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    organization_id = await organization_service.resolve_valid_org_id(db, current_user)
    return await lead_service.bulk_update_status(
        db,
        payload.ids,
        status_value,
        organization_id=organization_id,
        actor_id=current_user.id,
        current_user=current_user,
    )


@router.get(
    "/{lead_id}",
    response_model=LeadResponse,
    summary="Get lead details by ID",
    dependencies=[Depends(require_permission("leads:read"))],
)
async def get_lead(
    lead_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    organization_id = await organization_service.resolve_valid_org_id(db, current_user)
    return await lead_service.get_lead(
        db, lead_id, organization_id=organization_id, current_user=current_user
    )


@router.put(
    "/{lead_id}",
    response_model=LeadResponse,
    summary="Update lead by ID",
    dependencies=[Depends(require_permission("leads:update"))],
)
async def update_lead(
    lead_id: str,
    payload: LeadUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await lead_service.update_lead(db, lead_id, payload, current_user)


@router.delete(
    "/{lead_id}",
    response_model=MessageResponse,
    summary="Delete lead by ID",
    dependencies=[Depends(require_permission("leads:delete"))],
)
async def delete_lead(
    lead_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    organization_id = await organization_service.resolve_valid_org_id(db, current_user)
    return await lead_service.delete_lead(
        db, lead_id, organization_id=organization_id, current_user=current_user
    )


@router.post(
    "/{lead_id}/qualify",
    response_model=LeadResponse,
    summary="Qualify an active lead",
    dependencies=[Depends(require_permission("leads:update"))],
)
async def qualify_lead(
    lead_id: str,
    payload: LeadQualificationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await lead_service.qualify_lead(db, lead_id, payload, current_user)


@router.post(
    "/{lead_id}/disqualify",
    response_model=LeadResponse,
    summary="Disqualify an active lead",
    dependencies=[Depends(require_permission("leads:update"))],
)
async def disqualify_lead(
    lead_id: str,
    payload: LeadDisqualificationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await lead_service.disqualify_lead(db, lead_id, payload, current_user)


@router.post(
    "/{lead_id}/reopen",
    response_model=LeadResponse,
    summary="Reopen a disqualified lead",
    dependencies=[Depends(require_permission("leads:update"))],
)
async def reopen_lead(
    lead_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await lead_service.reopen_lead(db, lead_id, current_user)


@router.post(
    "/{lead_id}/convert",
    summary="Convert lead to Deal, Contact, and Company",
    dependencies=[Depends(require_permission("leads:convert"))],
)
async def convert_lead(
    lead_id: str,
    payload: LeadConvertRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await lead_service.convert_lead(db, lead_id, payload, current_user)


@router.post(
    "/{lead_id}/assign",
    response_model=MessageResponse,
    summary="Assign lead to specific sales rep",
    dependencies=[Depends(require_permission("leads:assign"))],
)
async def assign_lead(
    lead_id: str,
    user_id: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    organization_id = await organization_service.resolve_valid_org_id(db, current_user)
    return await lead_service.assign_lead(
        db,
        lead_id,
        user_id,
        organization_id=organization_id,
        actor_id=current_user.id,
    )


@router.post(
    "/{lead_id}/score",
    summary="Recalculate AI score for lead",
    dependencies=[
        Depends(require_permission("leads:update")),
        Depends(require_permission("ai:generate")),
    ],
)
async def recalculate_lead_score(
    lead_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await ai_domain_service.evaluate_lead_score(db, lead_id, current_user)


@router.get(
    "/{lead_id}/timeline",
    response_model=list[LeadTimelineEvent],
    summary="Get activity timeline for lead",
    dependencies=[Depends(require_permission("leads:read"))],
)
async def get_lead_timeline(
    lead_id: str,
    response: Response,
    page: int = Query(1, ge=1),
    limit: int = Query(15, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    organization_id = await organization_service.resolve_valid_org_id(db, current_user)
    timeline = await lead_service.get_timeline(
        db,
        lead_id,
        organization_id=organization_id,
        current_user=current_user,
        page=page,
        limit=limit,
    )
    response.headers["X-Total-Count"] = str(
        await lead_service.count_timeline(
            db, lead_id, organization_id=organization_id, current_user=current_user
        )
    )
    return timeline


@router.get(
    "/{lead_id}/notes",
    response_model=list[NoteResponse],
    summary="List notes attached to lead",
    dependencies=[
        Depends(require_permission("leads:read")),
        Depends(require_permission("notes:read")),
    ],
)
async def get_lead_notes(
    lead_id: str,
    response: Response,
    page: int = Query(1, ge=1),
    limit: int = Query(15, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    organization_id = await organization_service.resolve_valid_org_id(db, current_user)
    notes = await lead_service.get_notes(
        db, lead_id, organization_id=organization_id, page=page, limit=limit
    )
    response.headers["X-Total-Count"] = str(
        await lead_service.count_notes(db, lead_id, organization_id=organization_id)
    )
    return notes


@router.post(
    "/{lead_id}/notes",
    response_model=NoteResponse,
    summary="Add note to lead",
    dependencies=[
        Depends(require_permission("leads:read")),
        Depends(require_permission("notes:create")),
    ],
)
async def add_lead_note(
    lead_id: str,
    content: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    organization_id = await organization_service.resolve_valid_org_id(db, current_user)
    return await lead_service.add_note(
        db,
        lead_id,
        content,
        organization_id=organization_id,
        actor_id=current_user.id,
    )


@router.get(
    "/{lead_id}/tasks",
    response_model=list[TaskResponse],
    summary="List tasks assigned to lead",
    dependencies=[
        Depends(require_permission("leads:read")),
        Depends(require_permission("tasks:read")),
    ],
)
async def get_lead_tasks(
    lead_id: str,
    response: Response,
    page: int = Query(1, ge=1),
    limit: int = Query(15, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    organization_id = await organization_service.resolve_valid_org_id(db, current_user)
    tasks = await lead_service.get_tasks(
        db, lead_id, organization_id=organization_id, page=page, limit=limit
    )
    response.headers["X-Total-Count"] = str(
        await lead_service.count_tasks(db, lead_id, organization_id=organization_id)
    )
    return tasks


@router.post(
    "/{lead_id}/tasks",
    response_model=TaskResponse,
    summary="Create task for lead",
    dependencies=[
        Depends(require_permission("leads:read")),
        Depends(require_permission("tasks:create")),
    ],
)
async def create_lead_task(
    lead_id: str,
    payload: TaskCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    organization_id = await organization_service.resolve_valid_org_id(db, current_user)
    return await lead_service.create_task(
        db,
        lead_id,
        payload,
        organization_id=organization_id,
        actor_id=current_user.id,
    )


@router.get(
    "/{lead_id}/emails",
    response_model=list[EmailResponse],
    summary="List emails exchanged with lead",
    dependencies=[
        Depends(require_permission("leads:read")),
        Depends(require_permission("emails:read")),
    ],
)
async def get_lead_emails(
    lead_id: str,
    response: Response,
    page: int = Query(1, ge=1),
    limit: int = Query(15, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    organization_id = await organization_service.resolve_valid_org_id(db, current_user)
    emails = await lead_service.get_emails(
        db, lead_id, organization_id=organization_id, page=page, limit=limit
    )
    response.headers["X-Total-Count"] = str(
        await lead_service.count_emails(db, lead_id, organization_id=organization_id)
    )
    return emails


@router.post(
    "/{lead_id}/emails/send",
    response_model=EmailResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Send email to lead",
    dependencies=[
        Depends(require_permission("leads:read")),
        Depends(require_permission("emails:send")),
    ],
)
async def send_lead_email(
    lead_id: str,
    payload: EmailSendRequest,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key", max_length=128),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    organization_id = await organization_service.resolve_valid_org_id(db, current_user)
    return await lead_service.send_email(
        db,
        lead_id,
        payload,
        organization_id=organization_id,
        idempotency_key=idempotency_key,
    )


@router.get(
    "/{lead_id}/calls",
    response_model=list[CallLogResponse],
    summary="List call logs for lead",
    dependencies=[
        Depends(require_permission("leads:read")),
        Depends(require_permission("calls:read")),
    ],
)
async def get_lead_calls(
    lead_id: str,
    response: Response,
    page: int = Query(1, ge=1),
    limit: int = Query(15, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    organization_id = await organization_service.resolve_valid_org_id(db, current_user)
    calls = await lead_service.get_calls(
        db, lead_id, organization_id=organization_id, page=page, limit=limit
    )
    response.headers["X-Total-Count"] = str(
        await lead_service.count_calls(db, lead_id, organization_id=organization_id)
    )
    return calls


@router.post(
    "/{lead_id}/calls",
    response_model=CallLogResponse,
    summary="Log call with lead",
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        Depends(require_permission("leads:read")),
        Depends(require_permission("calls:create")),
    ],
)
async def log_lead_call(
    lead_id: str,
    payload: CallLogBase,
    idempotency_key: str | None = Header(
        default=None, alias="Idempotency-Key", min_length=1, max_length=128
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    lead_payload = payload.model_copy(update={"lead_id": lead_id})
    return await call_service.log_call(
        db,
        lead_payload,
        current_user,
        idempotency_key=idempotency_key,
    )


@router.get(
    "/{lead_id}/documents",
    response_model=list[DocumentResponse],
    summary="List documents attached to lead",
    dependencies=[
        Depends(require_permission("leads:read")),
        Depends(require_permission("documents:read")),
    ],
)
async def get_lead_documents(
    lead_id: str,
    response: Response,
    page: int = Query(1, ge=1),
    limit: int = Query(15, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    organization_id = await organization_service.resolve_valid_org_id(db, current_user)
    documents = await lead_service.get_documents(
        db, lead_id, organization_id=organization_id, page=page, limit=limit
    )
    response.headers["X-Total-Count"] = str(
        await lead_service.count_documents(db, lead_id, organization_id=organization_id)
    )
    return documents


@router.get(
    "/{lead_id}/documents/{document_id}/download",
    summary="Download lead document file",
    dependencies=[
        Depends(require_permission("leads:read")),
        Depends(require_permission("documents:read")),
    ],
)
async def download_lead_document(
    lead_id: str,
    document_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    file_bytes, media_type, filename = await lead_service.download_document(
        db, lead_id, document_id, current_user
    )
    return StreamingResponse(
        iter([file_bytes]),
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post(
    "/{lead_id}/documents",
    response_model=DocumentResponse,
    summary="Attach document file to lead via MinIO S3",
    dependencies=[
        Depends(require_permission("leads:read")),
        Depends(require_permission("documents:upload")),
    ],
)
async def upload_lead_document(
    lead_id: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await lead_service.upload_document(db, lead_id, file, current_user)


@router.post(
    "/{lead_id}/archive",
    response_model=MessageResponse,
    summary="Archive lead",
    dependencies=[Depends(require_permission("leads:update"))],
)
async def archive_lead(
    lead_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    organization_id = await organization_service.resolve_valid_org_id(db, current_user)
    return await lead_service.archive_lead(
        db, lead_id, organization_id=organization_id, actor_id=current_user.id
    )


@router.post(
    "/{lead_id}/unarchive",
    response_model=MessageResponse,
    summary="Unarchive lead",
    dependencies=[Depends(require_permission("leads:update"))],
)
async def unarchive_lead(
    lead_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    organization_id = await organization_service.resolve_valid_org_id(db, current_user)
    return await lead_service.unarchive_lead(
        db, lead_id, organization_id=organization_id, actor_id=current_user.id
    )
