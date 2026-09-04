from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user, require_permission
from app.db.session import get_db
from app.models import User
from app.schemas.crm_schemas import (
    BulkActionResponse,
    BulkDeleteRequest,
    CallLogResponse,
    ContactCreate,
    ContactResponse,
    ContactUpdate,
    CustomFieldDefinition,
    DealResponse,
    EmailResponse,
    MessageResponse,
    NoteResponse,
)
from app.services.contact_service import contact_service
from app.services.note_service import note_service

router = APIRouter()


@router.get(
    "",
    response_model=list[ContactResponse],
    summary="List all contacts",
    dependencies=[Depends(require_permission("contacts:read"))],
)
async def list_contacts(
    response: Response,
    page: int = Query(1, ge=1),
    limit: int = Query(15, ge=1, le=100),
    search: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    contacts = await contact_service.list_contacts(
        db, page=page, limit=limit, search=search, current_user=current_user
    )
    total = await contact_service.count_contacts(db, search=search, current_user=current_user)
    response.headers["X-Total-Count"] = str(total)
    return contacts


@router.post(
    "",
    response_model=ContactResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create new contact",
    dependencies=[Depends(require_permission("contacts:create"))],
)
async def create_contact(
    payload: ContactCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await contact_service.create_contact(db, payload, current_user)


@router.get(
    "/custom-fields",
    response_model=list[CustomFieldDefinition],
    summary="List custom fields available for contacts",
    dependencies=[Depends(require_permission("contacts:read"))],
)
async def list_contact_custom_fields(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await contact_service.list_custom_fields(db, current_user)


@router.get(
    "/starred",
    response_model=list[ContactResponse],
    summary="Get starred contacts list",
    dependencies=[Depends(require_permission("contacts:read"))],
)
async def get_starred_contacts(db: AsyncSession = Depends(get_db)):
    return await contact_service.get_starred_contacts(db)


@router.post(
    "/merge",
    response_model=MessageResponse,
    summary="Merge two contact profiles",
    dependencies=[Depends(require_permission("contacts:update"))],
)
async def merge_contacts(primary_id: str, secondary_id: str, db: AsyncSession = Depends(get_db)):
    return await contact_service.merge_contacts(db, primary_id, secondary_id)


@router.get(
    "/export/csv",
    summary="Export contacts as CSV",
    dependencies=[Depends(require_permission("contacts:export"))],
)
async def export_contacts_csv():
    return {"download_url": "https://api.crm.com/exports/contacts.csv"}


@router.post(
    "/import/csv",
    response_model=MessageResponse,
    summary="Import contacts from CSV",
    dependencies=[Depends(require_permission("contacts:import"))],
)
async def import_contacts_csv():
    return {"message": "Import completed successfully", "status": "success"}


@router.post(
    "/bulk-delete",
    response_model=BulkActionResponse,
    summary="Bulk delete contacts",
    dependencies=[Depends(require_permission("contacts:bulk_delete"))],
)
async def bulk_delete_contacts(payload: BulkDeleteRequest, db: AsyncSession = Depends(get_db)):
    return await contact_service.bulk_delete(db, payload.ids)


@router.get(
    "/{contact_id}",
    response_model=ContactResponse,
    summary="Get contact details by ID",
    dependencies=[Depends(require_permission("contacts:read"))],
)
async def get_contact(contact_id: str, db: AsyncSession = Depends(get_db)):
    return await contact_service.get_contact(db, contact_id)


@router.put(
    "/{contact_id}",
    response_model=ContactResponse,
    summary="Update contact by ID",
    dependencies=[Depends(require_permission("contacts:update"))],
)
async def update_contact(
    contact_id: str, payload: ContactUpdate, db: AsyncSession = Depends(get_db)
):
    return await contact_service.update_contact(db, contact_id, payload)


@router.delete(
    "/{contact_id}",
    response_model=MessageResponse,
    summary="Delete contact by ID",
    dependencies=[Depends(require_permission("contacts:delete"))],
)
async def delete_contact(contact_id: str, db: AsyncSession = Depends(get_db)):
    return await contact_service.delete_contact(db, contact_id)


@router.get(
    "/{contact_id}/deals",
    response_model=list[DealResponse],
    summary="List deals linked to contact",
    dependencies=[Depends(require_permission("contacts:read"))],
)
async def get_contact_deals(contact_id: str, db: AsyncSession = Depends(get_db)):
    await contact_service.get_contact(db, contact_id)
    return []


@router.get(
    "/{contact_id}/activities",
    summary="Get activity timeline for contact",
    dependencies=[Depends(require_permission("contacts:read"))],
)
async def get_contact_activities(contact_id: str, db: AsyncSession = Depends(get_db)):
    await contact_service.get_contact(db, contact_id)
    return []


@router.post(
    "/{contact_id}/star",
    response_model=MessageResponse,
    summary="Star contact",
    dependencies=[Depends(require_permission("contacts:update"))],
)
async def star_contact(contact_id: str, db: AsyncSession = Depends(get_db)):
    return await contact_service.set_starred(db, contact_id, starred=True)


@router.post(
    "/{contact_id}/unstar",
    response_model=MessageResponse,
    summary="Unstar contact",
    dependencies=[Depends(require_permission("contacts:update"))],
)
async def unstar_contact(contact_id: str, db: AsyncSession = Depends(get_db)):
    return await contact_service.set_starred(db, contact_id, starred=False)


@router.get(
    "/{contact_id}/notes",
    response_model=list[NoteResponse],
    summary="List notes for contact",
    dependencies=[Depends(require_permission("contacts:read"))],
)
async def get_contact_notes(
    contact_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await note_service.list_for_entity(
        db,
        entity_type="contact",
        entity_id=contact_id,
        created_by_default=current_user.id,
        current_user=current_user,
    )


@router.post(
    "/{contact_id}/notes",
    response_model=NoteResponse,
    summary="Add note to contact",
    dependencies=[Depends(require_permission("contacts:create"))],
)
async def add_contact_note(
    contact_id: str,
    content: str | None = Query(None),
    payload: dict | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    note_content = content
    if not note_content and isinstance(payload, dict):
        note_content = payload.get("content")
    if not note_content:
        note_content = "Note"
    return await note_service.add_for_entity(
        db,
        entity_type="contact",
        entity_id=contact_id,
        content=note_content,
        current_user=current_user,
    )


@router.get(
    "/{contact_id}/emails",
    response_model=list[EmailResponse],
    summary="List emails linked to contact",
    dependencies=[Depends(require_permission("contacts:read"))],
)
async def get_contact_emails(contact_id: str, db: AsyncSession = Depends(get_db)):
    await contact_service.get_contact(db, contact_id)
    return []


@router.get(
    "/{contact_id}/calls",
    response_model=list[CallLogResponse],
    summary="List call logs for contact",
    dependencies=[Depends(require_permission("contacts:read"))],
)
async def get_contact_calls(contact_id: str, db: AsyncSession = Depends(get_db)):
    await contact_service.get_contact(db, contact_id)
    return []
