from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user, require_permission
from app.core.errors import APIException
from app.db.session import get_db
from app.models import User
from app.schemas.crm_schemas import (
    BulkActionResponse,
    BulkDeleteRequest,
    MessageResponse,
    ProductBase,
)
from app.services.product_service import product_service

router = APIRouter()


@router.get(
    "",
    summary="List product catalog with search & pagination",
    dependencies=[Depends(require_permission("products:read"))],
)
async def list_products(
    response: Response,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    category: str | None = Query(None),
    search: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    products, total = await product_service.list_products(
        db, user=current_user, page=page, limit=limit, category=category, search=search
    )
    response.headers["X-Total-Count"] = str(total)
    return products


@router.post(
    "",
    summary="Create new product catalog item",
    dependencies=[Depends(require_permission("products:create"))],
)
async def create_product(
    payload: ProductBase,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await product_service.create_product(db, payload=payload, user=current_user)


@router.get(
    "/categories",
    summary="Get product categories list",
    dependencies=[Depends(require_permission("products:read"))],
)
async def get_product_categories(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await product_service.list_categories(db, user=current_user)


@router.post(
    "/categories",
    response_model=MessageResponse,
    summary="Create new product category",
    dependencies=[Depends(require_permission("products:create"))],
)
async def create_product_category(
    name: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await product_service.create_category(db, name=name, user=current_user)


@router.get(
    "/tax-rates",
    summary="Get tax rate tiers list",
    dependencies=[Depends(require_permission("products:read"))],
)
async def get_tax_rates(db: AsyncSession = Depends(get_db)):
    raise APIException(
        message="Organization tax rates are not configured",
        code="TAX_CONFIGURATION_UNAVAILABLE",
        status_code=501,
    )


@router.get(
    "/export/csv",
    summary="Export product catalog as CSV",
    dependencies=[Depends(require_permission("products:export"))],
)
async def export_products_csv(db: AsyncSession = Depends(get_db)):
    raise APIException(
        message="Product CSV export is not implemented",
        code="PRODUCT_EXPORT_UNAVAILABLE",
        status_code=501,
    )


@router.post(
    "/import/csv",
    response_model=MessageResponse,
    summary="Import product catalog from CSV",
    dependencies=[Depends(require_permission("products:import"))],
)
async def import_products_csv(db: AsyncSession = Depends(get_db)):
    raise APIException(
        message="Product CSV import is not implemented",
        code="PRODUCT_IMPORT_UNAVAILABLE",
        status_code=501,
    )


@router.post(
    "/bulk-delete",
    response_model=BulkActionResponse,
    summary="Bulk delete products",
    dependencies=[Depends(require_permission("products:delete"))],
)
async def bulk_delete_products(
    payload: BulkDeleteRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    count = await product_service.delete_products(db, ids=payload.ids, user=current_user)
    return {"affected_count": count, "message": "Products deleted successfully"}


@router.get(
    "/{product_id}",
    summary="Get product details by ID",
    dependencies=[Depends(require_permission("products:read"))],
)
async def get_product(
    product_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await product_service.get_product(db, product_id=product_id, user=current_user)


@router.put(
    "/{product_id}",
    summary="Update product catalog item",
    dependencies=[Depends(require_permission("products:update"))],
)
async def update_product(
    product_id: str,
    payload: ProductBase,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await product_service.update_product(
        db, product_id=product_id, payload=payload, user=current_user
    )


@router.delete(
    "/{product_id}",
    response_model=MessageResponse,
    summary="Delete product item by ID",
    dependencies=[Depends(require_permission("products:delete"))],
)
async def delete_product(
    product_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await product_service.delete_product(db, product_id=product_id, user=current_user)
    return {"message": f"Product {product_id} deleted successfully", "status": "success"}


@router.get(
    "/{product_id}/inventory",
    summary="Get inventory stock history",
    dependencies=[Depends(require_permission("products:read"))],
)
async def get_product_inventory(
    product_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await product_service.inventory(db, product_id=product_id, user=current_user)


@router.post(
    "/{product_id}/inventory",
    response_model=MessageResponse,
    summary="Update product inventory stock level",
    dependencies=[Depends(require_permission("products:update"))],
)
async def update_product_inventory(
    product_id: str,
    quantity_delta: int = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await product_service.adjust_inventory(
        db, product_id=product_id, quantity_delta=quantity_delta, user=current_user
    )
