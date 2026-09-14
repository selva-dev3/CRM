from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIException, NotFoundError
from app.core.record_access import RecordAccessContext, record_access_filter
from app.models import Company, Contact, Deal, Invoice, Lead, Payment, Project, Quote, Ticket, User
from app.repositories.project_access import project_record_access_filter

CRM_ENTITY_MODELS = {
    "lead": Lead,
    "contact": Contact,
    "company": Company,
    "deal": Deal,
}


async def validate_crm_relationships(
    db: AsyncSession,
    *,
    organization_id: str,
    lead_id: str | None = None,
    contact_id: str | None = None,
    company_id: str | None = None,
    deal_id: str | None = None,
    access_by_module: dict[str, RecordAccessContext] | None = None,
) -> dict[str, str | None]:
    values = {
        "lead": lead_id,
        "contact": contact_id,
        "company": company_id,
        "deal": deal_id,
    }
    resolved: dict[str, object] = {}
    for entity_type, entity_id in values.items():
        if not entity_id:
            continue
        model = CRM_ENTITY_MODELS[entity_type]
        query = select(model).where(
            model.id == entity_id,
            model.organization_id == organization_id,
        )
        if access_by_module is not None:
            assigned_column, created_column = {
                "lead": (Lead.assigned_to, Lead.created_by),
                "contact": (Contact.owner_id, Contact.created_by),
                "company": (Company.owner_id, Company.created_by),
                "deal": (Deal.assigned_to, Deal.created_by),
            }[entity_type]
            module_name = {
                "lead": "leads",
                "contact": "contacts",
                "company": "companies",
                "deal": "deals",
            }[entity_type]
            access_filter = record_access_filter(
                access_by_module[module_name],
                assigned_column=assigned_column,
                created_column=created_column,
            )
            if access_filter is not None:
                query = query.where(access_filter)
        entity = await db.scalar(query)
        if not entity:
            raise NotFoundError(message=f"Related {entity_type} not found")
        resolved[entity_type] = entity

    contact = resolved.get("contact")
    company = resolved.get("company")
    deal = resolved.get("deal")
    if contact and company and getattr(contact, "company_id", None) != company.id:  # type: ignore[attr-defined]
        raise APIException(
            message="Related contact does not belong to the selected company",
            code="CRM_RELATIONSHIP_MISMATCH",
            status_code=422,
        )
    if deal:
        if company and getattr(deal, "company_id", None) not in {None, company.id}:  # type: ignore[attr-defined]
            raise APIException(
                message="Related deal does not belong to the selected company",
                code="CRM_RELATIONSHIP_MISMATCH",
                status_code=422,
            )
        if contact and getattr(deal, "contact_id", None) not in {None, contact.id}:  # type: ignore[attr-defined]
            raise APIException(
                message="Related deal does not belong to the selected contact",
                code="CRM_RELATIONSHIP_MISMATCH",
                status_code=422,
            )
    return {f"{key}_id": value for key, value in values.items()}


async def resolve_crm_record_access(
    db: AsyncSession, current_user: User
) -> dict[str, RecordAccessContext]:
    from app.services.record_access_service import record_access_service

    return {
        module: await record_access_service.resolve(db, current_user, module)
        for module in ("leads", "contacts", "companies", "deals")
    }


async def validate_polymorphic_crm_entity(
    db: AsyncSession,
    *,
    organization_id: str,
    entity_type: str,
    entity_id: str,
    access_by_module: dict[str, RecordAccessContext] | None = None,
) -> dict[str, str | None]:
    normalized = entity_type.strip().casefold()
    if normalized not in CRM_ENTITY_MODELS:
        raise APIException(
            message="Entity type must be lead, contact, company, or deal",
            code="INVALID_CRM_ENTITY_TYPE",
            status_code=422,
        )
    return await validate_crm_relationships(
        db,
        organization_id=organization_id,
        access_by_module=access_by_module,
        **{f"{normalized}_id": entity_id},
    )


async def validate_document_relationships(
    db: AsyncSession,
    *,
    organization_id: str,
    quote_id: str | None = None,
    invoice_id: str | None = None,
    payment_id: str | None = None,
    project_id: str | None = None,
    ticket_id: str | None = None,
    access_by_module: dict[str, RecordAccessContext] | None = None,
    **crm_ids: str | None,
) -> dict[str, str | None]:
    relationships = await validate_crm_relationships(
        db,
        organization_id=organization_id,
        access_by_module=access_by_module,
        **crm_ids,
    )
    if access_by_module is not None:
        crm_access_specs = (
            ("lead", crm_ids.get("lead_id"), Lead, Lead.assigned_to, Lead.created_by, "leads"),
            (
                "contact",
                crm_ids.get("contact_id"),
                Contact,
                Contact.owner_id,
                Contact.created_by,
                "contacts",
            ),
            (
                "company",
                crm_ids.get("company_id"),
                Company,
                Company.owner_id,
                Company.created_by,
                "companies",
            ),
            ("deal", crm_ids.get("deal_id"), Deal, Deal.assigned_to, Deal.created_by, "deals"),
        )
        for name, entity_id, model, assigned_column, created_column, module in crm_access_specs:
            if not entity_id:
                continue
            access_filter = record_access_filter(
                access_by_module[module],
                assigned_column=assigned_column,
                created_column=created_column,
            )
            query = select(model.id).where(
                model.id == entity_id,
                model.organization_id == organization_id,
            )
            if access_filter is not None:
                query = query.where(access_filter)
            if not await db.scalar(query):
                raise NotFoundError(message=f"Related {name} not found")
    for name, entity_id, model in (
        ("quote", quote_id, Quote),
        ("invoice", invoice_id, Invoice),
        ("payment", payment_id, Payment),
        ("project", project_id, Project),
        ("ticket", ticket_id, Ticket),
    ):
        if not entity_id:
            relationships[f"{name}_id"] = entity_id
            continue
        query = select(model.id).where(
            model.id == entity_id,
            model.organization_id == organization_id,
        )
        if access_by_module is not None:
            access = access_by_module[f"{name}s"]
            if name == "project":
                access_filter = project_record_access_filter(access)
            elif name == "ticket":
                access_filter = record_access_filter(
                    access,
                    assigned_column=Ticket.assigned_to,
                    created_column=Ticket.created_by,
                    team_column=Ticket.team_id,
                )
            elif name == "payment":
                query = query.join(Invoice, Invoice.id == Payment.invoice_id)
                access_filter = record_access_filter(
                    access,
                    assigned_column=Invoice.created_by,
                    created_column=Invoice.created_by,
                )
            elif name == "quote":
                access_filter = record_access_filter(
                    access,
                    assigned_column=Quote.created_by,
                    created_column=Quote.created_by,
                )
            else:
                access_filter = record_access_filter(
                    access,
                    assigned_column=Invoice.created_by,
                    created_column=Invoice.created_by,
                )
            if access_filter is not None:
                query = query.where(access_filter)
        if not await db.scalar(query):
            raise NotFoundError(message=f"Related {name} not found")
        relationships[f"{name}_id"] = entity_id
    return relationships
