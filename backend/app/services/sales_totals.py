"""Shared, deterministic financial calculations for persisted sales documents."""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from app.core.errors import APIException

CENT = Decimal("0.01")
MAX_MONEY = Decimal("999999999999.99")


def decimal_value(value: object, *, maximum: Decimal = MAX_MONEY) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise APIException(message="Invalid financial value", code="INVALID_AMOUNT") from exc
    if not result.is_finite() or result < 0 or result > maximum:
        raise APIException(message="Financial value is outside the permitted range", code="INVALID_AMOUNT")
    return result


def rounded_value(value: object, *, maximum: Decimal = MAX_MONEY) -> Decimal:
    """Normalize before persistence so calculations use exactly the stored precision."""
    return decimal_value(value, maximum=maximum).quantize(CENT, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class LineTotals:
    subtotal: Decimal
    discount: Decimal
    tax: Decimal
    total: Decimal


def calculate_line(quantity: int, unit_price: object, discount_percent: object = 0,
                   tax_percent: object = 0) -> LineTotals:
    if isinstance(quantity, bool) or not isinstance(quantity, int) or not 1 <= quantity <= 1000000:
        raise APIException(message="Quantity must be a positive integer", code="INVALID_QUANTITY")
    price = rounded_value(unit_price)
    discount_rate = rounded_value(discount_percent, maximum=Decimal(100))
    tax_rate = rounded_value(tax_percent, maximum=Decimal(100))
    subtotal = (price * quantity).quantize(CENT, rounding=ROUND_HALF_UP)
    discount = (subtotal * discount_rate / 100).quantize(CENT, rounding=ROUND_HALF_UP)
    tax = ((subtotal - discount) * tax_rate / 100).quantize(CENT, rounding=ROUND_HALF_UP)
    total = subtotal - discount + tax
    decimal_value(subtotal)
    decimal_value(total)
    return LineTotals(subtotal, discount, tax, total)
