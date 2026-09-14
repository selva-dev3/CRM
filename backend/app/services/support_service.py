import re
from datetime import UTC, datetime, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError
from app.core.permissions import effective_organization_id
from app.models import (
    KnowledgeArticle,
    Ticket,
    TicketComment,
    TicketKnowledgeArticle,
    TicketStatusHistory,
    User,
)
from app.repositories.support_repository import support_repository
from app.schemas.support import (
    KnowledgeArticleCreate,
    KnowledgeArticleUpdate,
    TicketCommentCreate,
    TicketCreate,
    TicketUpdate,
)
from app.services.auth_service import api_key_scope_allows, auth_service
from app.services.crm_relationship_service import validate_crm_relationships
from app.services.record_access_service import record_access_service


class SupportService:
    STATUS_TRANSITIONS = {
        "New": {"Open", "Pending", "Resolved"},
        "Open": {"Pending", "Resolved"},
        "Pending": {"Open", "Resolved"},
        "Resolved": {"Open", "Closed"},
        "Closed": {"Open"},
    }
    @staticmethod
    def org(user: User) -> str:
        value = effective_organization_id(user)
        if not value:
            raise NotFoundError(message="Organization not found")
        return value

    @staticmethod
    def slug(value: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
        if not slug:
            raise ConflictError(message="Article slug is invalid")
        return slug

    async def list_tickets(self, db, user, search, ticket_status, priority, page, limit):
        from app.services.record_access_service import record_access_service

        access = await record_access_service.resolve(db, user, "tickets")
        return await support_repository.list_tickets(
            db,
            self.org(user),
            search=search,
            status=ticket_status,
            priority=priority,
            offset=(page - 1) * limit,
            limit=limit,
            access=access,
        )

    async def ticket(self, db, user, ticket_id):
        from app.services.record_access_service import record_access_service

        access = await record_access_service.resolve(db, user, "tickets")
        item = await support_repository.ticket(db, self.org(user), ticket_id, access)
        if not item:
            raise NotFoundError(message="Ticket not found")
        return item

    async def create_ticket(self, db: AsyncSession, user: User, payload: TicketCreate):
        org = self.org(user)
        if payload.assigned_to or payload.team_id:
            permissions = set(await auth_service.get_user_permissions(db, user))
            if "tickets:assign" not in permissions or not api_key_scope_allows(
                user, "tickets:assign"
            ):
                from app.core.errors import ForbiddenError

                raise ForbiddenError(message="Missing required permission: tickets:assign")
        links = payload.model_dump()
        invalid = await support_repository.validate_links(db, org, **links)
        if invalid:
            raise NotFoundError(
                message=f"Related {invalid.removesuffix('_id').replace('_', ' ')} not found"
            )
        from app.services.crm_relationship_service import resolve_crm_record_access

        await validate_crm_relationships(
            db,
            organization_id=org,
            contact_id=payload.contact_id,
            company_id=payload.company_id,
            access_by_module=await resolve_crm_record_access(db, user),
        )
        now = datetime.now(UTC)
        response_hours, resolution_hours = 1, 24
        if payload.sla_policy_id:
            from app.models import SLAPolicy

            policy = await db.get(SLAPolicy, payload.sla_policy_id)
            response_hours, resolution_hours = (
                policy.response_time_hours,
                policy.resolution_time_hours,
            )
        ticket = Ticket(
            organization_id=org,
            ticket_number=await support_repository.next_ticket_number(db, org),
            source="CRM",
            created_by=user.id,
            first_response_due_at=now + timedelta(hours=response_hours),
            resolution_due_at=now + timedelta(hours=resolution_hours),
            **payload.model_dump(),
        )
        db.add(ticket)
        await db.flush()
        db.add(
            TicketStatusHistory(
                ticket_id=ticket.id, from_status=None, to_status="New", changed_by=user.id
            )
        )
        from app.services.workflow_service import workflow_service

        await workflow_service.emit(
            db,
            organization_id=org,
            module="tickets",
            trigger="record.created",
            entity_id=ticket.id,
            actor_id=user.id,
            payload={"status": ticket.status, "priority": ticket.priority},
        )
        await db.commit()
        await db.refresh(ticket)
        return ticket

    async def update_ticket(
        self,
        db,
        user,
        ticket_id,
        payload: TicketUpdate,
        assignment: dict | None = None,
        emit_workflow: bool = True,
    ):
        ticket = await self.ticket(db, user, ticket_id)
        data = payload.model_dump(exclude_unset=True) | (assignment or {})
        invalid = await support_repository.validate_links(db, self.org(user), **data)
        if invalid:
            raise NotFoundError(message=f"Related {invalid.removesuffix('_id')} not found")
        from app.services.crm_relationship_service import resolve_crm_record_access

        await validate_crm_relationships(
            db,
            organization_id=self.org(user),
            contact_id=data.get("contact_id", ticket.contact_id),
            company_id=data.get("company_id", ticket.company_id),
            access_by_module=await resolve_crm_record_access(db, user),
        )
        old_status = ticket.status
        requested_status = data.get("status")
        if (
            requested_status
            and requested_status != old_status
            and requested_status not in self.STATUS_TRANSITIONS.get(old_status, set())
        ):
            raise ConflictError(
                message=f"Ticket cannot transition from {old_status} to {requested_status}"
            )
        for key, value in data.items():
            setattr(ticket, key, value)
        if ticket.status != old_status:
            now = datetime.now(UTC)
            db.add(
                TicketStatusHistory(
                    ticket_id=ticket.id,
                    from_status=old_status,
                    to_status=ticket.status,
                    changed_by=user.id,
                )
            )
            if ticket.status == "Resolved":
                ticket.resolved_at = now
                ticket.closed_at = None
            if ticket.status == "Closed":
                ticket.closed_at = now
            if ticket.status in {"New", "Open", "Pending"}:
                ticket.resolved_at = None
                ticket.closed_at = None
        if emit_workflow:
            from app.services.workflow_service import workflow_service

            changed_fields = list(data)
            await workflow_service.emit(
                db,
                organization_id=ticket.organization_id,
                module="tickets",
                trigger=(
                    "record.status_changed" if ticket.status != old_status else "record.updated"
                ),
                entity_id=ticket.id,
                actor_id=user.id,
                payload={
                    "status": ticket.status,
                    "priority": ticket.priority,
                    "old_status": old_status,
                    "changed_fields": changed_fields,
                },
            )
        await db.commit()
        await db.refresh(ticket)
        return ticket

    async def archive_ticket(self, db, user, ticket_id):
        ticket = await self.ticket(db, user, ticket_id)
        ticket.is_archived = True
        await db.commit()

    async def comments(self, db, user, ticket_id, page: int = 1, limit: int = 50):
        await self.ticket(db, user, ticket_id)
        rows = await support_repository.list_comments(
            db, ticket_id, offset=(page - 1) * limit, limit=limit
        )
        return rows, await support_repository.count_comments(db, ticket_id)

    async def add_comment(self, db, user, ticket_id, payload: TicketCommentCreate):
        ticket = await self.ticket(db, user, ticket_id)
        comment = TicketComment(ticket_id=ticket.id, user_id=user.id, **payload.model_dump())
        db.add(comment)
        if not payload.is_internal and not ticket.first_responded_at:
            ticket.first_responded_at = datetime.now(UTC)
        await db.commit()
        await db.refresh(comment)
        return comment

    async def history(self, db, user, ticket_id):
        await self.ticket(db, user, ticket_id)
        return await support_repository.status_history(db, ticket_id)

    async def escalate(self, db, user, ticket_id, *, reason, assigned_to=None, team_id=None):
        ticket = await self.ticket(db, user, ticket_id)
        links = {"assigned_to": assigned_to, "team_id": team_id}
        invalid = await support_repository.validate_links(db, self.org(user), **links)
        if invalid:
            raise NotFoundError(message=f"Related {invalid.removesuffix('_id')} not found")
        ticket.priority = "Urgent"
        ticket.escalated_at = datetime.now(UTC)
        ticket.escalated_by = user.id
        ticket.escalation_reason = reason.strip()
        if assigned_to is not None:
            ticket.assigned_to = assigned_to
        if team_id is not None:
            ticket.team_id = team_id
        await db.commit()
        await db.refresh(ticket)
        return ticket

    async def ticket_articles(self, db, user, ticket_id):
        await self.ticket(db, user, ticket_id)
        access = await record_access_service.resolve(db, user, "knowledge_base")
        return await support_repository.list_ticket_articles(db, ticket_id, access=access)

    async def link_ticket_article(self, db, user, ticket_id, article_id):
        await self.ticket(db, user, ticket_id)
        article = await self.article(db, user, article_id)
        link = TicketKnowledgeArticle(ticket_id=ticket_id, article_id=article.id)
        db.add(link)
        try:
            await db.commit()
        except IntegrityError as exc:
            await db.rollback()
            raise ConflictError(message="Article is already linked to this ticket") from exc
        return article

    async def unlink_ticket_article(self, db, user, ticket_id, article_id):
        await self.ticket(db, user, ticket_id)
        await self.article(db, user, article_id)
        link = await support_repository.get_ticket_article_link(db, ticket_id, article_id)
        if not link:
            raise NotFoundError(message="Linked knowledge article not found")
        await db.delete(link)
        await db.commit()

    async def list_articles(self, db, user, search, article_status, page, limit):
        access = await record_access_service.resolve(db, user, "knowledge_base")
        return await support_repository.list_articles(
            db,
            self.org(user),
            search=search,
            status=article_status,
            offset=(page - 1) * limit,
            limit=limit,
            access=access,
        )

    async def list_customers(self, db, user, search, page, limit):
        company_access = await record_access_service.resolve(db, user, "companies")
        contact_access = await record_access_service.resolve(db, user, "contacts")
        return await support_repository.customers(
            db,
            self.org(user),
            search,
            (page - 1) * limit,
            limit,
            company_access=company_access,
            contact_access=contact_access,
        )

    async def article(self, db, user, article_id):
        access = await record_access_service.resolve(db, user, "knowledge_base")
        article = await support_repository.article(
            db, self.org(user), article_id, access=access
        )
        if not article:
            raise NotFoundError(message="Knowledge article not found")
        return article

    async def public_article(self, db, organization_slug: str, article_slug: str):
        return await support_repository.public_article(db, organization_slug, article_slug)

    async def create_article(self, db, user, payload: KnowledgeArticleCreate):
        article = KnowledgeArticle(
            organization_id=self.org(user),
            author_id=user.id,
            slug=self.slug(payload.slug or payload.title),
            **payload.model_dump(exclude={"slug"}),
        )
        db.add(article)
        try:
            await db.commit()
            await db.refresh(article)
        except IntegrityError as exc:
            await db.rollback()
            raise ConflictError(message="An article with this slug already exists") from exc
        return article

    async def update_article(self, db, user, article_id, payload: KnowledgeArticleUpdate):
        article = await self.article(db, user, article_id)
        data = payload.model_dump(exclude_unset=True)
        if "slug" in data:
            data["slug"] = self.slug(data["slug"])
        for key, value in data.items():
            setattr(article, key, value)
        try:
            await db.commit()
            await db.refresh(article)
        except IntegrityError as exc:
            await db.rollback()
            raise ConflictError(message="An article with this slug already exists") from exc
        return article

    async def publish(self, db, user, article_id):
        article = await self.article(db, user, article_id)
        article.status = "Published"
        article.published_at = datetime.now(UTC)
        await db.commit()
        await db.refresh(article)
        return article

    async def delete_article(self, db, user, article_id):
        article = await self.article(db, user, article_id)
        await db.delete(article)
        await db.commit()


support_service = SupportService()
