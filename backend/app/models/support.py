import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Ticket(Base):
    __tablename__ = "tickets"
    __table_args__ = (
        CheckConstraint(
            "status IN ('New','Open','Pending','Resolved','Closed')", name="ck_tickets_status"
        ),
        CheckConstraint("priority IN ('Low','Medium','High','Urgent')", name="ck_tickets_priority"),
        UniqueConstraint("organization_id", "ticket_number", name="uq_tickets_org_number"),
        Index("ix_tickets_org_status_created", "organization_id", "status", "created_at"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[str] = mapped_column(
        String, ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    ticket_number: Mapped[str] = mapped_column(String(50), nullable=False)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="New", server_default="New", index=True)
    priority: Mapped[str] = mapped_column(
        String(20), default="Medium", server_default="Medium", index=True
    )
    source: Mapped[str] = mapped_column(String(20), default="CRM", server_default="CRM")
    contact_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("contacts.id", ondelete="SET NULL"), index=True
    )
    company_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("companies.id", ondelete="SET NULL"), index=True
    )
    assigned_to: Mapped[str | None] = mapped_column(
        String, ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    team_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("teams.id", ondelete="SET NULL"), index=True
    )
    sla_policy_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("sla_policies.id", ondelete="SET NULL"), index=True
    )
    created_by: Mapped[str | None] = mapped_column(
        String, ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    first_response_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolution_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    first_responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    escalated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    escalated_by: Mapped[str | None] = mapped_column(
        String, ForeignKey("users.id", ondelete="SET NULL")
    )
    escalation_reason: Mapped[str | None] = mapped_column(String(500))
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), server_default=func.now()
    )


class TicketComment(Base):
    __tablename__ = "ticket_comments"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    ticket_id: Mapped[str] = mapped_column(
        String, ForeignKey("tickets.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[str | None] = mapped_column(String, ForeignKey("users.id", ondelete="SET NULL"))
    body: Mapped[str] = mapped_column(Text, nullable=False)
    is_internal: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TicketStatusHistory(Base):
    __tablename__ = "ticket_status_history"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    ticket_id: Mapped[str] = mapped_column(
        String, ForeignKey("tickets.id", ondelete="CASCADE"), index=True
    )
    from_status: Mapped[str | None] = mapped_column(String(20))
    to_status: Mapped[str] = mapped_column(String(20), nullable=False)
    changed_by: Mapped[str | None] = mapped_column(
        String, ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class KnowledgeArticle(Base):
    __tablename__ = "knowledge_articles"
    __table_args__ = (
        UniqueConstraint("organization_id", "slug", name="uq_knowledge_articles_org_slug"),
    )
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[str] = mapped_column(
        String, ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str | None] = mapped_column(String(500))
    body: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20), default="Draft", server_default="Draft")
    author_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("users.id", ondelete="SET NULL")
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), server_default=func.now()
    )


class TicketKnowledgeArticle(Base):
    __tablename__ = "ticket_knowledge_articles"
    __table_args__ = (UniqueConstraint("ticket_id", "article_id", name="uq_ticket_knowledge_pair"),)
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    ticket_id: Mapped[str] = mapped_column(String, ForeignKey("tickets.id", ondelete="CASCADE"))
    article_id: Mapped[str] = mapped_column(
        String, ForeignKey("knowledge_articles.id", ondelete="CASCADE")
    )
