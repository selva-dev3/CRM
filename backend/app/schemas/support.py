from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

TicketStatus = Literal["New", "Open", "Pending", "Resolved", "Closed"]
TicketPriority = Literal["Low", "Medium", "High", "Urgent"]


class TicketCreate(BaseModel):
    subject: str = Field(min_length=1, max_length=255)
    description: str = Field(min_length=1, max_length=20000)
    priority: TicketPriority = "Medium"
    contact_id: str | None = None
    company_id: str | None = None
    assigned_to: str | None = None
    team_id: str | None = None
    sla_policy_id: str | None = None

    @model_validator(mode="after")
    def requires_customer(self):
        if not self.contact_id and not self.company_id:
            raise ValueError("A contact or company is required")
        return self


class TicketUpdate(BaseModel):
    subject: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, min_length=1, max_length=20000)
    status: TicketStatus | None = None
    priority: TicketPriority | None = None
    contact_id: str | None = None
    company_id: str | None = None
    sla_policy_id: str | None = None

    @model_validator(mode="after")
    def reject_null_required_fields(self):
        for field in {"subject", "description", "status", "priority"}:
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class TicketAssignmentUpdate(BaseModel):
    assigned_to: str | None = None
    team_id: str | None = None


class TicketResponse(BaseModel):
    id: str
    ticket_number: str
    subject: str
    description: str
    status: TicketStatus
    priority: TicketPriority
    source: str
    contact_id: str | None
    company_id: str | None
    assigned_to: str | None
    team_id: str | None
    sla_policy_id: str | None
    first_response_due_at: datetime | None
    resolution_due_at: datetime | None
    resolved_at: datetime | None
    created_at: datetime
    updated_at: datetime


class TicketCommentCreate(BaseModel):
    body: str = Field(min_length=1, max_length=10000)
    is_internal: bool = True


class TicketCommentResponse(BaseModel):
    id: str
    user_id: str
    body: str
    is_internal: bool
    created_at: datetime


class TicketArticleLinkCreate(BaseModel):
    article_id: str = Field(min_length=1)


class KnowledgeArticleCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    slug: str | None = Field(default=None, max_length=255)
    summary: str | None = Field(default=None, max_length=500)
    body: str = Field(min_length=1, max_length=100000)
    category: str | None = Field(default=None, max_length=100)


class KnowledgeArticleUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    slug: str | None = Field(default=None, min_length=1, max_length=255)
    summary: str | None = Field(default=None, max_length=500)
    body: str | None = Field(default=None, min_length=1, max_length=100000)
    category: str | None = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def reject_null_required_fields(self):
        for field in {"title", "slug", "body"}:
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class KnowledgeArticleResponse(BaseModel):
    id: str
    title: str
    slug: str
    summary: str | None
    body: str
    category: str | None
    status: str
    author_id: str | None
    published_at: datetime | None
    created_at: datetime
    updated_at: datetime


class PublicKnowledgeArticleResponse(BaseModel):
    title: str
    slug: str
    summary: str | None
    body: str
    category: str | None
    published_at: datetime | None


class CustomerResponse(BaseModel):
    entity_type: Literal["contact", "company"]
    entity_id: str
    name: str
    email: str | None = None
    company_id: str | None = None
    open_tickets: int = 0
