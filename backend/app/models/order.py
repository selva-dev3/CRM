import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SalesOrder(Base):
    __tablename__ = "sales_orders"
    __table_args__ = (
        CheckConstraint(
            "status IN ('Confirmed','Fulfilled','Cancelled')",
            name="ck_sales_orders_status",
        ),
        UniqueConstraint("organization_id", "quote_id", name="uq_sales_orders_org_quote"),
        UniqueConstraint("organization_id", "order_number", name="uq_sales_orders_org_number"),
        Index("ix_sales_orders_org_status_created", "organization_id", "status", "created_at"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[str] = mapped_column(
        String, ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    quote_id: Mapped[str] = mapped_column(
        String, ForeignKey("quotes.id", ondelete="RESTRICT"), index=True
    )
    deal_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("deals.id", ondelete="SET NULL"), index=True
    )
    company_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("companies.id", ondelete="SET NULL"), index=True
    )
    contact_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("contacts.id", ondelete="SET NULL"), index=True
    )
    order_number: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), default="Confirmed", server_default="Confirmed")
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    discount_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    tax_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    confirmed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    fulfilled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), server_default=func.now()
    )


class SalesOrderItem(Base):
    __tablename__ = "sales_order_items"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    order_id: Mapped[str] = mapped_column(
        String, ForeignKey("sales_orders.id", ondelete="CASCADE"), index=True
    )
    product_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("products.id", ondelete="SET NULL"), index=True
    )
    product_name: Mapped[str] = mapped_column(String(255), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    discount_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    tax_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    discount_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    tax_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
