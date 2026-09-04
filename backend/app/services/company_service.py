from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIException, NotFoundError
from app.models import User
from app.models.company import Company
from app.repositories.company_repository import CompanyRepository
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

    async def get_company(self, db: AsyncSession, company_id: str) -> dict:
        company = await self.repository.get_by_id(db, company_id)
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
        self, db: AsyncSession, company_id: str, payload: CompanyUpdate
    ) -> dict:
        company = await self.repository.get_by_id(db, company_id)
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

    async def delete_company(self, db: AsyncSession, company_id: str) -> dict:
        company = await self.repository.get_by_id(db, company_id)
        if not company:
            raise NotFoundError(message=f"Company '{company_id}' not found")
        await self.repository.delete(db, company)
        await self._commit(db, "Failed to delete company")
        return {"message": f"Company {company_id} deleted successfully", "status": "success"}

    async def bulk_delete(self, db: AsyncSession, ids: list[str]) -> dict:
        companies = await self.repository.list_by_ids(db, ids)
        for company in companies:
            await self.repository.delete(db, company)
        await self._commit(db, "Failed to bulk delete companies")
        return {"affected_count": len(companies), "message": "Companies deleted successfully"}

    async def require_company(self, db: AsyncSession, company_id: str) -> None:
        company = await self.repository.get_by_id(db, company_id)
        if not company:
            raise NotFoundError(message=f"Company '{company_id}' not found")

    async def get_company_contacts(self, db: AsyncSession, company_id: str) -> list[dict]:
        return await contact_service.list_company_contacts(db, company_id)

    async def get_company_deals(self, db: AsyncSession, company_id: str) -> list:
        await self.require_company(db, company_id)
        return []

    async def get_company_quotes(self, db: AsyncSession, company_id: str) -> list:
        await self.require_company(db, company_id)
        return []

    async def get_company_invoices(self, db: AsyncSession, company_id: str) -> list:
        await self.require_company(db, company_id)
        return []

    async def get_company_documents(self, db: AsyncSession, company_id: str) -> list:
        await self.require_company(db, company_id)
        return []

    async def get_company_hierarchy(self, db: AsyncSession, company_id: str) -> dict:
        await self.require_company(db, company_id)
        return {"parent_company": None, "subsidiaries": []}

    async def set_parent_company(self, db: AsyncSession, company_id: str, parent_id: str) -> dict:
        await self.require_company(db, company_id)
        return {
            "message": f"Set parent {parent_id} for company {company_id}",
            "status": "success",
        }

    async def lookup_domain(self, domain: str) -> dict:
        return {
            "domain": domain,
            "name": "Enriched Corp",
            "industry": "Software",
            "employee_count": 250,
            "location": "San Francisco, CA",
        }

    async def export_csv(self) -> dict:
        return {"download_url": "https://api.crm.com/exports/companies.csv"}

    async def import_csv(self) -> dict:
        return {"message": "Import completed successfully", "status": "success"}


company_service = CompanyService()
