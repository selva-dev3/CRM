from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIException
from app.db.session import get_db
from app.services.invoice_payment_service import invoice_payment_service

router = APIRouter()


@router.post("/stripe")
async def invoice_stripe_webhook(request: Request, stripe_signature: str = Header(...),
                                  db: AsyncSession = Depends(get_db)):
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > 1024 * 1024:
            raise APIException(message="Webhook payload is too large", status_code=413)
    return await invoice_payment_service.webhook(db, payload=bytes(body), signature=stripe_signature)
