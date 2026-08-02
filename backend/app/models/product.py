from sqlalchemy import String, Boolean, DateTime, Float, Integer, Text, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional
import uuid
from app.database import Base

class ProductCategory(Base):
    __tablename__ = "product_categories"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[str] = mapped_column(String, ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)

class Product(Base):
    __tablename__ = "products"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[str] = mapped_column(String, ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    category_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey("product_categories.id", ondelete="SET NULL"), index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    sku: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    in_stock_quantity: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())
