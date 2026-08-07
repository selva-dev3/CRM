from typing import Optional
import uuid

from sqlalchemy import (
    String,
    Boolean,
    DateTime,
    Text,
    Integer,
    ForeignKey,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


# ==========================================================
# Integrations
# ==========================================================

class Integration(Base):
    __tablename__ = "integrations"

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )

    organization_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        index=True,
        nullable=False
    )

    # Display Name
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )

    # zapier / slack / stripe / google / hubspot ...
    provider: Mapped[str] = mapped_column(
        String(50),
        index=True,
        nullable=False
    )

    is_connected: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False
    )

    # OAuth / API Credentials
    access_token: Mapped[Optional[str]] = mapped_column(Text)

    refresh_token: Mapped[Optional[str]] = mapped_column(Text)

    webhook_url: Mapped[Optional[str]] = mapped_column(Text)

    # Store provider configuration as JSON string
    credentials: Mapped[Optional[str]] = mapped_column(Text)

    status: Mapped[str] = mapped_column(
        String(30),
        default="disconnected"
    )

    last_synced: Mapped[Optional[DateTime]] = mapped_column(
        DateTime(timezone=True)
    )

    last_error: Mapped[Optional[str]] = mapped_column(Text)

    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now()
    )

    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now()
    )


# ==========================================================
# API Keys
# ==========================================================

class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )

    organization_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        index=True,
        nullable=False
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )

    key_hash: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False
    )

    scopes: Mapped[Optional[str]] = mapped_column(Text)

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False
    )

    expires_at: Mapped[Optional[DateTime]] = mapped_column(
        DateTime(timezone=True)
    )

    last_used: Mapped[Optional[DateTime]] = mapped_column(
        DateTime(timezone=True)
    )

    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now()
    )

    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now()
    )


# ==========================================================
# Webhooks
# ==========================================================

class Webhook(Base):
    __tablename__ = "webhooks"

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )

    organization_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        index=True,
        nullable=False
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )

    target_url: Mapped[str] = mapped_column(
        String(500),
        nullable=False
    )

    # Comma separated / JSON events
    events: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )

    secret: Mapped[Optional[str]] = mapped_column(
        String(255)
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False
    )

    last_triggered_at: Mapped[Optional[DateTime]] = mapped_column(
        DateTime(timezone=True)
    )

    failure_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False
    )

    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now()
    )

    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now()
    )