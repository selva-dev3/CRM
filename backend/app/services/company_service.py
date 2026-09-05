from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIException, NotFoundError
from app.models import User
from app.models.company import Company
from app.repositories.company_repository import CompanyRepository
from app.repositories.deal_repository import DealRepository
from app.repositories.invoice_repository import invoice_repository
from app.repositories.quote_repository import quote_repository
from app.schemas.crm_schemas import CompanyCreate, CompanyUpdate, CustomFieldDefinition
from app.services.contact_service import contact_service
from app.services.custom_field_service import CustomFieldService, custom_field_service
from app.services.notification_service import notification_service
from app.services.org_service import organization_service


def company_to_dict(company: Company) -> dict:
    return {
        "id": company.id,
        "name": company.name,
        "domain": company.website,
        "website": company.website,
        "industry": company.industry,
        "size": str(company.employee_count) if company.employee_count else None,
        "employee_count": company.employee_count,
        "created_at": str(company.created_at),
        "custom_fields": company.custom_fields or {},
    }


class CompanyService:
    """Business logic for the Company domain."""

    def __init__(
        self,
        repository: CompanyRepository | None = None,
        custom_field_service_instance: CustomFieldService | None = None,
    ) -> None:
        self.repository = repository or CompanyRepository()
        self.deal_repository = DealRepository()
        self.custom_field_service = custom_field_service_instance or custom_field_service

    async def _commit(self, db: AsyncSession, error_message: str) -> None:
        try:
            await db.commit()
        except Exception as e:
            await db.rollback()
            raise APIException(
                status_code=status.HTTP_400_BAD_REQUEST, message=error_message
            ) from e

    @staticmethod
    def _parse_employee_count(emp_raw: object | None) -> int | None:
        if emp_raw is None:
            return None
        if not isinstance(emp_raw, (str, bytes, bytearray, int, float)):
            return None
        try:
            return int(emp_raw)
        except (ValueError, TypeError):
            return None

    async def list_companies(
        self,
        db: AsyncSession,
        *,
        page: int,
        limit: int,
        search: str | None = None,
        current_user: User,
    ) -> list[dict]:
        organization_id = await organization_service.resolve_valid_org_id(db, current_user)
        companies = await self.repository.list_by_org(
            db,
            organization_id=organization_id,
            page=page,
            limit=limit,
            search=search,
        )
        return [company_to_dict(c) for c in companies]

    async def count_companies(
        self,
        db: AsyncSession,
        *,
        search: str | None = None,
        current_user: User,
    ) -> int:
        organization_id = await organization_service.resolve_valid_org_id(db, current_user)
        return await self.repository.count_by_org(
            db, organization_id=organization_id, search=search
        )

    async def get_company(self, db: AsyncSession, company_id: str, *, organization_id: str) -> dict:
        company = await self.repository.get_by_id_scoped(
            db, company_id=company_id, organization_id=organization_id
        )
        if not company:
            raise NotFoundError(message=f"Company '{company_id}' not found")
        return company_to_dict(company)

    async def list_custom_fields(
        self, db: AsyncSession, current_user: User
    ) -> list[CustomFieldDefinition]:
        organization_id = await organization_service.resolve_valid_org_id(db, current_user)
        return await self.custom_field_service.list_definitions(
            db, organization_id=organization_id, entity_type="Company"
        )

    async def create_company(
        self, db: AsyncSession, payload: CompanyCreate, current_user: User | None = None
    ) -> dict:
        org_id = await organization_service.resolve_valid_org_id(db, current_user)
        custom_fields = await self.custom_field_service.validate_values(
            db,
            organization_id=org_id,
            entity_type="Company",
            values=payload.custom_fields,
        )
        website = getattr(payload, "website", None) or getattr(payload, "domain", None)
        emp_raw = getattr(payload, "employee_count", None) or getattr(payload, "size", None)
        data = {
            "organization_id": org_id,
            "name": payload.name,
            "industry": getattr(payload, "industry", None),
            "website": website,
            "employee_count": self._parse_employee_count(emp_raw),
            "custom_fields": custom_fields,
        }
        company = await self.repository.create(db, data=data)
        await self._commit(db, "Failed to create company")
        await db.refresh(company)
        await notification_service.notify(
            db,
            event_name="company.created",
            organization_id=company.organization_id,
            actor_user_id=current_user.id if current_user else None,
            entity_type="company",
            entity_id=company.id,
            data={
                "id": company.id,
                "name": company.name,
                "website": company.website,
                "industry": company.industry,
                "employee_count": company.employee_count,
            },
        )
        return company_to_dict(company)

    async def update_company(
        self,
        db: AsyncSession,
        company_id: str,
        payload: CompanyUpdate,
        *,
        organization_id: str,
    ) -> dict:
        company = await self.repository.get_by_id_scoped(
            db, company_id=company_id, organization_id=organization_id
        )
        if not company:
            raise NotFoundError(message=f"Company '{company_id}' not found")

        name = getattr(payload, "name", None)
        if name:
            company.name = name
        industry = getattr(payload, "industry", None)
        if industry:
            company.industry = industry
        website = getattr(payload, "website", None) or getattr(payload, "domain", None)
        if website:
            company.website = website
        emp_raw = getattr(payload, "employee_count", None) or getattr(payload, "size", None)
        if emp_raw is not None:
            company.employee_count = self._parse_employee_count(emp_raw)
        if payload.custom_fields is not None:
            company.custom_fields = await self.custom_field_service.validate_values(
                db,
                organization_id=company.organization_id,
                entity_type="Company",
                values=payload.custom_fields,
            )

        await self._commit(db, "Failed to update company")
        await db.refresh(company)
        await notification_service.notify(
            db,
            event_name="company.updated",
            organization_id=company.organization_id,
            entity_type="company",
            entity_id=company.id,
            data={"id": company.id, "name": company.name, "industry": company.industry},
        )
        return company_to_dict(company)

    async def delete_company(
        self, db: AsyncSession, company_id: str, *, organization_id: str
    ) -> dict:
        company = await self.repository.get_by_id_scoped(
            db, company_id=company_id, organization_id=organization_id
        )
        if not company:
            raise NotFoundError(message=f"Company '{company_id}' not found")
        await self.repository.delete(db, company)
        await self._commit(db, "Failed to delete company")
        return {"message": f"Company {company_id} deleted successfully", "status": "success"}

    async def bulk_delete(self, db: AsyncSession, ids: list[str], *, organization_id: str) -> dict:
        companies = await self.repository.list_by_ids(db, ids, organization_id=organization_id)
        for company in companies:
            await self.repository.delete(db, company)
        await self._commit(db, "Failed to bulk delete companies")
        return {"affected_count": len(companies), "message": "Companies deleted successfully"}

    async def require_company(
        self, db: AsyncSession, company_id: str, *, organization_id: str
    ) -> Company:
        company = await self.repository.get_by_id_scoped(
            db, company_id=company_id, organization_id=organization_id
        )
        if not company:
            raise NotFoundError(message=f"Company '{company_id}' not found")
        return company

    async def get_company_contacts(
        self, db: AsyncSession, company_id: str, *, organization_id: str
    ) -> list[dict]:
        await self.require_company(db, company_id, organization_id=organization_id)
        return await contact_service.list_company_contacts(
            db, company_id, organization_id=organization_id
        )

    async def get_company_deals(
        self, db: AsyncSession, company_id: str, *, organization_id: str
    ) -> list:
        await self.require_company(db, company_id, organization_id=organization_id)
        from app.services.deal_service import deal_to_dict

        deals = await self.deal_repository.list_by_company(
            db, company_id=company_id, organization_id=organization_id
        )
        return [deal_to_dict(deal) for deal in deals]

    async def get_company_quotes(
        self, db: AsyncSession, company_id: str, *, organization_id: str
    ) -> list:
        await self.require_company(db, company_id, organization_id=organization_id)
        from app.services.quote_service import quote_to_dict

        quotes = await quote_repository.list_by_company(
            db, company_id=company_id, organization_id=organization_id
        )
        return [quote_to_dict(quote) for quote in quotes]

    async def get_company_invoices(
        self, db: AsyncSession, company_id: str, *, organization_id: str
    ) -> list:
        await self.require_company(db, company_id, organization_id=organization_id)
        from app.services.invoice_service import invoice_to_dict

        invoices = await invoice_repository.list_by_company(
            db, company_id=company_id, organization_id=organization_id
        )
        return [invoice_to_dict(invoice) for invoice in invoices]

    async def get_company_documents(
        self, db: AsyncSession, company_id: str, *, organization_id: str
    ) -> list:
        await self.require_company(db, company_id, organization_id=organization_id)
        raise APIException(
            message="Company documents are not linked to a CRM entity yet",
            code="COMPANY_DOCUMENT_RELATION_UNAVAILABLE",
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
        )

    async def get_company_hierarchy(
        self, db: AsyncSession, company_id: str, *, organization_id: str
    ) -> dict:
        company = await self.require_company(db, company_id, organization_id=organization_id)
        parent = None
        if company.parent_company_id:
            parent_record = await self.repository.get_by_id_scoped(
                db,
                company_id=company.parent_company_id,
                organization_id=organization_id,
            )
            if parent_record:
                parent = company_to_dict(parent_record)
        subsidiaries = await self.repository.list_subsidiaries(
            db, parent_company_id=company_id, organization_id=organization_id
        )
        return {
            "parent_company": parent,
            "subsidiaries": [company_to_dict(item) for item in subsidiaries],
        }

    async def set_parent_company(
        self,
        db: AsyncSession,
        company_id: str,
        parent_id: str,
        *,
        organization_id: str,
    ) -> dict:
        company = await self.require_company(db, company_id, organization_id=organization_id)
        parent = await self.require_company(db, parent_id, organization_id=organization_id)
        if company.id == parent.id:
            raise APIException(
                message="A company cannot be its own parent",
                code="INVALID_COMPANY_HIERARCHY",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        ancestor_id = parent.parent_company_id
        visited: set[str] = {parent.id}
        while ancestor_id:
            if ancestor_id == company.id or ancestor_id in visited:
                raise APIException(
                    message="Company hierarchy would create a cycle",
                    code="INVALID_COMPANY_HIERARCHY",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )
            visited.add(ancestor_id)
            ancestor = await self.repository.get_by_id_scoped(
                db, company_id=ancestor_id, organization_id=organization_id
            )
            if not ancestor:
                break
            ancestor_id = ancestor.parent_company_id
        await self.repository.set_parent(company, parent.id)
        await self._commit(db, "Failed to update company hierarchy")
        return {"message": "Parent company updated successfully", "status": "success"}

    async def lookup_domain(self, domain: str) -> dict:
        raise APIException(
            message="Company enrichment is not configured",
            code="COMPANY_ENRICHMENT_UNAVAILABLE",
            status_code=503,
        )

    async def export_csv(self) -> dict:
        raise APIException(
            message="Company CSV export is not implemented",
            code="COMPANY_EXPORT_UNAVAILABLE",
            status_code=501,
        )

    async def import_csv(self) -> dict:
        raise APIException(
            message="Company CSV import is not implemented",
            code="COMPANY_IMPORT_UNAVAILABLE",
            status_code=501,
        )


company_service = CompanyService()
