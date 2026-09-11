"""Customer-visible CRM context for verified WhatsApp contacts.

This module intentionally exposes a small allowlist of fields. Internal notes,
message bodies, documents, recordings, custom fields and other contacts are not
valid WhatsApp AI context.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Company,
    CompanyContact,
    Contact,
    Deal,
    Invoice,
    InvoiceItem,
    Payment,
    Project,
    Quote,
    QuoteItem,
    Task,
    User,
)
from app.models.whatsapp import WhatsAppContactIdentity, WhatsAppIntegration
from app.repositories.call_repository import CallRepository
from app.repositories.email_repository import EmailRepository
from app.repositories.meeting_repository import MeetingRepository
from app.repositories.whatsapp_repository import WhatsAppRepository
from app.schemas.whatsapp import CustomerAIPlan


class CustomerCRMContextService:
    """Resolve and render tenant-scoped, customer-safe CRM data by contact ID."""

    TOPIC_SOURCE: dict[str, str] = {
        "contact": "contact",
        "company": "company",
        "deal": "deal",
        "project": "project",
        "invoice": "invoice",
        "payment": "payment",
        "quote": "quote",
        "meeting": "meeting",
        "task": "task",
        "email": "email",
        "call": "call",
        "product": "product",
        "account_owner": "account_owner",
    }
    SOURCE_PERMISSION: dict[str, tuple[str, ...]] = {
        "contact": ("contacts:read",),
        "company": ("companies:read",),
        "deal": ("deals:read",),
        "project": ("projects:read", "deals:read"),
        "invoice": ("invoices:read",),
        "payment": ("invoices:read",),
        "quote": ("quotes:read",),
        "meeting": ("meetings:read",),
        "task": ("tasks:read",),
        "email": ("emails:read",),
        "call": ("calls:read",),
        "product": ("products:read", "invoices:read", "quotes:read"),
        "account_owner": ("deals:read",),
    }

    def __init__(
        self,
        whatsapp_repository: WhatsAppRepository | None = None,
        email_repository: EmailRepository | None = None,
        call_repository: CallRepository | None = None,
        meeting_repository: MeetingRepository | None = None,
    ) -> None:
        self.whatsapp_repository = whatsapp_repository or WhatsAppRepository()
        self.email_repository = email_repository or EmailRepository()
        self.call_repository = call_repository or CallRepository()
        self.meeting_repository = meeting_repository or MeetingRepository()

    async def answer(
        self,
        db: AsyncSession,
        config: WhatsAppIntegration,
        identity: WhatsAppContactIdentity,
        permissions: set[str],
        plan: CustomerAIPlan,
    ) -> str | None:
        """Revalidate the phone-to-contact binding, then fetch requested sources."""
        state, contact_id, _ = await self.whatsapp_repository.match(
            db, config, identity.normalized_phone_number
        )
        if (
            state != "MATCHED_CONTACT"
            or not contact_id
            or contact_id != identity.contact_id
            or "contacts:read" not in permissions
        ):
            return None

        requested: list[str] = (
            [*plan.sources] if plan.sources else [self.TOPIC_SOURCE.get(plan.topic, plan.topic)]
        )
        sources = list(dict.fromkeys(requested))[:4]
        if not sources or any(
            source not in self.SOURCE_PERMISSION
            or not set(self.SOURCE_PERMISSION[source]).issubset(permissions)
            for source in sources
        ):
            return None

        contact_email: str | None = None
        if {"email", "meeting"} & set(sources):
            contact_email = await db.scalar(
                select(Contact.email).where(
                    Contact.organization_id == config.organization_id,
                    Contact.id == contact_id,
                )
            )
            if not contact_email:
                return None

        sections: list[str] = []
        for source in sources:
            rendered = await self._render_source(
                db,
                organization_id=config.organization_id,
                contact_id=contact_id,
                contact_email=contact_email,
                source=source,
                plan=plan,
            )
            if rendered:
                sections.append(rendered)
        if not sections:
            return None
        answer = "\n\n".join(sections)
        return answer if len(answer) <= 1900 else answer[:1897].rstrip() + "..."

    async def _render_source(
        self,
        db: AsyncSession,
        *,
        organization_id: str,
        contact_id: str,
        source: str,
        plan: CustomerAIPlan,
        contact_email: str | None = None,
    ) -> str | None:
        limit = plan.limit
        reference = (plan.reference or "").strip()
        # Reused branch-local query names are explicitly dynamic so SQLAlchemy's
        # generic Select types do not incorrectly bind every branch to Deal.
        stmt: Any
        rows: Any

        if source == "contact":
            contact = await db.scalar(
                select(Contact).where(
                    Contact.organization_id == organization_id, Contact.id == contact_id
                )
            )
            if not contact:
                return None
            masked_email = self._mask_email(contact.email)
            return f"Your CRM contact is {contact.name}. Email: {masked_email}."

        if source == "company":
            companies = list(
                (
                    await db.scalars(
                        select(Company)
                        .where(
                            Company.organization_id == organization_id,
                            or_(
                                Company.id
                                == select(Contact.company_id)
                                .where(
                                    Contact.organization_id == organization_id,
                                    Contact.id == contact_id,
                                )
                                .scalar_subquery(),
                                Company.id.in_(
                                    select(CompanyContact.company_id).where(
                                        CompanyContact.contact_id == contact_id
                                    )
                                ),
                            ),
                        )
                        .order_by(Company.name)
                        .limit(limit)
                    )
                ).all()
            )
            return self._bullets("Your associated companies:", [row.name for row in companies])

        if source == "deal":
            stmt = select(Deal).where(
                Deal.organization_id == organization_id, Deal.contact_id == contact_id
            )
            if reference:
                stmt = stmt.where(Deal.title.ilike(f"%{reference}%"))
            rows = list(
                (await db.scalars(stmt.order_by(Deal.created_at.desc()).limit(limit))).all()
            )
            return self._bullets(
                "Your deals:",
                [
                    f"{row.title} — {row.stage}"
                    + (
                        f", expected close {self._date(row.expected_close_date)}"
                        if row.expected_close_date
                        else ""
                    )
                    for row in rows
                ],
            )

        if source == "project":
            stmt = (
                select(Project)
                .join(Deal, Deal.project_id == Project.id)
                .where(
                    Deal.organization_id == organization_id,
                    Deal.contact_id == contact_id,
                    Project.organization_id == organization_id,
                )
                .distinct()
            )
            if reference:
                stmt = stmt.where(Project.name.ilike(f"%{reference}%"))
            rows = list(
                (await db.scalars(stmt.order_by(Project.updated_at.desc()).limit(limit))).all()
            )
            return self._bullets(
                "Your projects:",
                [
                    f"{row.name} — {row.status}, {row.completion_percentage}% complete"
                    + (f", due {self._date(row.due_date)}" if row.due_date else "")
                    for row in rows
                ],
            )

        if source == "invoice":
            stmt = select(Invoice).where(
                Invoice.organization_id == organization_id,
                Invoice.contact_id == contact_id,
                Invoice.status.in_(["Finalized", "Accepted"]),
                Invoice.sent_at.is_not(None),
            )
            if reference:
                stmt = stmt.where(Invoice.invoice_number.ilike(f"%{reference}%"))
            rows = list(
                (await db.scalars(stmt.order_by(Invoice.created_at.desc()).limit(limit))).all()
            )
            return self._bullets(
                "Your invoices:",
                [
                    f"{row.invoice_number} — {row.payment_status}, outstanding "
                    f"{row.currency} {self._money(row.amount - row.paid_amount)}, "
                    f"due {self._date(row.due_date)}"
                    for row in rows
                ],
            )

        if source == "payment":
            stmt = (
                select(Payment, Invoice.invoice_number)
                .join(
                    Invoice,
                    and_(
                        Invoice.id == Payment.invoice_id,
                        Invoice.organization_id == Payment.organization_id,
                    ),
                )
                .where(
                    Payment.organization_id == organization_id,
                    Invoice.contact_id == contact_id,
                    Invoice.sent_at.is_not(None),
                    Payment.status == "Succeeded",
                )
            )
            if reference:
                stmt = stmt.where(Invoice.invoice_number.ilike(f"%{reference}%"))
            rows = (
                await db.execute(
                    stmt.order_by(Payment.paid_at.desc(), Payment.id.desc()).limit(limit)
                )
            ).all()
            return self._bullets(
                "Your recent payments:",
                [
                    f"{payment.payment_number} for {invoice_number} — {payment.currency} "
                    f"{self._money(payment.amount)} on {payment.payment_date.isoformat()}"
                    for payment, invoice_number in rows
                ],
            )

        if source == "quote":
            stmt = select(Quote).where(
                Quote.organization_id == organization_id,
                Quote.contact_id == contact_id,
                Quote.sent_at.is_not(None),
                Quote.status.in_(["Sent", "Accepted", "Rejected", "Expired"]),
            )
            if reference:
                stmt = stmt.where(Quote.quote_number.ilike(f"%{reference}%"))
            rows = list(
                (await db.scalars(stmt.order_by(Quote.created_at.desc()).limit(limit))).all()
            )
            return self._bullets(
                "Your quotes:",
                [
                    f"{row.quote_number} — {row.status}, {row.currency or ''} "
                    f"{self._money(row.total_amount)}"
                    for row in rows
                ],
            )

        if source == "meeting":
            start, end = self._time_window(plan.time_scope)
            if not contact_email:
                contact_email = await db.scalar(
                    select(Contact.email).where(
                        Contact.organization_id == organization_id, Contact.id == contact_id
                    )
                )
            if not contact_email:
                return None
            statuses = None if plan.time_scope == "recent" else ["Scheduled"]
            rows = await self.meeting_repository.list_for_contact(
                db,
                organization_id=organization_id,
                contact_id=contact_id,
                contact_email=contact_email,
                limit=limit,
                search=reference or None,
                statuses=statuses,
                start=start,
                end=end,
                newest_first=plan.time_scope == "recent",
            )
            if not rows:
                return "I couldn't find any matching meetings in your CRM."
            return self._bullets(
                "Your meetings:",
                [
                    f"{row.title} — {self._datetime(row.start_time)}"
                    + (f" at {row.location}" if row.location else "")
                    for row in rows
                ],
            )

        if source == "task":
            stmt = select(Task).where(
                Task.organization_id == organization_id, Task.contact_id == contact_id
            )
            if plan.time_scope != "latest":
                start, end = self._time_window(plan.time_scope)
                stmt = stmt.where(Task.due_date >= start)
                if end:
                    stmt = stmt.where(Task.due_date < end)
            order = Task.due_date.desc() if plan.time_scope == "recent" else Task.due_date
            rows = list((await db.scalars(stmt.order_by(order).limit(limit))).all())
            return self._bullets(
                "Your tasks:",
                [f"{row.status} — due {self._date(row.due_date)}" for row in rows],
            )

        if source == "email":
            if not contact_email:
                contact_email = await db.scalar(
                    select(Contact.email).where(
                        Contact.organization_id == organization_id, Contact.id == contact_id
                    )
                )
            if not contact_email:
                return None
            rows = await self.email_repository.list_for_contact(
                db,
                organization_id=organization_id,
                contact_id=contact_id,
                recipient_email=contact_email,
                limit=limit,
                statuses=["Sent"],
                search=reference or None,
            )
            total = await self.email_repository.count_for_contact(
                db,
                organization_id=organization_id,
                contact_id=contact_id,
                recipient_email=contact_email,
                statuses=["Sent"],
                search=reference or None,
            )
            if not rows:
                return "I couldn't find any matching emails in your CRM history."
            title = (
                f"You have {total} matching CRM email{'s' if total != 1 else ''}."
                if reference
                else f"You have {total} CRM email{'s' if total != 1 else ''} sent to you."
            )
            if total > len(rows):
                title += f" Here are the {len(rows)} most recent:"
            return self._bullets(
                title,
                [
                    f"{row.subject} — {self._datetime(row.sent_at or row.created_at)}; "
                    f"from {row.from_email} to {row.to_email}"
                    for row in rows
                ],
            )

        if source == "call":
            call_start: datetime | None = None
            call_end: datetime | None = None
            if plan.time_scope not in {"latest", "upcoming"}:
                call_start, call_end = self._time_window(plan.time_scope)
            rows = await self.call_repository.list_by_contact(
                db,
                organization_id=organization_id,
                contact_id=contact_id,
                limit=limit,
                search=reference or None,
                start=call_start,
                end=call_end,
            )
            if not rows:
                return "I couldn't find any matching calls in your CRM history."
            return self._bullets(
                "Your recent calls:",
                [
                    f"{row.subject or row.call_type + ' call'} — {self._datetime(row.timestamp)}, "
                    f"{row.disposition or 'status unavailable'}, {row.duration_seconds // 60} min"
                    for row in rows
                ],
            )

        if source == "product":
            invoice_products = await db.scalars(
                select(InvoiceItem.product_name)
                .join(Invoice, Invoice.id == InvoiceItem.invoice_id)
                .where(
                    Invoice.organization_id == organization_id,
                    Invoice.contact_id == contact_id,
                    Invoice.sent_at.is_not(None),
                    Invoice.status.in_(["Finalized", "Accepted"]),
                )
                .order_by(Invoice.created_at.desc())
                .limit(limit)
            )
            quote_products = await db.scalars(
                select(QuoteItem.product_name)
                .join(Quote, Quote.id == QuoteItem.quote_id)
                .where(
                    Quote.organization_id == organization_id,
                    Quote.contact_id == contact_id,
                    Quote.sent_at.is_not(None),
                    Quote.status.in_(["Sent", "Accepted"]),
                )
                .order_by(Quote.created_at.desc())
                .limit(limit)
            )
            names = list(
                dict.fromkeys(name for name in [*invoice_products, *quote_products] if name)
            )[:limit]
            return self._bullets("Products on your sent documents:", names)

        if source == "account_owner":
            owner = await db.scalar(
                select(User.name)
                .join(Deal, Deal.assigned_to == User.id)
                .where(
                    Deal.organization_id == organization_id,
                    Deal.contact_id == contact_id,
                    User.organization_id == organization_id,
                    User.is_active.is_(True),
                )
                .order_by(Deal.created_at.desc())
                .limit(1)
            )
            return f"{owner} is handling your account." if owner else None
        return None

    @staticmethod
    def _bullets(title: str, lines: list[str]) -> str | None:
        return f"{title}\n" + "\n".join(f"• {line}" for line in lines) if lines else None

    @staticmethod
    def _mask_email(email: str) -> str:
        local, separator, domain = email.partition("@")
        if not separator:
            return "not available"
        visible = local[:2]
        return f"{visible}{'*' * max(3, len(local) - len(visible))}@{domain}"

    @staticmethod
    def _money(value: Decimal | float) -> str:
        return f"{value:.2f}"

    @staticmethod
    def _date(value: Any) -> str:
        return value.date().isoformat()

    @staticmethod
    def _datetime(value: Any | None) -> str:
        return value.isoformat() if value else "time unavailable"

    @staticmethod
    def _time_window(scope: str) -> tuple[datetime, datetime | None]:
        now = datetime.now(UTC)
        today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        if scope == "today":
            return today, today + timedelta(days=1)
        if scope == "tomorrow":
            return today + timedelta(days=1), today + timedelta(days=2)
        if scope == "this_week":
            return now, today + timedelta(days=7 - today.weekday())
        if scope == "recent":
            return now - timedelta(days=7), now
        return now, None


customer_crm_context_service = CustomerCRMContextService()
