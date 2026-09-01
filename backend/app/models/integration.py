import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

# ==========================================================
# Integrations
# ==========================================================


class Integration(Base):
    __tablename__ = "integrations"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    organization_id: Mapped[str] = mapped_column(
        String, ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=False
    )

    name: Mapped[str] = mapped_column(String(100), nullable=False)

    # zapier / slack / stripe / google / hubspot
    provider: Mapped[str] = mapped_column(String(50), index=True, nullable=False)

    is_connected: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    status: Mapped[str] = mapped_column(String(30), default="disconnected", nullable=False)

    # OAuth Credentials
    access_token: Mapped[str | None] = mapped_column(Text)

    refresh_token: Mapped[str | None] = mapped_column(Text)

    # Webhook URL (Zapier / Slack etc.)
    webhook_url: Mapped[str | None] = mapped_column(Text)

    # Provider configuration JSON
    credentials: Mapped[str | None] = mapped_column(Text)

    # Provider object id
    external_id: Mapped[str | None] = mapped_column(String(255))

    # JSON string
    enabled_events: Mapped[str | None] = mapped_column(Text)

    sync_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    last_synced: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    last_error: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


# ==========================================================
# API Keys
# ==========================================================


class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    organization_id: Mapped[str] = mapped_column(
        String, ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=False
    )

    name: Mapped[str] = mapped_column(String(100), nullable=False)

    description: Mapped[str | None] = mapped_column(Text)

    created_by: Mapped[str | None] = mapped_column(
        String, ForeignKey("users.id", ondelete="SET NULL")
    )

    key_hash: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)

    scopes: Mapped[str | None] = mapped_column(Text)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    last_used: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    usage_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


# ==========================================================
# Webhooks
# ==========================================================


class Webhook(Base):
    __tablename__ = "webhooks"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    organization_id: Mapped[str] = mapped_column(
        String, ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=False
    )

    name: Mapped[str] = mapped_column(String(100), nullable=False)

    target_url: Mapped[str] = mapped_column(String(500), nullable=False)

    method: Mapped[str] = mapped_column(String(10), default="POST", nullable=False)

    content_type: Mapped[str] = mapped_column(
        String(100), default="application/json", nullable=False
    )

    headers: Mapped[str | None] = mapped_column(Text)

    # JSON array or comma separated
    events: Mapped[str] = mapped_column(Text, nullable=False)

    secret: Mapped[str | None] = mapped_column(String(255))

    timeout_seconds: Mapped[int] = mapped_column(Integer, default=30, nullable=False)

    retry_count: Mapped[int] = mapped_column(Integer, default=3, nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    last_status_code: Mapped[int | None] = mapped_column(Integer)

    last_response: Mapped[str | None] = mapped_column(Text)

    last_triggered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    failure_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
