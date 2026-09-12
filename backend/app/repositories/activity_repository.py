from sqlalchemy import String, cast, func, literal, select, union_all
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    CalendarEventModel,
    CallLog,
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
    def _sources(
        organization_id: str,
        modules: set[str],
        *,
        user_id: str,
        whatsapp_permissions: set[str],
    ) -> list:
        sources = []
        null_string = cast(literal(None), String)

        if "leads" in modules:
            sources.append(
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
                .where(Lead.organization_id == organization_id)
            )
        if "deals" in modules:
            sources.append(
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
                .where(Deal.organization_id == organization_id)
            )
        if "tasks" in modules:
            sources.append(
                select(
                    Task.id.label("source_id"),
                    literal("tasks").label("module"),
                    literal("Task created").label("action"),
                    Task.title.label("description"),
                    literal("task").label("entity_type"),
                    Task.id.label("entity_id"),
                    null_string.label("actor_id"),
                    Task.created_at.label("occurred_at"),
                ).where(Task.organization_id == organization_id)
            )
        if "meetings" in modules:
            sources.append(
                select(
                    Meeting.id.label("source_id"),
                    literal("meetings").label("module"),
                    literal("Meeting scheduled").label("action"),
                    Meeting.title.label("description"),
                    literal("meeting").label("entity_type"),
                    Meeting.id.label("entity_id"),
                    null_string.label("actor_id"),
                    Meeting.created_at.label("occurred_at"),
                ).where(Meeting.organization_id == organization_id)
            )
        if "calls" in modules:
            sources.append(
                select(
                    CallLog.id.label("source_id"),
                    literal("calls").label("module"),
                    CallLog.call_type.label("action"),
                    func.coalesce(
                        CallLog.subject, CallLog.notes, literal("Call logged")
                    ).label("description"),
                    literal("call").label("entity_type"),
                    CallLog.id.label("entity_id"),
                    CallLog.created_by.label("actor_id"),
                    CallLog.timestamp.label("occurred_at"),
                ).where(CallLog.organization_id == organization_id)
            )
        if "emails" in modules:
            sources.append(
                select(
                    Email.id.label("source_id"),
                    literal("emails").label("module"),
                    (literal("Email ") + Email.status).label("action"),
                    Email.subject.label("description"),
                    literal("email").label("entity_type"),
                    Email.id.label("entity_id"),
                    null_string.label("actor_id"),
                    func.coalesce(Email.sent_at, Email.created_at).label("occurred_at"),
                ).where(Email.organization_id == organization_id)
            )
        if "notes" in modules:
            sources.append(
                select(
                    Note.id.label("source_id"),
                    literal("notes").label("module"),
                    literal("Note added").label("action"),
                    Note.content.label("description"),
                    Note.entity_type.label("entity_type"),
                    Note.entity_id.label("entity_id"),
                    Note.created_by.label("actor_id"),
                    Note.created_at.label("occurred_at"),
                ).where(Note.organization_id == organization_id)
            )
        if "calendar" in modules:
            sources.append(
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
                .where(User.organization_id == organization_id)
            )
        if "whatsapp" in modules:
            sources.append(
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
                .join(WhatsAppConversation, WhatsAppConversation.id == WhatsAppMessage.conversation_id)
                .where(
                    WhatsAppRepository.access_clause(
                        organization_id, user_id, whatsapp_permissions
                    )
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
        search: str | None,
    ):
        sources = cls._sources(
            organization_id,
            modules,
            user_id=user_id,
            whatsapp_permissions=whatsapp_permissions,
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
        page: int,
        limit: int,
        search: str | None,
    ) -> list:
        query = self._query(
            organization_id,
            modules,
            user_id=user_id,
            whatsapp_permissions=whatsapp_permissions,
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
