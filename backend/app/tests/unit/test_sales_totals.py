from decimal import Decimal

import pytest

from app.core.errors import APIException
from app.services.sales_totals import calculate_line


def test_discount_applies_before_tax_and_rounding_is_decimal():
    result = calculate_line(3, "19.99", "10", "18")
    assert result.subtotal == Decimal("59.97")
    assert result.discount == Decimal("6.00")
    assert result.tax == Decimal("9.71")
    assert result.total == Decimal("63.68")


def test_unit_price_rounding_matches_numeric_storage():
    assert calculate_line(2, "12.345").total == Decimal("24.70")


def test_percentage_rounding_matches_numeric_storage():
    assert calculate_line(2, "100", "10.125", "18.125") == calculate_line(2, "100", "10.13", "18.13")


def test_zero_price_is_valid_and_does_not_fall_back_to_catalog_price():
    assert calculate_line(2, 0).total == Decimal("0.00")


@pytest.mark.parametrize("quantity,price,discount,tax", [
    (0, 1, 0, 0), (-1, 1, 0, 0), (True, 1, 0, 0), (1.5, 1, 0, 0),
    (1, -1, 0, 0), (1, "NaN", 0, 0), (1, "Infinity", 0, 0),
    (1, 1, 101, 0), (1, 1, 0, -1), (1000000, "999999999999.99", 0, 0),
])
def test_invalid_financial_input_is_rejected(quantity, price, discount, tax):
    with pytest.raises(APIException):
        calculate_line(quantity, price, discount, tax)
