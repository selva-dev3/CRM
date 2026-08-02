from fastapi import APIRouter
from typing import List
from app.schemas.crm_schemas import ProductResponse, ProductBase

router = APIRouter()

@router.get("/", response_model=List[ProductResponse], summary="List catalog products")
async def list_products():
    return [
        {"id": "prod-1", "name": "CRM Enterprise Seat (Annual)", "sku": "CRM-ENT-01", "price": 1200.0, "category": "Subscription"}
    ]

@router.post("/", response_model=ProductResponse, status_code=201, summary="Create catalog product")
async def create_product(payload: ProductBase):
    return {"id": "prod-2", **payload.model_dump()}
