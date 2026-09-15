from sqlalchemy import String, and_, cast, exists, false, func, literal, or_, select, union_all
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.record_access import RecordAccessContext, record_access_filter
from app.models import (
    CalendarEventModel,
    CallLog,
    Company,
    Contact,
    Deal,
    DealActivity,
    Email,
    Lead,
    LeadActivity,
    Meeting,
    Note,
    Task,
    User,
    WhatsAppConversation,
    WhatsAppMessage,
)
from app.repositories.whatsapp_repository import WhatsAppRepository


class ActivityRepository:
    @staticmethod
    def _with_access(
        query,
        access: RecordAccessContext,
        module_access: RecordAccessContext | None = None,
        **columns,
    ):
        for context in (access, module_access):
            if context is None:
                continue
            access_filter = record_access_filter(context, **columns)
            if access_filter is not None:
                query = query.where(access_filter)
        return query

    @staticmethod
    def _relationship_access(
        access: RecordAccessContext,
        module_access: dict[str, RecordAccessContext],
        organization_id: str,
        *,
        lead_id_column,
        contact_id_column,
        company_id_column,
        deal_id_column,
    ):
        """Authorize a channel event through both activity and linked-record scopes."""
        if access.scope == "none":
            return false()

        links = (
            ("leads", Lead, Lead.id, lead_id_column, Lead.assigned_to, Lead.created_by),
            (
                "contacts",
                Contact,
                Contact.id,
                contact_id_column,
                Contact.owner_id,
                Contact.created_by,
            ),
            (
                "companies",
                Company,
                Company.id,
                company_id_column,
                Company.owner_id,
                Company.created_by,
            ),
            ("deals", Deal, Deal.id, deal_id_column, Deal.assigned_to, Deal.created_by),
        )
        predicates = []
        populated_links = []
        for name, model, model_id, linked_id, assigned_column, created_column in links:
            populated_links.append(linked_id.is_not(None))
            constraints = [model_id == linked_id, model.organization_id == organization_id]
            for context in (access, module_access[name]):
                access_filter = record_access_filter(
                    context,
                    assigned_column=assigned_column,
                    created_column=created_column,
                )
                if access_filter is not None:
                    constraints.append(access_filter)
            # Every populated relationship must be visible. Using OR across
            # relationships would let an accessible contact disclose an event
            # also linked to an inaccessible lead/deal. Unlinked events remain
            # governed by the activity scope itself.
            predicates.append(
                or_(linked_id.is_(None), exists(select(model_id).where(and_(*constraints))))
            )
        if access.scope == "all":
            return and_(*predicates)
        return and_(or_(*populated_links), *predicates)

    @staticmethod
    def _sources(
        organization_id: str,
        modules: set[str],
        *,
        user_id: str,
        whatsapp_permissions: set[str],
        access: RecordAccessContext,
        module_access: dict[str, RecordAccessContext],
    ) -> list:
        sources = []
        null_string = cast(literal(None), String)

        if "leads" in modules:
            sources.append(
                ActivityRepository._with_access(
                    select(
                        LeadActivity.id.label("source_id"),
                        literal("leads").label("module"),
                        LeadActivity.action.label("action"),
                        LeadActivity.details.label("description"),
                        literal("lead").label("entity_type"),
                        LeadActivity.lead_id.label("entity_id"),
                        LeadActivity.performed_by.label("actor_id"),
                        LeadActivity.timestamp.label("occurred_at"),
                    )
                    .join(Lead, Lead.id == LeadActivity.lead_id)
                    .where(Lead.organization_id == organization_id),
                    access,
                    module_access["leads"],
                    assigned_column=Lead.assigned_to,
                    created_column=Lead.created_by,
                )
            )
        if "deals" in modules:
            sources.append(
                ActivityRepository._with_access(
                    select(
                        DealActivity.id.label("source_id"),
                        literal("deals").label("module"),
                        DealActivity.action.label("action"),
                        null_string.label("description"),
                        literal("deal").label("entity_type"),
                        DealActivity.deal_id.label("entity_id"),
                        DealActivity.performed_by.label("actor_id"),
                        DealActivity.timestamp.label("occurred_at"),
                    )
                    .join(Deal, Deal.id == DealActivity.deal_id)
                    .where(Deal.organization_id == organization_id),
                    access,
                    module_access["deals"],
                    assigned_column=Deal.assigned_to,
                    created_column=Deal.created_by,
                )
            )
        if "tasks" in modules:
            sources.append(
                ActivityRepository._with_access(
                    select(
                        Task.id.label("source_id"),
                        literal("tasks").label("module"),
                        literal("Task created").label("action"),
                        Task.title.label("description"),
                        literal("task").label("entity_type"),
                        Task.id.label("entity_id"),
                        null_string.label("actor_id"),
                        Task.created_at.label("occurred_at"),
                    ).where(Task.organization_id == organization_id),
                    access,
                    module_access["tasks"],
                    assigned_column=Task.assigned_to,
                    created_column=Task.created_by,
                )
            )
        if "meetings" in modules:
            meeting_query = select(
                Meeting.id.label("source_id"),
                literal("meetings").label("module"),
                literal("Meeting scheduled").label("action"),
                Meeting.title.label("description"),
                literal("meeting").label("entity_type"),
                Meeting.id.label("entity_id"),
                null_string.label("actor_id"),
                Meeting.created_at.label("occurred_at"),
            ).where(Meeting.organization_id == organization_id)
            meeting_access = ActivityRepository._relationship_access(
                access,
                module_access,
                organization_id,
                lead_id_column=Meeting.lead_id,
                contact_id_column=Meeting.contact_id,
                company_id_column=Meeting.company_id,
                deal_id_column=Meeting.deal_id,
            )
            sources.append(
                meeting_query.where(meeting_access) if meeting_access is not None else meeting_query
            )
        if "calls" in modules:
            sources.append(
                ActivityRepository._with_access(
                    select(
                        CallLog.id.label("source_id"),
                        literal("calls").label("module"),
                        CallLog.call_type.label("action"),
                        func.coalesce(CallLog.subject, CallLog.notes, literal("Call logged")).label(
                            "description"
                        ),
                        literal("call").label("entity_type"),
                        CallLog.id.label("entity_id"),
                        CallLog.created_by.label("actor_id"),
                        CallLog.timestamp.label("occurred_at"),
                    ).where(CallLog.organization_id == organization_id),
                    access,
                    assigned_column=CallLog.created_by,
                    created_column=CallLog.created_by,
                )
            )
        if "emails" in modules:
            email_query = select(
                Email.id.label("source_id"),
                literal("emails").label("module"),
                (literal("Email ") + Email.status).label("action"),
                Email.subject.label("description"),
                literal("email").label("entity_type"),
                Email.id.label("entity_id"),
                null_string.label("actor_id"),
                func.coalesce(Email.sent_at, Email.created_at).label("occurred_at"),
            ).where(Email.organization_id == organization_id)
            email_access = ActivityRepository._relationship_access(
                access,
                module_access,
                organization_id,
                lead_id_column=Email.lead_id,
                contact_id_column=Email.contact_id,
                company_id_column=Email.company_id,
                deal_id_column=Email.deal_id,
            )
            sources.append(
                email_query.where(email_access) if email_access is not None else email_query
            )
        if "notes" in modules:
            sources.append(
                ActivityRepository._with_access(
                    select(
                        Note.id.label("source_id"),
                        literal("notes").label("module"),
                        literal("Note added").label("action"),
                        Note.content.label("description"),
                        Note.entity_type.label("entity_type"),
                        Note.entity_id.label("entity_id"),
                        Note.created_by.label("actor_id"),
                        Note.created_at.label("occurred_at"),
                    ).where(Note.organization_id == organization_id),
                    access,
                    assigned_column=Note.created_by,
                    created_column=Note.created_by,
                )
            )
        if "calendar" in modules:
            sources.append(
                ActivityRepository._with_access(
                    select(
                        CalendarEventModel.id.label("source_id"),
                        literal("calendar").label("module"),
                        CalendarEventModel.event_type.label("action"),
                        CalendarEventModel.title.label("description"),
                        literal("calendar").label("entity_type"),
                        CalendarEventModel.id.label("entity_id"),
                        CalendarEventModel.user_id.label("actor_id"),
                        CalendarEventModel.created_at.label("occurred_at"),
                    )
                    .join(User, User.id == CalendarEventModel.user_id)
                    .where(User.organization_id == organization_id),
                    access,
                    assigned_column=CalendarEventModel.user_id,
                    created_column=CalendarEventModel.user_id,
                )
            )
        if "whatsapp" in modules:
            sources.append(
                ActivityRepository._with_access(
                    select(
                        WhatsAppMessage.id.label("source_id"),
                        literal("whatsapp").label("module"),
                        literal("WhatsApp message").label("action"),
                        WhatsAppMessage.body.label("description"),
                        literal("whatsapp_conversation").label("entity_type"),
                        WhatsAppMessage.conversation_id.label("entity_id"),
                        WhatsAppMessage.actor_user_id.label("actor_id"),
                        func.coalesce(
                            WhatsAppMessage.provider_timestamp, WhatsAppMessage.created_at
                        ).label("occurred_at"),
                    )
                    .join(
                        WhatsAppConversation,
                        WhatsAppConversation.id == WhatsAppMessage.conversation_id,
                    )
                    .where(
                        WhatsAppRepository.access_clause(
                            organization_id, user_id, whatsapp_permissions
                        )
                    ),
                    access,
                    assigned_column=WhatsAppConversation.assigned_user_id,
                    created_column=WhatsAppConversation.assigned_user_id,
                )
            )
        return sources

    @classmethod
    def _query(
        cls,
        organization_id: str,
        modules: set[str],
        *,
        user_id: str,
        whatsapp_permissions: set[str],
        access: RecordAccessContext,
        module_access: dict[str, RecordAccessContext],
        search: str | None,
    ):
        sources = cls._sources(
            organization_id,
            modules,
            user_id=user_id,
            whatsapp_permissions=whatsapp_permissions,
            access=access,
            module_access=module_access,
        )
        if not sources:
            return None
        activity = union_all(*sources).subquery("crm_activity_feed")
        query = select(activity)
        if search and search.strip():
            pattern = f"%{search.strip()}%"
            query = query.where(
                activity.c.action.ilike(pattern) | activity.c.description.ilike(pattern)
            )
        return query

    async def list(
        self,
        db: AsyncSession,
        *,
        organization_id: str,
        modules: set[str],
        user_id: str,
        whatsapp_permissions: set[str],
        access: RecordAccessContext,
        module_access: dict[str, RecordAccessContext],
        page: int,
        limit: int,
        search: str | None,
    ) -> list:
        query = self._query(
            organization_id,
            modules,
            user_id=user_id,
            whatsapp_permissions=whatsapp_permissions,
            access=access,
            module_access=module_access,
            search=search,
        )
        if query is None:
            return []
        result = await db.execute(
            query.order_by(
                query.selected_columns.occurred_at.desc(),
                query.selected_columns.source_id.desc(),
            )
            .offset((page - 1) * limit)
            .limit(limit)
        )
        return list(result.mappings().all())

    async def count(self, db: AsyncSession, **kwargs) -> int:
        query = self._query(**kwargs)
        if query is None:
            return 0
        result = await db.execute(select(func.count()).select_from(query.subquery()))
        return int(result.scalar_one())


activity_repository = ActivityRepository()
