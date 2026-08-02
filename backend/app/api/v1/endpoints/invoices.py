from fastapi import APIRouter
from typing import List
from app.schemas.crm_schemas import InvoiceResponse, InvoiceBase

router = APIRouter()

@router.get("/", response_model=List[InvoiceResponse], summary="List billing invoices")
async def list_invoices():
    return [
        {"id": "inv-1", "invoice_number": "INV-2026-001", "amount": 12000.0, "status": "Paid", "due_date": "2026-08-15", "stripe_checkout_url": "https://checkout.stripe.com/c/pay/cs_test_123", "created_at": "2026-08-01T10:00:00Z"}
    ]

@router.post("/", response_model=InvoiceResponse, status_code=201, summary="Generate invoice")
async def create_invoice(payload: InvoiceBase):
    return {"id": "inv-2", **payload.model_dump(), "stripe_checkout_url": "https://checkout.stripe.com/c/pay/cs_test_456", "created_at": "2026-08-02T12:00:00Z"}
