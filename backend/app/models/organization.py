import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Organization(Base):
    __tablename__ = "organizations"
    __table_args__ = (Index("uq_organizations_normalized_name", text("lower(btrim(name))"), unique=True),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str | None] = mapped_column(String(255))
    domain: Mapped[str | None] = mapped_column(String(255), index=True)
    email: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(100))
    website: Mapped[str | None] = mapped_column(String(255))
    industry: Mapped[str | None] = mapped_column(String(100))
    company_size: Mapped[str | None] = mapped_column(String(100))
    country: Mapped[str | None] = mapped_column(String(100))
    state: Mapped[str | None] = mapped_column(String(100))
    city: Mapped[str | None] = mapped_column(String(100))
    address: Mapped[str | None] = mapped_column(String(500))
    postal_code: Mapped[str | None] = mapped_column(String(50))
    timezone: Mapped[str | None] = mapped_column(String(100), default="Asia/Kolkata")
    currency: Mapped[str | None] = mapped_column(String(10), default="INR")
    invoice_prefix: Mapped[str] = mapped_column(String(20), default="INV", server_default="INV")
    invoice_sequence: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")
    payment_prefix: Mapped[str] = mapped_column(String(20), default="PAY", server_default="PAY")
    payment_sequence: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")
    quote_prefix: Mapped[str] = mapped_column(String(20), default="QUO", server_default="QUO")
    quote_sequence: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")
    language: Mapped[str | None] = mapped_column(String(10), default="en")
    logo_url: Mapped[str | None] = mapped_column(String(500))
    tax_number: Mapped[str | None] = mapped_column(String(100))
    registration_number: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str | None] = mapped_column(String(50), default="active")
    role: Mapped[str | None] = mapped_column(String(100), default="Admin")

    plan: Mapped[str] = mapped_column(String(100), default="Free", server_default="Free")
    max_users: Mapped[int] = mapped_column(Integer, default=3, server_default="3")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), server_default=func.now()
    )


class OrganizationSetting(Base):
    __tablename__ = "organization_settings"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[str] = mapped_column(
        String, ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    primary_color: Mapped[str] = mapped_column(String(50), default="#3B82F6")
    logo_url: Mapped[str | None] = mapped_column(String(500))
    timezone: Mapped[str] = mapped_column(String(100), default="UTC")
    currency: Mapped[str] = mapped_column(String(10), default="USD")
    language: Mapped[str] = mapped_column(String(10), default="en")


class OrganizationSubscription(Base):
    __tablename__ = "organization_subscriptions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    organization_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )

    plan_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("subscription_plans.id", ondelete="SET NULL"), nullable=True
    )

    status: Mapped[str] = mapped_column(String(50), default="active", nullable=False)

    billing_cycle: Mapped[str] = mapped_column(String(20), default="Monthly", nullable=False)

    amount: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    currency: Mapped[str] = mapped_column(String(10), default="INR", nullable=False)

    # Trial
    trial: Mapped[bool] = mapped_column(Boolean, default=False)

    # Billing Dates
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    current_period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    current_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    next_billing: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    auto_renew: Mapped[bool] = mapped_column(Boolean, default=True)

    # Preserve the provider archive alongside current subscription billing state.
    legacy_provider_data: Mapped[dict | None] = mapped_column(JSON)
    payment_provider: Mapped[str | None] = mapped_column(String(50))

    payment_method: Mapped[str | None] = mapped_column(String(100))

    customer_id: Mapped[str | None] = mapped_column(String(255))

    subscription_id: Mapped[str | None] = mapped_column(String(255), index=True)

    invoice_id: Mapped[str | None] = mapped_column(String(100))

    checkout_session_id: Mapped[str | None] = mapped_column(String(255), index=True)
    checkout_operation_id: Mapped[str | None] = mapped_column(String(64))
    checkout_request_hash: Mapped[str | None] = mapped_column(String(64))
    checkout_plan_slug: Mapped[str | None] = mapped_column(String(100))
    checkout_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    reconciliation_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_provider_check_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_provider_error_code: Mapped[str | None] = mapped_column(String(80))
    last_provider_request_id: Mapped[str | None] = mapped_column(String(120))

    # Usage
    max_users: Mapped[int] = mapped_column(Integer, default=100)

    current_users: Mapped[int] = mapped_column(Integer, default=1)

    storage_limit_gb: Mapped[int] = mapped_column(Integer, default=500)

    storage_used_gb: Mapped[float] = mapped_column(Float, default=0.5)

    ai_credits: Mapped[int] = mapped_column(Integer, default=-1)

    support_plan: Mapped[str] = mapped_column(String(50), default="Standard")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class SubscriptionPlan(Base):
    __tablename__ = "subscription_plans"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    name: Mapped[str] = mapped_column(String(100), nullable=False)

    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)

    description: Mapped[str] = mapped_column(String(500), default="", nullable=False)

    currency: Mapped[str] = mapped_column(String(10), default="INR", nullable=False)

    billing_cycle: Mapped[str] = mapped_column(String(20), default="month", nullable=False)

    price_monthly: Mapped[float] = mapped_column(Float, default=0)

    price_yearly: Mapped[float] = mapped_column(Float, default=0)

    max_users: Mapped[int] = mapped_column(Integer, default=3)

    max_storage_gb: Mapped[int] = mapped_column(Integer, default=5)

    ai_credits: Mapped[int] = mapped_column(Integer, default=0)

    features: Mapped[str | None] = mapped_column(Text)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    is_popular: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class OrganizationInvitation(Base):
    __tablename__ = "organization_invitations"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=True
    )
    email: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role_id: Mapped[str | None] = mapped_column(String(100), default="Admin", nullable=True)
    subscription_id: Mapped[str | None] = mapped_column(String, nullable=True)
    token: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    status: Mapped[str] = mapped_column(
        String(50), default="Pending", nullable=False
    )  # Pending, Accepted, Expired, Cancelled
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ProcessedWebhookEvent(Base):
    __tablename__ = "processed_webhook_events"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    event_id: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
