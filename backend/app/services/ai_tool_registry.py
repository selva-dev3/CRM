from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from functools import cached_property
from time import monotonic
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIException, ForbiddenError
from app.core.request_context import get_request_id
from app.models import AIRun, User
from app.repositories.ai_repository import AIRepository
from app.schemas.ai import CRMSearchPlan
from app.schemas.ai_tools import (
    AIToolRecord,
    AIToolResult,
    RecordToolArguments,
    SearchToolArguments,
)
from app.services.ai_audit_service import AIAuditService, ai_audit_service

if TYPE_CHECKING:
    from app.services.activity_service import ActivityService
    from app.services.calendar_service import CalendarService
    from app.services.call_service import CallService
    from app.services.company_service import CompanyService
    from app.services.contact_service import ContactService
    from app.services.deal_service import DealService
    from app.services.document_service import DocumentService
    from app.services.email_domain_service import EmailDomainService
    from app.services.invoice_service import InvoiceService
    from app.services.lead_service import LeadService
    from app.services.meeting_service import MeetingService
    from app.services.note_service import NoteService
    from app.services.product_service import ProductService
    from app.services.project_service import ProjectService
    from app.services.quote_service import QuoteService
    from app.services.task_service import TaskService
    from app.services.user_service import UserService

SensitivePolicy = Literal["safe_only", "purpose_restricted"]
AuditPolicy = Literal["metadata_only"]
ToolFallback = Callable[[CRMSearchPlan], Awaitable[list[dict[str, object]]]]
ToolExecutor = Callable[
    ["AIToolContext", str, BaseModel, ToolFallback], Awaitable[AIToolResult]
]


@dataclass(frozen=True)
class RegisteredAITool:
    name: str
    description: str
    argument_schema: type[BaseModel]
    result_schema: type[AIToolResult]
    required_permission: str
    record_scope_required: bool
    maximum_result_count: int
    sensitive_field_policy: SensitivePolicy
    executor: ToolExecutor
    timeout_seconds: float
    audit_policy: AuditPolicy = "metadata_only"


@dataclass(frozen=True)
class AIToolContext:
    db: AsyncSession
    user: User
    organization_id: str
    permissions: frozenset[str]
    run: AIRun


