from typing import Literal

from pydantic import BaseModel, Field

OrderStatus = Literal["Confirmed", "Fulfilled", "Cancelled"]


class OrderStatusUpdate(BaseModel):
    status: Literal["Fulfilled", "Cancelled"]


class OrderItemResponse(BaseModel):
    id: str
    product_id: str | None = None
    product_name: str
    quantity: int
    unit_price: float
    discount_percent: float
    tax_percent: float
    subtotal: float
    discount_total: float
    tax_total: float
    total: float


class OrderResponse(BaseModel):
    id: str
    quote_id: str
    deal_id: str | None = None
    company_id: str | None = None
    contact_id: str | None = None
    order_number: str
    status: OrderStatus
    currency: str
    subtotal: float
    discount_total: float
    tax_total: float
    total: float
    confirmed_at: str
    fulfilled_at: str | None = None
    cancelled_at: str | None = None
    created_at: str | None = None
    items: list[OrderItemResponse] = Field(default_factory=list)
