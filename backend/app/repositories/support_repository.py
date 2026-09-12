from sqlalchemy import String, cast, exists, func, literal, or_, select, union_all
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.record_access import record_access_filter
from app.models import (
    Company,
    Contact,
    Deal,
    Invoice,
    KnowledgeArticle,
    Quote,
    SalesOrder,
    SLAPolicy,
    Team,
    Ticket,
    TicketComment,
    TicketKnowledgeArticle,
    User,
)


class SupportRepository:
    async def next_ticket_number(self, db: AsyncSession, organization_id: str) -> str:
        from app.models import Organization

        org = await db.scalar(
            select(Organization).where(Organization.id == organization_id).with_for_update()
        )
        org.ticket_sequence += 1
        return f"{org.ticket_prefix}-{org.ticket_sequence:06d}"

    async def validate_links(self, db: AsyncSession, organization_id: str, **links):
        models = {
            "contact_id": Contact,
            "company_id": Company,
            "assigned_to": User,
            "team_id": Team,
            "sla_policy_id": SLAPolicy,
        }
        for key, value in links.items():
            if value is None or key not in models:
                continue
            model = models[key]
            org_column = User._organization_id if model is User else model.organization_id
            filters = [model.id == value, org_column == organization_id]
            if model in {User, Team}:
                filters.append(model.is_active.is_(True))
            if not await db.scalar(select(model.id).where(*filters)):
                return key
        return None

    async def list_tickets(
        self,
        db: AsyncSession,
        organization_id: str,
        *,
        search: str | None,
        status: str | None,
        priority: str | None,
        offset: int,
        limit: int,
        access=None,
    ):
        filters = [Ticket.organization_id == organization_id, Ticket.is_archived.is_(False)]
        access_filter = record_access_filter(
            access,
            assigned_column=Ticket.assigned_to,
            created_column=Ticket.created_by,
            team_column=Ticket.team_id,
        )
        if access_filter is not None:
            filters.append(access_filter)
        if search:
            filters.append(
                or_(
                    Ticket.subject.ilike(f"%{search.strip()}%"),
                    Ticket.ticket_number.ilike(f"%{search.strip()}%"),
                )
            )
        if status:
            filters.append(Ticket.status == status)
        if priority:
            filters.append(Ticket.priority == priority)
        rows = (
            await db.scalars(
                select(Ticket)
                .where(*filters)
                .order_by(Ticket.created_at.desc())
                .offset(offset)
                .limit(limit)
            )
        ).all()
        total = int(
            (await db.scalar(select(func.count()).select_from(Ticket).where(*filters))) or 0
        )
        return rows, total

    async def ticket(self, db: AsyncSession, organization_id: str, ticket_id: str, access=None):
        filters = [
            Ticket.id == ticket_id,
            Ticket.organization_id == organization_id,
            Ticket.is_archived.is_(False),
        ]
        access_filter = record_access_filter(
            access,
            assigned_column=Ticket.assigned_to,
            created_column=Ticket.created_by,
            team_column=Ticket.team_id,
        )
        if access_filter is not None:
            filters.append(access_filter)
        return await db.scalar(select(Ticket).where(*filters))

    async def list_comments(self, db: AsyncSession, ticket_id: str):
        return (
            await db.scalars(
                select(TicketComment)
                .where(TicketComment.ticket_id == ticket_id)
                .order_by(TicketComment.created_at)
            )
        ).all()

    async def list_ticket_articles(self, db: AsyncSession, ticket_id: str):
        return (
            await db.scalars(
                select(KnowledgeArticle)
                .join(
                    TicketKnowledgeArticle,
                    TicketKnowledgeArticle.article_id == KnowledgeArticle.id,
                )
                .where(TicketKnowledgeArticle.ticket_id == ticket_id)
                .order_by(KnowledgeArticle.title)
            )
        ).all()

    async def get_ticket_article_link(
        self, db: AsyncSession, ticket_id: str, article_id: str
    ) -> TicketKnowledgeArticle | None:
        return await db.scalar(
            select(TicketKnowledgeArticle).where(
                TicketKnowledgeArticle.ticket_id == ticket_id,
                TicketKnowledgeArticle.article_id == article_id,
            )
        )

    async def list_articles(
        self,
        db: AsyncSession,
        organization_id: str,
        *,
        search: str | None,
        status: str | None,
        offset: int,
        limit: int,
    ):
        filters = [KnowledgeArticle.organization_id == organization_id]
        if search:
            filters.append(
                or_(
                    KnowledgeArticle.title.ilike(f"%{search.strip()}%"),
                    KnowledgeArticle.summary.ilike(f"%{search.strip()}%"),
                )
            )
        if status:
            filters.append(KnowledgeArticle.status == status)
        rows = (
            await db.scalars(
                select(KnowledgeArticle)
                .where(*filters)
                .order_by(KnowledgeArticle.updated_at.desc())
                .offset(offset)
                .limit(limit)
            )
        ).all()
        total = int(
            (await db.scalar(select(func.count()).select_from(KnowledgeArticle).where(*filters)))
            or 0
        )
        return rows, total

    async def article(self, db: AsyncSession, organization_id: str, article_id: str):
        return await db.scalar(
            select(KnowledgeArticle).where(
                KnowledgeArticle.id == article_id,
                KnowledgeArticle.organization_id == organization_id,
            )
        )

    async def public_article(self, db: AsyncSession, organization_slug: str, article_slug: str):
        from app.models import Organization

        return await db.scalar(
            select(KnowledgeArticle)
            .join(Organization, Organization.id == KnowledgeArticle.organization_id)
            .where(
                Organization.slug == organization_slug,
                KnowledgeArticle.slug == article_slug,
                KnowledgeArticle.status == "Published",
                Organization.is_active.is_(True),
            )
        )

    async def customers(
        self,
        db: AsyncSession,
        organization_id: str,
        search: str | None,
        offset: int,
        limit: int,
        *,
        company_access=None,
        contact_access=None,
    ):
        company_is_customer = or_(
            exists(
                select(Deal.id).where(
                    Deal.organization_id == organization_id,
                    Deal.company_id == Company.id,
                    Deal.stage == "Closed Won",
                )
            ),
            exists(
                select(Quote.id).where(
                    Quote.organization_id == organization_id,
                    Quote.company_id == Company.id,
                    Quote.status == "Accepted",
                )
            ),
            exists(
                select(SalesOrder.id).where(
                    SalesOrder.organization_id == organization_id,
                    SalesOrder.company_id == Company.id,
                )
            ),
            exists(
                select(Invoice.id).where(
                    Invoice.organization_id == organization_id,
                    Invoice.company_id == Company.id,
                    Invoice.status.notin_(("Draft", "Cancelled")),
                )
            ),
        )
        contact_is_customer = or_(
            exists(
                select(Deal.id).where(
                    Deal.organization_id == organization_id,
                    Deal.contact_id == Contact.id,
                    Deal.stage == "Closed Won",
                )
            ),
            exists(
                select(Quote.id).where(
                    Quote.organization_id == organization_id,
                    Quote.contact_id == Contact.id,
                    Quote.status == "Accepted",
                )
            ),
            exists(
                select(SalesOrder.id).where(
                    SalesOrder.organization_id == organization_id,
                    SalesOrder.contact_id == Contact.id,
                )
            ),
            exists(
                select(Invoice.id).where(
                    Invoice.organization_id == organization_id,
                    Invoice.contact_id == Contact.id,
                    Invoice.status.notin_(("Draft", "Cancelled")),
                )
            ),
        )
        company_filters = [Company.organization_id == organization_id, company_is_customer]
        contact_filters = [Contact.organization_id == organization_id, contact_is_customer]
        company_scope = record_access_filter(
            company_access,
            assigned_column=Company.owner_id,
            created_column=Company.created_by,
        )
        contact_scope = record_access_filter(
            contact_access,
            assigned_column=Contact.owner_id,
            created_column=Contact.created_by,
        )
        if company_scope is not None:
            company_filters.append(company_scope)
        if contact_scope is not None:
            contact_filters.append(contact_scope)
        if search:
            pattern = f"%{search.strip()}%"
            company_filters.append(Company.name.ilike(pattern))
            contact_filters.append(or_(Contact.name.ilike(pattern), Contact.email.ilike(pattern)))

        open_statuses = ("New", "Open", "Pending")
        company_open_tickets = (
            select(func.count(Ticket.id))
            .where(
                Ticket.organization_id == organization_id,
                Ticket.company_id == Company.id,
                Ticket.status.in_(open_statuses),
                Ticket.is_archived.is_(False),
            )
            .correlate(Company)
            .scalar_subquery()
        )
        contact_open_tickets = (
            select(func.count(Ticket.id))
            .where(
                Ticket.organization_id == organization_id,
                Ticket.contact_id == Contact.id,
                Ticket.status.in_(open_statuses),
                Ticket.is_archived.is_(False),
            )
            .correlate(Contact)
            .scalar_subquery()
        )
        customers = union_all(
            select(
                literal("company").label("entity_type"),
                Company.id.label("entity_id"),
                Company.name.label("name"),
                cast(literal(None), String).label("email"),
                Company.id.label("company_id"),
                company_open_tickets.label("open_tickets"),
            ).where(*company_filters),
            select(
                literal("contact").label("entity_type"),
                Contact.id.label("entity_id"),
                Contact.name.label("name"),
                Contact.email.label("email"),
                Contact.company_id.label("company_id"),
                contact_open_tickets.label("open_tickets"),
            ).where(*contact_filters),
        ).subquery()
        rows = (
            (
                await db.execute(
                    select(customers)
                    .order_by(customers.c.name, customers.c.entity_id)
                    .offset(offset)
                    .limit(limit)
                )
            )
            .mappings()
            .all()
        )
        total = int((await db.scalar(select(func.count()).select_from(customers))) or 0)
        return [dict(row) for row in rows], total


support_repository = SupportRepository()
