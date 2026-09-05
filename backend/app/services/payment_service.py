from __future__ import annotations

from app.repositories.payment_repository import PaymentRepository


def payment_to_dict(row: tuple) -> dict[str, object]:
    payment, invoice_number, company_name, contact_name, contact_email = row
    return {
        "id": payment.id,
        "invoice_id": payment.invoice_id,
        "invoice_number": invoice_number,
        "company_name": company_name,
        "contact_name": contact_name,
        "contact_email": contact_email,
        "amount": payment.amount or 0.0,
        "currency": payment.currency,
        "payment_method": payment.payment_method,
        "status": payment.status,
        "provider": payment.provider,
        "provider_payment_id": payment.provider_payment_id,
        "checkout_session_id": payment.checkout_session_id,
        "paid_at": payment.paid_at.isoformat(),
        "created_at": payment.created_at.isoformat() if payment.created_at else None,
    }


class PaymentService:
    def __init__(self, repository: PaymentRepository | None = None) -> None:
        self.repository = repository or PaymentRepository()

    async def list_payments(self, db, *, organization_id: str, page: int, limit: int,
                            status: str | None = None, search: str | None = None,
                            invoice_id: str | None = None) -> list[dict[str, object]]:
        rows = await self.repository.list_scoped(
            db,
            organization_id=organization_id,
            page=page,
            limit=limit,
            status=status,
            search=search,
            invoice_id=invoice_id,
        )
        return [payment_to_dict(row) for row in rows]

    async def get_payment(self, db, *, payment_id: str, organization_id: str) -> dict[str, object] | None:
        row = await self.repository.get_scoped(
            db, payment_id=payment_id, organization_id=organization_id
        )
        return payment_to_dict(row) if row else None


payment_service = PaymentService()
