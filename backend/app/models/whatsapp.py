"""WhatsApp channel persistence; no credentials or message bodies in audit events."""

import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class WhatsAppIntegration(Base):
    __tablename__ = "whatsapp_integrations"
    __table_args__ = (UniqueConstraint("organization_id", "id"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[str] = mapped_column(
        String, ForeignKey("organizations.id", ondelete="CASCADE"), unique=True
    )
    # Reuse the integration catalog and its encrypted access-token storage.
    catalog_integration_id: Mapped[str] = mapped_column(
        String, ForeignKey("integrations.id", ondelete="RESTRICT"), unique=True
    )
    business_account_id: Mapped[str] = mapped_column(String(100))
    phone_number_id: Mapped[str] = mapped_column(String(100), unique=True)
    display_phone_number: Mapped[str | None] = mapped_column(String(50))
    verified_name: Mapped[str | None] = mapped_column(String(255))
    api_version: Mapped[str] = mapped_column(String(20))
    default_phone_region: Mapped[str | None] = mapped_column(String(2))
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    phone_index_ready: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    phone_backfill_stage: Mapped[str] = mapped_column(
        String(10), default="contacts", server_default="contacts"
    )
    phone_backfill_cursor: Mapped[str | None] = mapped_column(String)
    ai_user_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("users.id", ondelete="SET NULL")
    )
    default_assignee_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("users.id", ondelete="SET NULL")
    )
    last_webhook_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_successful_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class WhatsAppPhoneRepair(Base):
    __tablename__ = "whatsapp_phone_repairs"
    __table_args__ = (
        UniqueConstraint("organization_id", "entity_type", "entity_id"),
        CheckConstraint("entity_type IN ('contact','lead')", name="ck_wa_phone_repair_type"),
        Index("ix_wa_phone_repair_work", "created_at", "id"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[str] = mapped_column(
        String, ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    entity_type: Mapped[str] = mapped_column(String(10))
    entity_id: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class WhatsAppContactIdentity(Base):
    __tablename__ = "whatsapp_contact_identities"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "integration_id"],
            ["whatsapp_integrations.organization_id", "whatsapp_integrations.id"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organization_id", "contact_id"],
            ["contacts.organization_id", "contacts.id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "lead_id"],
            ["leads.organization_id", "leads.id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint("integration_id", "normalized_phone_number"),
        UniqueConstraint("organization_id", "integration_id", "id"),
        CheckConstraint(
            "state IN ('UNKNOWN','AMBIGUOUS','MATCHED_CONTACT','MATCHED_LEAD')",
            name="ck_wa_identity_state",
        ),
        CheckConstraint(
            "consent IN ('UNKNOWN','OPTED_IN','OPTED_OUT')", name="ck_wa_identity_consent"
        ),
    )
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[str] = mapped_column(
        String, ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    integration_id: Mapped[str] = mapped_column(String)
    normalized_phone_number: Mapped[str] = mapped_column(String(16))
    contact_id: Mapped[str | None] = mapped_column(String, index=True)
    lead_id: Mapped[str | None] = mapped_column(String, index=True)
    state: Mapped[str] = mapped_column(String(30), default="UNKNOWN")
    consent: Mapped[str] = mapped_column(String(20), default="UNKNOWN")
    consent_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    provider_verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class WhatsAppTemplate(Base):
    __tablename__ = "whatsapp_templates"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "integration_id"],
            ["whatsapp_integrations.organization_id", "whatsapp_integrations.id"],
            ondelete="CASCADE",
        ),
        UniqueConstraint("integration_id", "provider_template_id"),
        UniqueConstraint("integration_id", "name", "language"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[str] = mapped_column(
        String, ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    integration_id: Mapped[str] = mapped_column(String)
    provider_template_id: Mapped[str] = mapped_column(String(100))
    name: Mapped[str] = mapped_column(String(512))
    language: Mapped[str] = mapped_column(String(20))
    category: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(30), index=True)
    body_parameter_count: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class WhatsAppConversation(Base):
    __tablename__ = "whatsapp_conversations"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "integration_id", "identity_id"],
            [
                "whatsapp_contact_identities.organization_id",
                "whatsapp_contact_identities.integration_id",
                "whatsapp_contact_identities.id",
            ],
            ondelete="CASCADE",
        ),
        UniqueConstraint("identity_id"),
        UniqueConstraint("organization_id", "integration_id", "id"),
        CheckConstraint(
            "status IN ('OPEN','HUMAN_HANDOFF','CLOSED')", name="ck_wa_conversation_status"
        ),
        Index("ix_wa_conversation_inbox", "organization_id", "last_message_at"),
    )
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[str] = mapped_column(
        String, ForeignKey("organizations.id", ondelete="CASCADE")
    )
    integration_id: Mapped[str] = mapped_column(String)
    identity_id: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String(30), default="OPEN")
    ai_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    assigned_user_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    last_customer_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class WhatsAppMessage(Base):
    __tablename__ = "whatsapp_messages"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "integration_id", "conversation_id"],
            [
                "whatsapp_conversations.organization_id",
                "whatsapp_conversations.integration_id",
                "whatsapp_conversations.id",
            ],
            ondelete="CASCADE",
        ),
        UniqueConstraint("integration_id", "provider_message_id"),
        UniqueConstraint("integration_id", "idempotency_key"),
        UniqueConstraint("reply_to_message_id"),
        CheckConstraint("direction IN ('INBOUND','OUTBOUND')", name="ck_wa_message_direction"),
        CheckConstraint(
            "status IN ('RECEIVED','PENDING','PROCESSING','ACCEPTED','SENT','DELIVERED','READ','FAILED','UNKNOWN')",
            name="ck_wa_message_status",
        ),
        Index("ix_wa_message_history", "organization_id", "conversation_id", "created_at", "id"),
        Index("ix_wa_message_work", "work_status", "next_attempt_at", "direction"),
    )
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[str] = mapped_column(
        String, ForeignKey("organizations.id", ondelete="CASCADE")
    )
    integration_id: Mapped[str] = mapped_column(String)
    conversation_id: Mapped[str] = mapped_column(String)
    provider_message_id: Mapped[str | None] = mapped_column(String(255))
    idempotency_key: Mapped[str] = mapped_column(String(100))
    reply_to_message_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("whatsapp_messages.id", ondelete="RESTRICT")
    )
    direction: Mapped[str] = mapped_column(String(10))
    source: Mapped[str] = mapped_column(String(10))
    message_type: Mapped[str] = mapped_column(String(30), default="text")
    body: Mapped[str | None] = mapped_column(Text)
    media_metadata: Mapped[dict | None] = mapped_column(JSON)
    media_s3_key: Mapped[str | None] = mapped_column(String(500))
    template_payload: Mapped[dict | None] = mapped_column(JSON)
    ai_topic: Mapped[str | None] = mapped_column(String(30))
    sender_phone: Mapped[str] = mapped_column(String(50))
    recipient_phone: Mapped[str] = mapped_column(String(50))
    actor_user_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("users.id", ondelete="SET NULL")
    )
    status: Mapped[str] = mapped_column(String(20), default="PENDING")
    work_status: Mapped[str] = mapped_column(String(20), default="PENDING")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    next_attempt_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(80))
    error_message: Mapped[str | None] = mapped_column(String(255))
    provider_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    @property
    def media_available(self) -> bool:
        return bool(self.media_s3_key)


