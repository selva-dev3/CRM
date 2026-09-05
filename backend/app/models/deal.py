import uuid
from decimal import Decimal

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Deal(Base):
    __tablename__ = "deals"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[str] = mapped_column(
        String, ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    stage: Mapped[str] = mapped_column(String(100), default="Prospecting", index=True)
    probability: Mapped[float] = mapped_column(Float, default=50.0)
    loss_reason: Mapped[str | None] = mapped_column(String(255))
    expected_close_date: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), index=True)
    assigned_to: Mapped[str] = mapped_column(
        String, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    contact_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("contacts.id", ondelete="SET NULL")
    )
    company_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("companies.id", ondelete="SET NULL")
    )
    project_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("projects.id", ondelete="SET NULL"), index=True
    )
    custom_fields: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), server_default=func.now()
    )


class DealStage(Base):
    __tablename__ = "deal_stages"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[str] = mapped_column(
        String, ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    default_probability: Mapped[float] = mapped_column(Float, default=50.0)
    order_index: Mapped[int] = mapped_column(Integer, default=0)


class DealActivity(Base):
    __tablename__ = "deal_activities"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    deal_id: Mapped[str] = mapped_column(
        String, ForeignKey("deals.id", ondelete="CASCADE"), index=True
    )
    action: Mapped[str] = mapped_column(String(255), nullable=False)
    performed_by: Mapped[str | None] = mapped_column(
        String, ForeignKey("users.id", ondelete="SET NULL")
    )
    timestamp: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DealStageHistory(Base):
    __tablename__ = "deal_stage_history"
    __table_args__ = (
        Index(
            "uq_deal_stage_history_current",
            "deal_id",
            unique=True,
            postgresql_where=text("exited_at IS NULL"),
            sqlite_where=text("exited_at IS NULL"),
        ),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[str] = mapped_column(
        String, ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    deal_id: Mapped[str] = mapped_column(
        String, ForeignKey("deals.id", ondelete="CASCADE"), index=True
    )
    stage: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    entered_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    exited_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), index=True)
    actor_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("users.id", ondelete="SET NULL"), index=True
    )


class DealProduct(Base):
    __tablename__ = "deal_products"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    deal_id: Mapped[str] = mapped_column(
        String, ForeignKey("deals.id", ondelete="CASCADE"), index=True
    )
    product_id: Mapped[str] = mapped_column(
        String, ForeignKey("products.id", ondelete="RESTRICT"), index=True
    )
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    product_name: Mapped[str | None] = mapped_column(String(255))
    discount_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=0, server_default="0")
    tax_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=0, server_default="0")
