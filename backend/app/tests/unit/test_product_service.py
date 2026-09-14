from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError
from app.repositories.product_repository import ProductRepository
from app.schemas.crm_schemas import ProductBase
from app.services import product_service as product_module
from app.services.product_service import ProductService, product_to_dict


def _product(**overrides):
    values = {
        "id": "product-1",
        "name": "Support",
        "sku": "SUP-1",
        "price": Decimal("25.00"),
        "in_stock_quantity": 0,
        "is_active": True,
        "category_id": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_product_response_preserves_zero_stock():
    assert product_to_dict(_product())["in_stock_quantity"] == 0


def test_product_schema_rejects_negative_stock():
    with pytest.raises(ValueError):
        ProductBase(name="Support", sku="SUP-1", in_stock_quantity=-1)


@pytest.mark.asyncio
async def test_update_without_real_sku_preserves_existing_sku(monkeypatch):
    repository = AsyncMock(spec=ProductRepository)
    product = _product()
    repository.get.return_value = product
    db = AsyncMock(spec=AsyncSession)
    monkeypatch.setattr(
        product_module.organization_service,
        "resolve_valid_org_id",
        AsyncMock(return_value="org-1"),
    )

    await ProductService(repository).update_product(
        db,
        product_id=product.id,
        payload=ProductBase(name="Updated", sku="N/A", price=30, in_stock_quantity=0),
        user=SimpleNamespace(id="user-1"),
    )

    assert product.sku == "SUP-1"
    assert product.price == Decimal("30")
    assert product.in_stock_quantity == 0


@pytest.mark.asyncio
async def test_inventory_adjustment_is_locked_and_cannot_go_negative(monkeypatch):
    repository = AsyncMock(spec=ProductRepository)
    repository.get.return_value = _product(in_stock_quantity=2)
    db = AsyncMock(spec=AsyncSession)
    monkeypatch.setattr(
        product_module.organization_service,
        "resolve_valid_org_id",
        AsyncMock(return_value="org-1"),
    )

    with pytest.raises(ConflictError):
        await ProductService(repository).adjust_inventory(
            db,
            product_id="product-1",
            quantity_delta=-3,
            user=SimpleNamespace(id="user-1"),
        )

    repository.get.assert_awaited_once_with(
        db, product_id="product-1", organization_id="org-1", lock=True
    )
    db.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_direct_delete_of_unknown_or_foreign_product_is_not_success(monkeypatch):
    repository = AsyncMock(spec=ProductRepository)
    repository.get.return_value = None
    db = AsyncMock(spec=AsyncSession)
    monkeypatch.setattr(
        product_module.organization_service,
        "resolve_valid_org_id",
        AsyncMock(return_value="org-1"),
    )

    with pytest.raises(NotFoundError):
        await ProductService(repository).delete_product(
            db, product_id="foreign-product", user=SimpleNamespace(id="user-1")
        )