class WhatsAppWebhookEvent(Base):
    __tablename__ = "whatsapp_webhook_events"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "integration_id"],
            ["whatsapp_integrations.organization_id", "whatsapp_integrations.id"],
            ondelete="CASCADE",
        ),
        UniqueConstraint("integration_id", "event_key"),
        Index("ix_wa_event_work", "status", "next_attempt_at"),
    )
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[str] = mapped_column(
        String, ForeignKey("organizations.id", ondelete="CASCADE")
    )
    integration_id: Mapped[str] = mapped_column(String)
    event_key: Mapped[str] = mapped_column(String(64))
    correlation_id: Mapped[str] = mapped_column(String(36))
    payload: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), default="PENDING")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    error_code: Mapped[str | None] = mapped_column(String(80))
    next_attempt_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class WhatsAppReadState(Base):
    __tablename__ = "whatsapp_read_states"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "integration_id", "conversation_id"],
            [
                "whatsapp_conversations.organization_id",
                "whatsapp_conversations.integration_id",
                "whatsapp_conversations.id",
            ],
            ondelete="CASCADE",
        ),
        UniqueConstraint("conversation_id", "user_id"),
    )
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[str] = mapped_column(
        String, ForeignKey("organizations.id", ondelete="CASCADE")
    )
    integration_id: Mapped[str] = mapped_column(String)
    conversation_id: Mapped[str] = mapped_column(String)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id", ondelete="CASCADE"))
    last_read_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
