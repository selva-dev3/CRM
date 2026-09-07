from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIException, NotFoundError
from app.models import Company, Contact, Deal, Invoice, Lead, Payment, Quote

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
        entity = await db.scalar(
            select(model).where(
                model.id == entity_id,
                model.organization_id == organization_id,
            )
        )
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


async def validate_polymorphic_crm_entity(
    db: AsyncSession, *, organization_id: str, entity_type: str, entity_id: str
) -> dict[str, str | None]:
    normalized = entity_type.strip().casefold()
    if normalized not in CRM_ENTITY_MODELS:
        raise APIException(
            message="Entity type must be lead, contact, company, or deal",
            code="INVALID_CRM_ENTITY_TYPE",
            status_code=422,
        )
    return await validate_crm_relationships(
        db, organization_id=organization_id, **{f"{normalized}_id": entity_id}
    )


async def validate_document_relationships(
    db: AsyncSession,
    *,
    organization_id: str,
    quote_id: str | None = None,
    invoice_id: str | None = None,
    payment_id: str | None = None,
    **crm_ids: str | None,
) -> dict[str, str | None]:
    relationships = await validate_crm_relationships(db, organization_id=organization_id, **crm_ids)
    for name, entity_id, model in (
        ("quote", quote_id, Quote),
        ("invoice", invoice_id, Invoice),
        ("payment", payment_id, Payment),
    ):
        if entity_id and not await db.scalar(
            select(model.id).where(
                model.id == entity_id,
                model.organization_id == organization_id,
            )
        ):
            raise NotFoundError(message=f"Related {name} not found")
        relationships[f"{name}_id"] = entity_id
    return relationships