class AIToolRegistry:
    """Provider-neutral allow-list; provider output never selects executable code."""

    def __init__(
        self,
        repository: AIRepository | None = None,
        audit_service: AIAuditService | None = None,
    ) -> None:
        self.repository = repository or AIRepository()
        self.audit_service = audit_service or ai_audit_service
        self._tools = self._build_registry()

    @cached_property
    def leads(self) -> LeadService:
        from app.services.lead_service import LeadService

        return LeadService()

    @cached_property
    def contacts(self) -> ContactService:
        from app.services.contact_service import ContactService

        return ContactService()

    @cached_property
    def companies(self) -> CompanyService:
        from app.services.company_service import CompanyService

        return CompanyService()

    @cached_property
    def deals(self) -> DealService:
        from app.services.deal_service import DealService

        return DealService()

    @cached_property
    def tasks(self) -> TaskService:
        from app.services.task_service import TaskService

        return TaskService()

    @cached_property
    def meetings(self) -> MeetingService:
        from app.services.meeting_service import MeetingService

        return MeetingService()

    @cached_property
    def projects(self) -> ProjectService:
        from app.services.project_service import ProjectService

        return ProjectService()

    @cached_property
    def calls(self) -> CallService:
        from app.services.call_service import CallService

        return CallService()

    @cached_property
    def emails(self) -> EmailDomainService:
        from app.services.email_domain_service import EmailDomainService

        return EmailDomainService()

    @cached_property
    def notes(self) -> NoteService:
        from app.services.note_service import NoteService

        return NoteService()

    @cached_property
    def documents(self) -> DocumentService:
        from app.services.document_service import DocumentService

        return DocumentService()

    @cached_property
    def products(self) -> ProductService:
        from app.services.product_service import ProductService

        return ProductService()

    @cached_property
    def quotes(self) -> QuoteService:
        from app.services.quote_service import QuoteService

        return QuoteService()

    @cached_property
    def invoices(self) -> InvoiceService:
        from app.services.invoice_service import InvoiceService

        return InvoiceService()

    @cached_property
    def calendar(self) -> CalendarService:
        from app.services.calendar_service import CalendarService

        return CalendarService()

    @cached_property
    def activities(self) -> ActivityService:
        from app.services.activity_service import ActivityService

        return ActivityService()

    @cached_property
    def users(self) -> UserService:
        from app.services.user_service import UserService

        return UserService()

    def _build_registry(self) -> dict[str, RegisteredAITool]:
        descriptions = {
            "search_leads": ("Search authorized leads.", "leads:read", True),
            "get_lead": ("Get one authorized lead.", "leads:read", True),
            "search_contacts": ("Search authorized contacts.", "contacts:read", True),
            "get_contact": ("Get one authorized contact.", "contacts:read", True),
            "search_companies": ("Search authorized companies.", "companies:read", True),
            "get_company": ("Get one authorized company.", "companies:read", True),
            "search_deals": ("Search authorized deals.", "deals:read", True),
            "get_deal": ("Get one authorized deal.", "deals:read", True),
            "get_tasks": ("List authorized tasks.", "tasks:read", True),
            "get_meetings": ("List authorized meetings.", "meetings:read", True),
            "get_sales_pipeline": ("Summarize the authorized sales pipeline.", "deals:read", True),
            "get_dashboard_metrics": ("Get authorized CRM metrics.", "reports:read", True),
            "search_projects": ("Search authorized projects.", "projects:read", True),
            "search_calls": ("Search authorized call records.", "calls:read", True),
            "search_emails": ("Search authorized email metadata.", "emails:read", True),
            "search_notes": ("Search authorized notes.", "notes:read", True),
            "search_documents": ("Search authorized document metadata.", "documents:read", True),
            "search_products": ("Search authorized products.", "products:read", False),
            "search_quotes": ("Search authorized quotes.", "quotes:read", True),
            "search_invoices": ("Search authorized invoices.", "invoices:read", True),
            "search_calendar_events": ("Search authorized calendar events.", "calendar:read", True),
            "search_activities": ("Search authorized activities.", "activities:read", True),
            "search_users": ("Search authorized users.", "users:read", True),
        }
        tools: dict[str, RegisteredAITool] = {}
        detail_tools = {"get_lead", "get_contact", "get_company", "get_deal"}
        for name, (description, permission, scoped) in descriptions.items():
            tools[name] = RegisteredAITool(
                name=name,
                description=description,
                argument_schema=RecordToolArguments if name in detail_tools else SearchToolArguments,
                result_schema=AIToolResult,
                required_permission=permission,
                record_scope_required=scoped,
                maximum_result_count=50,
                sensitive_field_policy="purpose_restricted",
                executor=self._execute_registered_search,
                timeout_seconds=10.0,
            )
        return tools

    @property
    def definitions(self) -> tuple[RegisteredAITool, ...]:
        return tuple(self._tools.values())

    @staticmethod
    def tool_name_for_plan(plan: CRMSearchPlan) -> str:
        prefix = "get" if plan.intent == "detail" else "search"
        mapping = {
            "lead": f"{prefix}_lead" if prefix == "get" else "search_leads",
            "contact": f"{prefix}_contact" if prefix == "get" else "search_contacts",
            "company": f"{prefix}_company" if prefix == "get" else "search_companies",
            "deal": (
                "get_sales_pipeline"
                if plan.intent in {"aggregate", "comparison"}
                else (f"{prefix}_deal" if prefix == "get" else "search_deals")
            ),
            "task": "get_tasks",
            "meeting": "get_meetings",
            "report": "get_dashboard_metrics",
            "project": "search_projects",
            "call": "search_calls",
            "email": "search_emails",
            "note": "search_notes",
            "document": "search_documents",
            "product": "search_products",
            "quote": "search_quotes",
            "invoice": "search_invoices",
            "calendar_event": "search_calendar_events",
            "activity": "search_activities",
            "user": "search_users",
        }
        name = mapping.get(plan.entity_type)
        if name is None:
            raise APIException(
                status_code=400,
                code="AI_TOOL_NOT_REGISTERED",
                message="The requested CRM capability is not available to the AI assistant.",
            )
        return name

    async def execute_plan(
        self,
        context: AIToolContext,
        plan: CRMSearchPlan,
        *,
        fallback: Callable[[CRMSearchPlan], Awaitable[list[dict[str, object]]]],
    ) -> list[dict[str, object]]:
        name = self.tool_name_for_plan(plan)
        tool = self._tools[name]
        started = monotonic()
        error_category: str | None = None
        succeeded = False
        result_count = 0
        try:
            if tool.required_permission not in context.permissions:
                raise ForbiddenError(
                    message=f"Missing required permission: {tool.required_permission}"
                )
            arguments = (
                tool.argument_schema.model_validate({"record_id": plan.record_id})
                if tool.argument_schema is RecordToolArguments
                else tool.argument_schema.model_validate({"plan": plan})
            )
            # Service adapters cover ordinary list/detail operations. Advanced
            # bounded reporting remains behind this registered fallback while
            # it is incrementally extracted from AIRepository.
            result = await asyncio.wait_for(
                tool.executor(context, name, arguments, fallback),
                timeout=tool.timeout_seconds,
            )
            result_count = result.result_count
            succeeded = True
            return result.dictionaries()
        except TimeoutError as exc:
            error_category = "timeout"
            raise APIException(
                status_code=504,
                code="AI_TOOL_TIMEOUT",
                message="The CRM data lookup timed out.",
            ) from exc
        except APIException as exc:
            error_category = exc.code
            raise
        except Exception:
            error_category = "internal_error"
            raise
        finally:
            await self.audit_service.record_tool_execution(
                request_id=get_request_id() or context.run.id,
                run_id=context.run.id,
                organization_id=context.organization_id,
                user_id=context.user.id,
                tool_name=name,
                provider=getattr(context.run, "provider", None),
                model_name=getattr(context.run, "model_name", None),
                duration_ms=int((monotonic() - started) * 1000),
                result_count=result_count,
                succeeded=succeeded,
                error_category=error_category,
            )

    async def _execute_registered_search(
        self,
        context: AIToolContext,
        name: str,
        arguments: BaseModel,
        fallback: Callable[[CRMSearchPlan], Awaitable[list[dict[str, object]]]],
    ) -> AIToolResult:
        if isinstance(arguments, RecordToolArguments):
            record = await self._service_detail(context, name, arguments.record_id)
            return AIToolResult(
                records=[AIToolRecord.model_validate(record)],
                result_count=1,
            )
        parsed = SearchToolArguments.model_validate(arguments.model_dump())
        plan = parsed.plan
        simple = not (
            plan.filters
            or plan.include_fields
            or plan.aggregate
            or plan.group_by
            or plan.date_range
            or plan.inactive_days
            or plan.minimum_open_deal_amount is not None
            or (
                name == "search_deals"
                and (plan.status or "").strip().lower() in {"open", "won", "lost"}
            )
        )
        records: list[dict[str, object]]
        if simple and plan.intent == "list":
            service_records = await self._service_list(context, name, plan)
            records = service_records if service_records is not None else await fallback(plan)
        else:
            records = await fallback(plan)
        bounded = records[: self._tools[name].maximum_result_count]
        return AIToolResult(
            records=[AIToolRecord.model_validate(record) for record in bounded],
            result_count=len(bounded),
        )

    async def _service_detail(
        self, context: AIToolContext, name: str, record_id: str
    ) -> dict[str, object]:
        if name == "get_lead":
            return await self.leads.get_lead(
                context.db,
                record_id,
                organization_id=context.organization_id,
                current_user=context.user,
            )
        if name == "get_contact":
            return await self.contacts.get_contact(
                context.db,
                record_id,
                organization_id=context.organization_id,
                current_user=context.user,
            )
        if name == "get_company":
            return await self.companies.get_company(
                context.db,
                record_id,
                organization_id=context.organization_id,
                current_user=context.user,
            )
        if name == "get_deal":
            return await self.deals.get_deal(
                context.db,
                record_id,
                organization_id=context.organization_id,
                current_user=context.user,
            )
        raise APIException(
            status_code=400,
            code="AI_TOOL_ARGUMENTS_UNSUPPORTED",
            message=f"The registered tool '{name}' does not support record lookup.",
        )

    async def _service_list(
        self, context: AIToolContext, name: str, plan: CRMSearchPlan
    ) -> list[dict[str, object]] | None:
        if name == "search_leads":
            return await self.leads.list_leads(
                context.db,
                organization_id=context.organization_id,
                search=plan.text_query,
                lead_status=plan.status,
                current_user=context.user,
                page=1,
                limit=plan.limit,
            )
        if name == "search_contacts":
            return await self.contacts.list_contacts(
                context.db,
                page=1,
                limit=plan.limit,
                search=plan.text_query,
                current_user=context.user,
            )
        if name == "search_companies":
            return await self.companies.list_companies(
                context.db,
                page=1,
                limit=plan.limit,
                search=plan.text_query,
                current_user=context.user,
            )
        if name == "search_deals":
            return await self.deals.list_deals(
                context.db,
                organization_id=context.organization_id,
                search=plan.text_query,
                stage=plan.status,
                current_user=context.user,
                page=1,
                limit=plan.limit,
            )
        if name == "get_tasks":
            return await self.tasks.list_tasks(
                context.db,
                organization_id=context.organization_id,
                status=plan.status,
                search=plan.text_query,
                current_user=context.user,
                page=1,
                limit=plan.limit,
            )
        if name == "get_meetings":
            return await self.meetings.list_meetings(
                context.db,
                organization_id=context.organization_id,
                search=plan.text_query,
                current_user=context.user,
                page=1,
                limit=plan.limit,
            )
        if name == "search_projects":
            return await self.projects.list_projects(
                context.db,
                context.user,
                page=1,
                limit=plan.limit,
                search=plan.text_query,
                status=plan.status,
            )
        if name == "search_calls":
            return await self.calls.list_calls(
                context.db,
                page=1,
                limit=plan.limit,
                search=plan.text_query,
                current_user=context.user,
            )
        if name == "search_emails":
            return await self.emails.get_inbox(
                context.db,
                page=1,
                limit=plan.limit,
                search=plan.text_query,
                current_user=context.user,
            )
        if name == "search_notes":
            return await self.notes.list_notes(
                context.db,
                page=1,
                limit=plan.limit,
                search=plan.text_query,
                current_user=context.user,
            )
        if name == "search_documents":
            return await self.documents.list_documents(
                context.db,
                page=1,
                limit=plan.limit,
                search=plan.text_query,
                current_user=context.user,
            )
        if name == "search_products":
            records, _ = await self.products.list_products(
                context.db,
                user=context.user,
                page=1,
                limit=plan.limit,
                search=plan.text_query,
            )
            return records
        if name == "search_quotes":
            return await self.quotes.list_quotes(
                context.db,
                organization_id=context.organization_id,
                page=1,
                limit=plan.limit,
                status=plan.status,
                search=plan.text_query,
                current_user=context.user,
            )
        if name == "search_invoices":
            return await self.invoices.list_invoices(
                context.db,
                organization_id=context.organization_id,
                page=1,
                limit=plan.limit,
                status=plan.status,
                search=plan.text_query,
                current_user=context.user,
            )
        if name == "search_calendar_events":
            return await self.calendar.get_calendar_events(
                context.db,
                search=plan.text_query,
                page=1,
                limit=plan.limit,
                current_user=context.user,
            )
        if name == "search_activities":
            records, _ = await self.activities.list_activities(
                context.db,
                context.user,
                organization_id=context.organization_id,
                page=1,
                limit=plan.limit,
                module=None,
                search=plan.text_query,
            )
            return records
        if name == "search_users":
            return await self.users.list_users(
                context.db,
                page=1,
                limit=plan.limit,
                search=plan.text_query,
                current_user=context.user,
            )
        # These tools remain explicitly registered and validated. Until their
        # domain services expose equivalent scope-aware search contracts, use
        # the registry's bounded, tenant-aware query executor rather than a
        # broken or duplicated service implementation.
        return None


ai_tool_registry = AIToolRegistry()
