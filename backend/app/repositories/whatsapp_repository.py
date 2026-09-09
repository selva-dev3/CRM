"""Tenant-bound channel queries. Provider routing is the only global lookup."""

import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from sqlalchemy import and_, delete, exists, func, or_, select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.core.phone import normalize_phone
from app.models import (
    AuditLog,
    Contact,
    Deal,
    Integration,
    Invoice,
    Lead,
    Meeting,
    Notification,
    Organization,
    Payment,
    Quote,
    Task,
    User,
)
from app.models.whatsapp import (
    WhatsAppContactIdentity as Identity,
)
from app.models.whatsapp import (
    WhatsAppConversation as Conversation,
)
from app.models.whatsapp import (
    WhatsAppIntegration as Configuration,
)
from app.models.whatsapp import (
    WhatsAppMessage as Message,
)
from app.models.whatsapp import WhatsAppPhoneRepair as PhoneRepair
from app.models.whatsapp import (
    WhatsAppReadState as ReadState,
)
from app.models.whatsapp import WhatsAppTemplate as Template
from app.models.whatsapp import (
    WhatsAppWebhookEvent as Event,
)
from app.schemas.whatsapp import InboundEvent, StatusEvent, WebhookPayload


class WhatsAppRepository:
    @staticmethod
    async def flush(db: AsyncSession) -> None:
        await db.flush()

    @staticmethod
    def add_audit(
        db: AsyncSession,
        organization_id: str,
        action: str,
        entity_id: str,
        user_id: str | None = None,
    ) -> None:
        db.add(
            AuditLog(
                organization_id=organization_id,
                user_id=user_id,
                action=f"whatsapp.{action}",
                details=json.dumps({"entity_id": entity_id}),
            )
        )

    @staticmethod
    def add_notification(
        db: AsyncSession, conversation: Conversation, user_id: str, reason: str
    ) -> None:
        db.add(
            Notification(
                organization_id=conversation.organization_id,
                user_id=user_id,
                event_name="whatsapp.attention",
                entity_type="whatsapp_conversation",
                entity_id=conversation.id,
                title="WhatsApp requires attention",
                message=reason,
            )
        )

    @staticmethod
    async def create_configuration(
        db: AsyncSession,
        organization_id: str,
        business_account_id: str,
        phone_number_id: str,
        api_version: str,
    ) -> tuple[Integration, Configuration]:
        catalog = Integration(
            id=str(uuid4()),
            organization_id=organization_id,
            name="WhatsApp",
            provider="whatsapp",
            status="disconnected",
            is_connected=False,
        )
        db.add(catalog)
        await db.flush()
        config = Configuration(
            id=str(uuid4()),
            organization_id=organization_id,
            catalog_integration_id=catalog.id,
            business_account_id=business_account_id,
            phone_number_id=phone_number_id,
            api_version=api_version,
        )
        db.add(config)
        return catalog, config

    async def message_by_idempotency(
        self, db: AsyncSession, organization_id: str, integration_id: str, key: str
    ) -> Message | None:
        return await db.scalar(
            select(Message).where(
                Message.organization_id == organization_id,
                Message.integration_id == integration_id,
                Message.idempotency_key == key,
            )
        )

    @staticmethod
    def create_message(db: AsyncSession, **values: Any) -> Message:
        message = Message(**values)
        db.add(message)
        return message

    async def identity_by_id(
        self, db: AsyncSession, organization_id: str, identity_id: str, *, lock: bool = False
    ) -> Identity | None:
        query = select(Identity).where(
            Identity.id == identity_id, Identity.organization_id == organization_id
        )
        if lock:
            query = query.with_for_update()
        return await db.scalar(query)

    async def crm_record(
        self,
        db: AsyncSession,
        organization_id: str,
        entity_type: str,
        entity_id: str,
        *,
        lock: bool = False,
    ) -> Contact | Lead | None:
        model = Contact if entity_type == "contact" else Lead
        query = select(model).where(model.id == entity_id, model.organization_id == organization_id)
        if lock:
            query = query.with_for_update()
        return await db.scalar(query)

    async def conversations_for_identity(
        self, db: AsyncSession, organization_id: str, identity_id: str, *, lock: bool = False
    ) -> list[Conversation]:
        query = select(Conversation).where(
            Conversation.organization_id == organization_id,
            Conversation.identity_id == identity_id,
        )
        if lock:
            query = query.with_for_update()
        return list((await db.execute(query)).scalars().all())

    async def message(
        self,
        db: AsyncSession,
        organization_id: str,
        conversation_id: str,
        message_id: str,
        *,
        inbound_only: bool = False,
    ) -> Message | None:
        query = select(Message).where(
            Message.id == message_id,
            Message.organization_id == organization_id,
            Message.conversation_id == conversation_id,
        )
        if inbound_only:
            query = query.where(Message.direction == "INBOUND")
        return await db.scalar(query)

    @staticmethod
    async def mark_read(
        db: AsyncSession,
        conversation: Conversation,
        user_id: str,
        read_through: datetime,
    ) -> None:
        await db.execute(
            insert(ReadState)
            .values(
                id=str(uuid4()),
                organization_id=conversation.organization_id,
                integration_id=conversation.integration_id,
                conversation_id=conversation.id,
                user_id=user_id,
                last_read_at=read_through,
            )
            .on_conflict_do_update(
                index_elements=["conversation_id", "user_id"],
                set_={"last_read_at": func.greatest(ReadState.last_read_at, read_through)},
            )
        )

    async def templates(self, db: AsyncSession, organization_id: str) -> list[Template]:
        return list(
            (
                await db.execute(
                    select(Template)
                    .where(Template.organization_id == organization_id)
                    .order_by(Template.name, Template.language)
                )
            )
            .scalars()
            .all()
        )

    async def template(self, db: AsyncSession, organization_id: str, template_id: str) -> Template:
        row = (
            await db.execute(
                select(Template).where(
                    Template.id == template_id, Template.organization_id == organization_id
                )
            )
        ).scalar_one_or_none()
        if row is None:
            raise NotFoundError(message="WhatsApp template not found.")
        return row

    async def replace_templates(
        self, db: AsyncSession, config: Configuration, records: list[dict]
    ) -> None:
        import re

        seen: set[str] = set()
        for record in records:
            provider_id, name, language = (
                record.get("id"),
                record.get("name"),
                record.get("language"),
            )
            category, status = record.get("category"), record.get("status")
            if not all(
                isinstance(v, str) and v for v in (provider_id, name, language, category, status)
            ):
                raise ValueError("Malformed provider template")
            components = record.get("components", [])
            if not isinstance(components, list):
                raise ValueError("Malformed provider template components")
            body = next(
                (
                    item.get("text", "")
                    for item in components
                    if isinstance(item, dict) and item.get("type") == "BODY"
                ),
                "",
            )
            indices = sorted({int(value) for value in re.findall(r"\{\{(\d+)\}\}", body)})
            unsupported_parameters = any(
                re.search(r"\{\{\d+\}\}", json.dumps(item))
                for item in components
                if isinstance(item, dict) and item.get("type") != "BODY"
            )
            if indices and indices != list(range(1, indices[-1] + 1)):
                raise ValueError("Template body parameters must be contiguous")
            count = indices[-1] if indices else 0
            normalized_status = "UNSUPPORTED" if unsupported_parameters else status[:30].upper()
            await db.execute(
                insert(Template)
                .values(
                    id=str(uuid4()),
                    organization_id=config.organization_id,
                    integration_id=config.id,
                    provider_template_id=provider_id[:100],
                    name=name[:512],
                    language=language[:20],
                    category=category[:30].upper(),
                    status=normalized_status,
                    body_parameter_count=count,
                )
                .on_conflict_do_update(
                    index_elements=["integration_id", "provider_template_id"],
                    set_={
                        "name": name[:512],
                        "language": language[:20],
                        "category": category[:30].upper(),
                        "status": normalized_status,
                        "body_parameter_count": count,
                        "updated_at": datetime.now(UTC),
                    },
                )
            )
            seen.add(provider_id[:100])
        stale = update(Template).where(
            Template.organization_id == config.organization_id,
            Template.integration_id == config.id,
        )
        if seen:
            stale = stale.where(Template.provider_template_id.not_in(seen))
        await db.execute(stale.values(status="UNAVAILABLE"))

    async def customer_answer(
        self,
        db: AsyncSession,
        config: Configuration,
        identity: Identity,
        permissions: set[str],
        topic: str,
    ) -> str | None:
        # Re-resolve on every query. A persisted link cannot outlive phone verification.
        state, contact_id, lead_id = await self.match(db, config, identity.normalized_phone_number)
        if state == "MATCHED_LEAD" and lead_id == identity.lead_id and "leads:read" in permissions:
            lead = (
                await db.execute(
                    select(Lead).where(
                        Lead.id == lead_id, Lead.organization_id == config.organization_id
                    )
                )
            ).scalar_one_or_none()
            if lead is None:
                return None
            if topic == "lead":
                # Qualification notes are internal free text and are not customer-visible.
                return f"Your enquiry status is {lead.status}."
            if topic == "account_owner" and lead.assigned_to:
                owner = await db.scalar(
                    select(User.name).where(
                        User.id == lead.assigned_to,
                        User.organization_id == config.organization_id,
                        User.is_active.is_(True),
                    )
                )
                return f"{owner} is handling your enquiry." if owner else None
            if topic == "meeting" and "meetings:read" in permissions:
                meeting = await db.scalar(
                    select(Meeting)
                    .where(
                        Meeting.organization_id == config.organization_id,
                        Meeting.lead_id == lead_id,
                        Meeting.status == "Scheduled",
                        Meeting.start_time >= datetime.now(UTC),
                    )
                    .order_by(Meeting.start_time)
                    .limit(1)
                )
                return (
                    f"Your upcoming meeting is at {meeting.start_time.isoformat()}."
                    if meeting
                    else None
                )
            if topic == "task" and "tasks:read" in permissions:
                task = await db.scalar(
                    select(Task)
                    .where(Task.organization_id == config.organization_id, Task.lead_id == lead_id)
                    .order_by(Task.due_date)
                    .limit(1)
                )
                return (
                    f"Your task is {task.status} and due {task.due_date.date().isoformat()}."
                    if task
                    else None
                )
            return None
        if (
            state != "MATCHED_CONTACT"
            or contact_id != identity.contact_id
            or "contacts:read" not in permissions
        ):
            return None
        if topic == "invoice" and "invoices:read" in permissions:
            rows = (
                (
                    await db.execute(
                        select(Invoice)
                        .where(
                            Invoice.organization_id == config.organization_id,
                            Invoice.contact_id == contact_id,
                            Invoice.status.in_(["Finalized", "Accepted"]),
                            Invoice.sent_at.is_not(None),
                        )
                        .order_by(Invoice.created_at.desc())
                        .limit(3)
                    )
                )
                .scalars()
                .all()
            )
            return (
                "\n\n".join(
                    f"Invoice {r.invoice_number}: {r.payment_status}\nTotal: {r.currency} {r.amount:.2f}\nPaid: {r.currency} {r.paid_amount:.2f}\nOutstanding: {r.currency} {r.amount - r.paid_amount:.2f}\nDue: {r.due_date.date().isoformat()}"
                    for r in rows
                )
                or None
            )
        if topic == "payment" and "invoices:read" in permissions:
            rows = (
                await db.execute(
                    select(Payment, Invoice.invoice_number)
                    .join(
                        Invoice,
                        and_(
                            Invoice.id == Payment.invoice_id,
                            Invoice.organization_id == Payment.organization_id,
                        ),
                    )
                    .where(
                        Payment.organization_id == config.organization_id,
                        Invoice.contact_id == contact_id,
                        Invoice.sent_at.is_not(None),
                        Payment.status == "Succeeded",
                    )
                    .order_by(Payment.paid_at.desc(), Payment.id.desc())
                    .limit(3)
                )
            ).all()
            return (
                "\n".join(
                    f"Payment {payment.payment_number} for invoice {invoice_number}: "
                    f"{payment.currency} {payment.amount:.2f} received on "
                    f"{payment.payment_date.isoformat()}."
                    for payment, invoice_number in rows
                )
                or None
            )
        if topic == "quote" and "quotes:read" in permissions:
            rows = (
                (
                    await db.execute(
                        select(Quote)
                        .where(
                            Quote.organization_id == config.organization_id,
                            Quote.contact_id == contact_id,
                            Quote.sent_at.is_not(None),
                            Quote.status.in_(["Sent", "Accepted", "Rejected", "Expired"]),
                        )
                        .order_by(Quote.created_at.desc())
                        .limit(3)
                    )
                )
                .scalars()
                .all()
            )
            return (
                "\n\n".join(
                    f"Quote {r.quote_number}: {r.status}\nTotal: {r.currency or ''} {r.total_amount:.2f}"
                    for r in rows
                )
                or None
            )
        if topic == "meeting" and "meetings:read" in permissions:
            rows = (
                (
                    await db.execute(
                        select(Meeting)
                        .where(
                            Meeting.organization_id == config.organization_id,
                            Meeting.contact_id == contact_id,
                            Meeting.status == "Scheduled",
                            Meeting.start_time >= datetime.now(UTC),
                        )
                        .order_by(Meeting.start_time)
                        .limit(3)
                    )
                )
                .scalars()
                .all()
            )
            return (
                "\n".join(f"Your upcoming meeting is at {r.start_time.isoformat()}." for r in rows)
                or None
            )
        if topic == "deal" and "deals:read" in permissions:
            deal = await db.scalar(
                select(Deal)
                .where(
                    Deal.organization_id == config.organization_id, Deal.contact_id == contact_id
                )
                .order_by(Deal.created_at.desc())
                .limit(1)
            )
            return f"Your deal stage is {deal.stage}." if deal else None
        if topic == "task" and "tasks:read" in permissions:
            task = await db.scalar(
                select(Task)
                .where(
                    Task.organization_id == config.organization_id, Task.contact_id == contact_id
                )
                .order_by(Task.due_date)
                .limit(1)
            )
            return (
                f"Your task is {task.status} and due {task.due_date.date().isoformat()}."
                if task
                else None
            )
        if topic == "account_owner":
            owner = await db.scalar(
                select(User.name)
                .join(Deal, Deal.assigned_to == User.id)
                .where(
                    Deal.organization_id == config.organization_id,
                    Deal.contact_id == contact_id,
                    User.organization_id == config.organization_id,
                    User.is_active.is_(True),
                )
                .order_by(Deal.created_at.desc())
                .limit(1)
            )
            return f"{owner} is handling your account." if owner else None
        return None

    async def configuration(
        self, db: AsyncSession, organization_id: str, *, lock: bool = False
    ) -> Configuration | None:
        query = select(Configuration).where(Configuration.organization_id == organization_id)
        if lock:
            query = query.with_for_update()
        return (await db.execute(query)).scalar_one_or_none()

    async def organization_active(self, db: AsyncSession, organization_id: str) -> bool:
        return bool(
            await db.scalar(
                select(Organization.id).where(
                    Organization.id == organization_id,
                    Organization.is_active.is_(True),
                    func.lower(func.trim(Organization.status)) == "active",
                )
            )
        )

    async def next_phone_backfill_configuration(self, db: AsyncSession) -> Configuration | None:
        return await db.scalar(
            select(Configuration)
            .join(Organization, Organization.id == Configuration.organization_id)
            .where(
                Configuration.enabled.is_(True),
                Configuration.phone_index_ready.is_(False),
                Organization.is_active.is_(True),
                func.lower(func.trim(Organization.status)) == "active",
            )
            .order_by(Configuration.updated_at, Configuration.id)
            .limit(1)
            .with_for_update(skip_locked=True)
        )

    async def prepare_crm_phone(
        self, db: AsyncSession, organization_id: str, record: Contact | Lead
    ) -> None:
        """Maintain a safe E.164 search index for normal CRM writes.

        Normalization is not verification. Any phone change revokes a prior
        WhatsApp ownership assertion until an administrator resolves it again.
        """
        config = await self.configuration(db, organization_id)
        previous_normalized = record.normalized_phone
        previous_verification = record.whatsapp_phone_verified_at
        expected_phone = record.phone
        if config is None:
            record.normalized_phone = None
            record.whatsapp_phone_verified_at = None
            return
        try:
            normalized = normalize_phone(record.phone or "", config.default_phone_region)
        except ValueError:
            normalized = None
        same_identity = normalized is not None and normalized == previous_normalized
        record.normalized_phone = normalized
        record.whatsapp_phone_verified_at = previous_verification if same_identity else None

        # Flush the phone write so the rollout trigger has run, then remove the
        # now-unnecessary repair item. The application has normalized this row
        # synchronously. Restore verification only when the E.164 identity did
        # not change; the trigger deliberately clears it for raw/bulk writes.
        await db.flush()
        if same_identity:
            model = Contact if isinstance(record, Contact) else Lead
            restored = await db.execute(
                update(model)
                .where(
                    model.organization_id == organization_id,
                    model.id == record.id,
                    model.phone == expected_phone,
                    model.normalized_phone == normalized,
                )
                .values(whatsapp_phone_verified_at=previous_verification)
            )
            if restored.rowcount != 1:
                # A stale ORM instance must never transfer verification onto a
                # database row whose phone identity has already changed.
                await db.refresh(record)
                return
            record.whatsapp_phone_verified_at = previous_verification
        entity_type = "contact" if isinstance(record, Contact) else "lead"
        await db.execute(
            delete(PhoneRepair).where(
                PhoneRepair.organization_id == organization_id,
                PhoneRepair.entity_type == entity_type,
                PhoneRepair.entity_id == record.id,
            )
        )

    async def detach_crm_identities(
        self,
        db: AsyncSession,
        organization_id: str,
        *,
        contact_ids: set[str] | None = None,
        lead_ids: set[str] | None = None,
    ) -> None:
        """Preserve message history while safely detaching deleted CRM records."""
        contact_ids = contact_ids or set()
        lead_ids = lead_ids or set()
        if not contact_ids and not lead_ids:
            return
        # Conversion, inbound matching, identity resolution, and deletion all
        # take this guard before entity/Identity row locks. Keeping it here also
        # covers every single and bulk deletion caller.
        await self.lock_phone_guard(db, organization_id)
        clauses = []
        if contact_ids:
            clauses.append(Identity.contact_id.in_(contact_ids))
        if lead_ids:
            clauses.append(Identity.lead_id.in_(lead_ids))
        identities = list(
            (
                await db.execute(
                    select(Identity)
                    .where(Identity.organization_id == organization_id, or_(*clauses))
                    .with_for_update()
                )
            )
            .scalars()
            .all()
        )
        for identity in identities:
            if identity.contact_id in contact_ids:
                identity.contact_id = None
            if identity.lead_id in lead_ids:
                identity.lead_id = None
            identity.state = "UNKNOWN"
            await db.execute(
                update(Conversation)
                .where(
                    Conversation.organization_id == organization_id,
                    Conversation.identity_id == identity.id,
                )
                .values(ai_enabled=False, status="HUMAN_HANDOFF")
            )

    async def catalog(self, db: AsyncSession, config: Configuration) -> Integration:
        row = (
            await db.execute(
                select(Integration).where(
                    Integration.id == config.catalog_integration_id,
                    Integration.organization_id == config.organization_id,
                    Integration.provider == "whatsapp",
                )
            )
        ).scalar_one_or_none()
        if row is None:
            raise NotFoundError(message="WhatsApp integration not found.")
        return row

    async def user(
        self, db: AsyncSession, organization_id: str, user_id: str | None
    ) -> User | None:
        if user_id is None:
            return None
        return (
            await db.execute(
                select(User).where(
                    User.id == user_id,
                    User.organization_id == organization_id,
                    User.is_active.is_(True),
                    User.is_platform_admin.is_(False),
                )
            )
        ).scalar_one_or_none()

    async def assignees(self, db: AsyncSession, organization_id: str) -> list[User]:
        return list(
            (
                await db.execute(
                    select(User)
                    .where(
                        User.organization_id == organization_id,
                        User.is_active.is_(True),
                        User.is_platform_admin.is_(False),
                    )
                    .order_by(User.name, User.id)
                    .limit(500)
                )
            )
            .scalars()
            .all()
        )

    async def default_conversation_assignee(
        self, db: AsyncSession, config: Configuration, identity: Identity
    ) -> str | None:
        candidate: str | None = None
        if identity.state == "MATCHED_LEAD" and identity.lead_id:
            candidate = await db.scalar(
                select(Lead.assigned_to).where(
                    Lead.id == identity.lead_id,
                    Lead.organization_id == config.organization_id,
                )
            )
        elif identity.state == "MATCHED_CONTACT" and identity.contact_id:
            candidate = await db.scalar(
                select(Deal.assigned_to)
                .where(
                    Deal.contact_id == identity.contact_id,
                    Deal.organization_id == config.organization_id,
                )
                .order_by(Deal.created_at.desc())
                .limit(1)
            )
        if await self.user(db, config.organization_id, candidate):
            return candidate
        if await self.user(db, config.organization_id, config.default_assignee_id):
            return config.default_assignee_id
        return None

    @staticmethod
    def access_clause(organization_id: str, user_id: str, permissions: set[str]):
        tenant = Conversation.organization_id == organization_id
        if "whatsapp:read_all" in permissions:
            return tenant
        if "whatsapp:read_assigned" not in permissions:
            return and_(tenant, False)
        related = exists(
            select(Identity.id).where(
                Identity.id == Conversation.identity_id,
                Identity.organization_id == organization_id,
                or_(
                    exists(
                        select(Lead.id).where(
                            Lead.id == Identity.lead_id,
                            Lead.organization_id == organization_id,
                            Lead.assigned_to == user_id,
                        )
                    ),
                    exists(
                        select(Deal.id).where(
                            Deal.contact_id == Identity.contact_id,
                            Deal.organization_id == organization_id,
                            Deal.assigned_to == user_id,
                        )
                    ),
                ),
            )
        )
        return and_(tenant, or_(Conversation.assigned_user_id == user_id, related))

    async def conversation(
        self,
        db: AsyncSession,
        organization_id: str,
        conversation_id: str,
        user_id: str,
        permissions: set[str],
        *,
        lock: bool = False,
    ) -> Conversation:
        query = select(Conversation).where(
            Conversation.id == conversation_id,
            self.access_clause(organization_id, user_id, permissions),
        )
        if lock:
            query = query.with_for_update()
        row = (await db.execute(query)).scalar_one_or_none()
        if row is None:
            raise NotFoundError(message="Conversation not found.")
        return row

    async def identity(self, db: AsyncSession, conversation: Conversation) -> Identity:
        row = (
            await db.execute(
                select(Identity).where(
                    Identity.id == conversation.identity_id,
                    Identity.organization_id == conversation.organization_id,
                    Identity.integration_id == conversation.integration_id,
                )
            )
        ).scalar_one_or_none()
        if row is None:
            raise NotFoundError(message="Conversation not found.")
        return row

    async def list_conversations(
        self,
        db: AsyncSession,
        organization_id: str,
        user_id: str,
        permissions: set[str],
        search: str,
        offset: int,
        limit: int,
    ) -> list[dict]:
        unread = (
            select(func.count(Message.id))
            .where(
                Message.organization_id == organization_id,
                Message.conversation_id == Conversation.id,
                Message.direction == "INBOUND",
                or_(ReadState.last_read_at.is_(None), Message.created_at > ReadState.last_read_at),
            )
            .correlate(Conversation, ReadState)
            .scalar_subquery()
        )
        query = (
            select(Conversation, Identity, unread)
            .join(
                Identity,
                and_(
                    Identity.id == Conversation.identity_id,
                    Identity.organization_id == organization_id,
                ),
            )
            .outerjoin(
                ReadState,
                and_(
                    ReadState.conversation_id == Conversation.id,
                    ReadState.user_id == user_id,
                    ReadState.organization_id == organization_id,
                ),
            )
            .where(self.access_clause(organization_id, user_id, permissions))
        )
        if search:
            query = query.where(Identity.normalized_phone_number.contains(search, autoescape=True))
        rows = (
            await db.execute(
                query.order_by(Conversation.last_message_at.desc().nullslast(), Conversation.id)
                .offset(offset)
                .limit(limit)
            )
        ).all()
        return [self.conversation_dict(c, i, n) for c, i, n in rows]

    @staticmethod
    def conversation_dict(c: Conversation, identity: Identity, unread: int = 0) -> dict:
        return {
            **{
                key: getattr(c, key)
                for key in (
                    "id",
                    "identity_id",
                    "status",
                    "ai_enabled",
                    "assigned_user_id",
                    "last_customer_message_at",
                    "last_message_at",
                )
            },
            "customer_phone": identity.normalized_phone_number,
            "identity_state": identity.state,
            "consent": identity.consent,
            "contact_id": identity.contact_id,
            "lead_id": identity.lead_id,
            "unread_count": unread,
        }

    async def messages(
        self, db: AsyncSession, conversation: Conversation, offset: int = 0, limit: int = 100
    ) -> list[Message]:
        rows = (
            (
                await db.execute(
                    select(Message)
                    .where(
                        Message.organization_id == conversation.organization_id,
                        Message.conversation_id == conversation.id,
                    )
                    .order_by(Message.created_at.desc(), Message.id.desc())
                    .offset(offset)
                    .limit(limit)
                )
            )
            .scalars()
            .all()
        )
        return list(reversed(rows))

    async def ingest(self, db: AsyncSession, payload: WebhookPayload, correlation_id: str) -> int:
        count = 0
        for entry in payload.entry:
            for change in entry.changes:
                # Never resolve tenant from headers, sender text, or a customer identifier.
                config = (
                    await db.execute(
                        select(Configuration).where(
                            Configuration.phone_number_id == change.value.metadata.phone_number_id,
                            Configuration.business_account_id == entry.id,
                        )
                    )
                ).scalar_one_or_none()
                if config is None:
                    continue
                config.last_webhook_at = datetime.now(UTC)
                for kind, events in (
                    ("message", change.value.messages),
                    ("status", change.value.statuses),
                ):
                    for event in events:
                        data = {
                            "kind": kind,
                            "data": event.model_dump(by_alias=True, exclude_none=True),
                        }
                        # Provider message identity is stable even when Meta retries
                        # it inside a slightly different envelope.
                        event_data = data["data"]
                        identity = {"kind": kind, "id": event_data.get("id")}
                        if kind == "status":
                            identity.update(
                                {
                                    "status": event_data.get("status"),
                                    "timestamp": event_data.get("timestamp"),
                                }
                            )
                        key = hashlib.sha256(
                            json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
                        ).hexdigest()
                        result = await db.execute(
                            insert(Event)
                            .values(
                                id=str(uuid4()),
                                organization_id=config.organization_id,
                                integration_id=config.id,
                                event_key=key,
                                correlation_id=correlation_id,
                                payload=data,
                                status="PENDING",
                                attempts=0,
                            )
                            .on_conflict_do_nothing(index_elements=["integration_id", "event_key"])
                            .returning(Event.id)
                        )
                        count += result.scalar_one_or_none() is not None
        return count

    async def match(
        self, db: AsyncSession, config: Configuration, phone: str
    ) -> tuple[str, str | None, str | None]:
        if not config.phone_index_ready:
            return "UNKNOWN", None, None
        # Serialize the authorization snapshot with import/update triggers.
        # This is organization-scoped and does not invalidate unrelated rows.
        await self.lock_phone_guard(db, config.organization_id)

        # Raw imports are deliberately repaired asynchronously. Until a pending
        # row with this number is normalized, an indexed match is not unique
        # enough to authorize customer-data disclosure.
        for model, entity_type in ((Contact, "contact"), (Lead, "lead")):
            pending_phones = (
                await db.execute(
                    select(model.phone)
                    .join(
                        PhoneRepair,
                        and_(
                            PhoneRepair.organization_id == model.organization_id,
                            PhoneRepair.entity_id == model.id,
                            PhoneRepair.entity_type == entity_type,
                        ),
                    )
                    .where(model.organization_id == config.organization_id)
                )
            ).scalars()
            for pending_phone in pending_phones:
                try:
                    if normalize_phone(pending_phone or "", config.default_phone_region) == phone:
                        return "AMBIGUOUS", None, None
                except ValueError:
                    continue
        # Include unverified duplicates when determining ambiguity. No first-row guessing.
        for model, state in ((Contact, "MATCHED_CONTACT"), (Lead, "MATCHED_LEAD")):
            query = (
                select(model)
                .where(
                    model.organization_id == config.organization_id, model.normalized_phone == phone
                )
                .limit(2)
            )
            rows = (await db.execute(query)).scalars().all()
            if len(rows) > 1:
                return "AMBIGUOUS", None, None
            if rows:
                row = rows[0]
                try:
                    current = normalize_phone(row.phone or "", config.default_phone_region)
                except ValueError:
                    continue
                if current != phone or row.whatsapp_phone_verified_at is None:
                    continue
                return (
                    state,
                    row.id if model is Contact else None,
                    row.id if model is Lead else None,
                )
        return "UNKNOWN", None, None

    async def lock_phone_guard(self, db: AsyncSession, organization_id: str) -> None:
        """Acquire the organization phone/identity lock before any related row lock."""
        await db.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:lock_key))"),
            {"lock_key": f"wa-phone:{organization_id}"},
        )

    async def backfill_phone_batch(self, db: AsyncSession, config: Configuration) -> bool:
        """Bounded resumable normalization; never infer ownership from legacy data."""
        if config.phone_index_ready:
            return True
        model = Contact if config.phone_backfill_stage == "contacts" else Lead
        query = select(model).where(model.organization_id == config.organization_id)
        if config.phone_backfill_cursor:
            query = query.where(model.id > config.phone_backfill_cursor)
        rows = (
            (await db.execute(query.order_by(model.id).limit(250).with_for_update()))
            .scalars()
            .all()
        )
        for row in rows:
            try:
                row.normalized_phone = normalize_phone(row.phone or "", config.default_phone_region)
            except ValueError:
                row.normalized_phone = None
            config.phone_backfill_cursor = row.id
        if len(rows) < 250:
            config.phone_backfill_cursor = None
            if config.phone_backfill_stage == "contacts":
                config.phone_backfill_stage = "leads"
            else:
                config.phone_index_ready = True
        return config.phone_index_ready

    async def repair_phone_batch(self, db: AsyncSession, limit: int = 250) -> int:
        """Repair raw-import phone indexes without granting phone ownership."""
        # Candidate discovery is intentionally unlocked. Each entity row is
        # locked before its repair row, matching the order used by CRM writes
        # and the database trigger and avoiding a repair/update deadlock.
        repairs = list(
            (
                await db.execute(
                    select(PhoneRepair)
                    .order_by(PhoneRepair.created_at, PhoneRepair.id)
                    .limit(limit)
                )
            )
            .scalars()
            .all()
        )
        processed = 0
        for candidate in repairs:
            record = await self.crm_record(
                db,
                candidate.organization_id,
                candidate.entity_type,
                candidate.entity_id,
                lock=True,
            )
            repair = (
                await db.execute(
                    select(PhoneRepair)
                    .where(
                        PhoneRepair.id == candidate.id,
                        PhoneRepair.organization_id == candidate.organization_id,
                    )
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if repair is None:
                continue
            config = await self.configuration(db, repair.organization_id)
            if config is not None and record is not None:
                try:
                    record.normalized_phone = normalize_phone(
                        record.phone or "", config.default_phone_region
                    )
                except ValueError:
                    record.normalized_phone = None
            await db.delete(repair)
            processed += 1
        return processed

    async def has_pending_inbound_events(
        self, db: AsyncSession, organization_id: str, integration_id: str
    ) -> bool:
        return bool(
            await db.scalar(
                select(Event.id)
                .where(
                    Event.organization_id == organization_id,
                    Event.integration_id == integration_id,
                    Event.status == "PENDING",
                    Event.payload["kind"].as_string() == "message",
                )
                .limit(1)
            )
        )

    async def link_converted_lead(self, db: AsyncSession, lead: Lead, contact: Contact) -> None:
        await self.lock_phone_guard(db, lead.organization_id)
        identities = (
            (
                await db.execute(
                    select(Identity)
                    .where(
                        Identity.organization_id == lead.organization_id,
                        Identity.lead_id == lead.id,
                    )
                    .with_for_update()
                )
            )
            .scalars()
            .all()
        )
        if not identities:
            return
        config = await self.configuration(db, lead.organization_id)
        if config is None:
            return
        try:
            phone = normalize_phone(contact.phone or "", config.default_phone_region)
        except ValueError:
            phone = None
        for identity in identities:
            # Conversion does not verify an existing Contact's phone ownership.
            identity.contact_id = contact.id
            identity.state = (
                "MATCHED_CONTACT"
                if phone == identity.normalized_phone_number and contact.whatsapp_phone_verified_at
                else "UNKNOWN"
            )

    async def timeline_messages(
        self,
        db: AsyncSession,
        user: User,
        permissions: set[str],
        *,
        contact_id: str | None = None,
        lead_id: str | None = None,
    ) -> list[Message]:
        query = (
            select(Message)
            .join(
                Conversation,
                and_(
                    Message.conversation_id == Conversation.id,
                    Message.organization_id == Conversation.organization_id,
                ),
            )
            .join(
                Identity,
                and_(
                    Identity.id == Conversation.identity_id,
                    Identity.organization_id == Conversation.organization_id,
                ),
            )
            .where(
                Message.organization_id == user.organization_id,
                self.access_clause(user.organization_id, user.id, permissions),
            )
        )
        query = (
            query.where(Identity.contact_id == contact_id)
            if contact_id
            else query.where(Identity.lead_id == lead_id)
        )
        return list(
            (await db.execute(query.order_by(Message.created_at.desc(), Message.id).limit(100)))
            .scalars()
            .all()
        )

    async def persist_inbound(
        self, db: AsyncSession, config: Configuration, event: InboundEvent
    ) -> tuple[Conversation, Message] | None:
        existing = await db.scalar(
            select(Message.id).where(
                Message.integration_id == config.id, Message.provider_message_id == event.id
            )
        )
        if existing:
            return None
        phone = normalize_phone(event.sender, provider=True)
        when = datetime.fromtimestamp(int(event.timestamp), UTC)
        if when > datetime.now(UTC) + timedelta(minutes=5):
            raise ValueError("Future provider timestamp")
        await self.lock_phone_guard(db, config.organization_id)
        await db.execute(
            insert(Identity)
            .values(
                id=str(uuid4()),
                organization_id=config.organization_id,
                integration_id=config.id,
                normalized_phone_number=phone,
                provider_verified_at=when,
                state="UNKNOWN",
                consent="UNKNOWN",
            )
            .on_conflict_do_nothing(index_elements=["integration_id", "normalized_phone_number"])
        )
        identity = (
            await db.execute(
                select(Identity)
                .where(
                    Identity.integration_id == config.id,
                    Identity.organization_id == config.organization_id,
                    Identity.normalized_phone_number == phone,
                )
                .with_for_update()
            )
        ).scalar_one()
        identity.state, identity.contact_id, identity.lead_id = await self.match(db, config, phone)
        assignee_id = await self.default_conversation_assignee(db, config, identity)
        await db.execute(
            insert(Conversation)
            .values(
                id=str(uuid4()),
                organization_id=config.organization_id,
                integration_id=config.id,
                identity_id=identity.id,
                status="OPEN",
                ai_enabled=bool(
                    config.enabled and config.ai_user_id and identity.state.startswith("MATCHED")
                ),
                assigned_user_id=assignee_id,
            )
            .on_conflict_do_nothing(index_elements=["identity_id"])
        )
        conversation = (
            await db.execute(
                select(Conversation)
                .where(
                    Conversation.organization_id == config.organization_id,
                    Conversation.identity_id == identity.id,
                )
                .with_for_update()
            )
        ).scalar_one()
        conversation.last_customer_message_at = max(
            filter(None, (conversation.last_customer_message_at, when))
        )
        conversation.last_message_at = max(filter(None, (conversation.last_message_at, when)))
        media = (
            getattr(event, event.type, None)
            if event.type in {"image", "audio", "video", "document"}
            else None
        )
        message = Message(
            id=str(uuid4()),
            organization_id=config.organization_id,
            integration_id=config.id,
            conversation_id=conversation.id,
            provider_message_id=event.id,
            idempotency_key=hashlib.sha256(event.id.encode()).hexdigest(),
            direction="INBOUND",
            source="CUSTOMER",
            message_type=event.type,
            body=event.text.body if event.type == "text" and event.text else None,
            media_metadata=media.model_dump(exclude_none=True) if media else None,
            sender_phone=phone,
            recipient_phone=config.display_phone_number or config.phone_number_id,
            status="RECEIVED",
            provider_timestamp=when,
            work_status="PENDING",
        )
        db.add(message)
        await db.flush()
        return conversation, message

    async def apply_status(
        self, db: AsyncSession, config: Configuration, event: StatusEvent
    ) -> bool:
        message = (
            await db.execute(
                select(Message)
                .where(
                    Message.organization_id == config.organization_id,
                    Message.integration_id == config.id,
                    Message.provider_message_id == event.id,
                    Message.direction == "OUTBOUND",
                )
                .with_for_update()
            )
        ).scalar_one_or_none()
        callback_id = event.biz_opaque_callback_data
        if message is None and callback_id:
            message = (
                await db.execute(
                    select(Message)
                    .where(
                        Message.id == callback_id,
                        Message.organization_id == config.organization_id,
                        Message.integration_id == config.id,
                        Message.direction == "OUTBOUND",
                    )
                    .with_for_update()
                )
            ).scalar_one_or_none()
        if message is None:
            return False  # A receipt can race the send response; retain and retry the inbox event.
        if normalize_phone(event.recipient_id, provider=True) != message.recipient_phone:
            raise ValueError("Receipt recipient mismatch")
        if message.provider_message_id and message.provider_message_id != event.id:
            raise ValueError("Receipt provider identity mismatch")
        if message.provider_message_id is None:
            collision = await db.scalar(
                select(Message.id).where(
                    Message.integration_id == config.id,
                    Message.provider_message_id == event.id,
                    Message.id != message.id,
                )
            )
            if collision:
                raise ValueError("Receipt provider identity collision")
            message.provider_message_id = event.id
        when = datetime.fromtimestamp(int(event.timestamp), UTC)
        state = event.status.upper()
        ranking = {
            "PENDING": 0,
            "PROCESSING": 0,
            "UNKNOWN": 0,
            "ACCEPTED": 1,
            "FAILED": 1,
            "SENT": 2,
            "DELIVERED": 3,
            "READ": 4,
        }
        if state == "FAILED":
            message.failed_at = message.failed_at or when
            message.error_code = str(event.errors[0].code) if event.errors else "PROVIDER_FAILED"
            if message.status not in {"DELIVERED", "READ"}:
                message.status = state
        else:
            setattr(message, f"{event.status}_at", getattr(message, f"{event.status}_at") or when)
            if ranking[state] > ranking.get(message.status, 0):
                message.status = state
        message.work_status = "DONE"
        return True
