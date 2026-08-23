from sqlalchemy import String, Boolean, DateTime, Integer, Float, Text, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional
import uuid
from app.db.base import Base

class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[Optional[str]] = mapped_column(String(255))
    domain: Mapped[Optional[str]] = mapped_column(String(255), index=True)
    email: Mapped[Optional[str]] = mapped_column(String(255))
    phone: Mapped[Optional[str]] = mapped_column(String(100))
    website: Mapped[Optional[str]] = mapped_column(String(255))
    industry: Mapped[Optional[str]] = mapped_column(String(100))
    company_size: Mapped[Optional[str]] = mapped_column(String(100))
    country: Mapped[Optional[str]] = mapped_column(String(100))
    state: Mapped[Optional[str]] = mapped_column(String(100))
    city: Mapped[Optional[str]] = mapped_column(String(100))
    address: Mapped[Optional[str]] = mapped_column(String(500))
    postal_code: Mapped[Optional[str]] = mapped_column(String(50))
    timezone: Mapped[Optional[str]] = mapped_column(String(100), default="Asia/Kolkata")
    currency: Mapped[Optional[str]] = mapped_column(String(10), default="INR")
    language: Mapped[Optional[str]] = mapped_column(String(10), default="en")
    logo_url: Mapped[Optional[str]] = mapped_column(String(500))
    tax_number: Mapped[Optional[str]] = mapped_column(String(100))
    registration_number: Mapped[Optional[str]] = mapped_column(String(100))
    status: Mapped[Optional[str]] = mapped_column(String(50), default="active")
    role: Mapped[Optional[str]] = mapped_column(String(100), default="Admin")

    plan: Mapped[str] = mapped_column(String(100), default="Enterprise")
    max_users: Mapped[int] = mapped_column(Integer, default=50)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())

class OrganizationSetting(Base):
    __tablename__ = "organization_settings"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[str] = mapped_column(String, ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    primary_color: Mapped[str] = mapped_column(String(50), default="#3B82F6")
    logo_url: Mapped[Optional[str]] = mapped_column(String(500))
    timezone: Mapped[str] = mapped_column(String(100), default="UTC")
    currency: Mapped[str] = mapped_column(String(10), default="USD")
    language: Mapped[str] = mapped_column(String(10), default="en")

class OrganizationSubscription(Base):
    __tablename__ = "organization_subscriptions"

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )

    organization_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False
    )

    plan_id: Mapped[Optional[str]] = mapped_column(
        String,
        ForeignKey("subscription_plans.id", ondelete="SET NULL"),
        nullable=True
    )



    status: Mapped[str] = mapped_column(
        String(50),
        default="active",
        nullable=False
    )

    billing_cycle: Mapped[str] = mapped_column(
        String(20),
        default="Monthly",
        nullable=False
    )

    amount: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False
    )

    currency: Mapped[str] = mapped_column(
        String(10),
        default="INR",
        nullable=False
    )

    # Trial
    trial: Mapped[bool] = mapped_column(
        Boolean,
        default=False
    )

    # Billing Dates
    started_at: Mapped[Optional[DateTime]] = mapped_column(
        DateTime(timezone=True)
    )

    current_period_start: Mapped[Optional[DateTime]] = mapped_column(
        DateTime(timezone=True)
    )

    current_period_end: Mapped[Optional[DateTime]] = mapped_column(
        DateTime(timezone=True)
    )

    next_billing: Mapped[Optional[DateTime]] = mapped_column(
        DateTime(timezone=True)
    )

    expires_at: Mapped[Optional[DateTime]] = mapped_column(
        DateTime(timezone=True)
    )

    auto_renew: Mapped[bool] = mapped_column(
        Boolean,
        default=True
    )

    # Payment
    payment_provider: Mapped[Optional[str]] = mapped_column(
        String(50),
        default="Stripe"
    )

    payment_method: Mapped[Optional[str]] = mapped_column(
        String(100)
    )

    customer_id: Mapped[Optional[str]] = mapped_column(
        String(255)
    )

    subscription_id: Mapped[Optional[str]] = mapped_column(
        String(255)
    )

    invoice_id: Mapped[Optional[str]] = mapped_column(
        String(100)
    )

    # Usage
    max_users: Mapped[int] = mapped_column(
        Integer,
        default=100
    )

    current_users: Mapped[int] = mapped_column(
        Integer,
        default=1
    )

    storage_limit_gb: Mapped[int] = mapped_column(
        Integer,
        default=500
    )

    storage_used_gb: Mapped[float] = mapped_column(
        Float,
        default=0.5
    )

    ai_credits: Mapped[int] = mapped_column(
        Integer,
        default=-1
    )

    support_plan: Mapped[str] = mapped_column(
        String(50),
        default="Standard"
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


class SubscriptionPlan(Base):
    __tablename__ = "subscription_plans"

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )

    name: Mapped[str] = mapped_column(String(100), nullable=False)

    slug: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False
    )

    price_monthly: Mapped[float] = mapped_column(Float, default=0)

    price_yearly: Mapped[float] = mapped_column(Float, default=0)

    max_users: Mapped[int] = mapped_column(Integer, default=3)

    max_storage_gb: Mapped[int] = mapped_column(Integer, default=5)

    ai_credits: Mapped[int] = mapped_column(Integer, default=0)

    features: Mapped[Optional[str]] = mapped_column(Text)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class OrganizationInvitation(Base):
    __tablename__ = "organization_invitations"

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    organization_id: Mapped[Optional[str]] = mapped_column(
        String,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        index=True,
        nullable=True
    )
    email: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    full_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    role_id: Mapped[Optional[str]] = mapped_column(String(100), default="Admin", nullable=True)
    subscription_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    token: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="Pending", nullable=False)  # Pending, Accepted, Expired, Cancelled
    expires_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False)
    accepted_at: Mapped[Optional[DateTime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ProcessedWebhookEvent(Base):
    __tablename__ = "processed_webhook_events"

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    event_id: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False
    )
    event_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now()
    )