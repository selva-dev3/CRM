from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIException, ConflictError, NotFoundError
from app.models import User
from app.models.deal import Deal
from app.repositories.deal_repository import DealRepository
from app.repositories.invoice_repository import invoice_repository
from app.repositories.setting_repository import SettingRepository
from app.schemas.crm_schemas import (
    DealCreate,
    DealCustomFieldDefinition,
    DealCustomFieldValue,
    DealUpdate,
)
from app.services.ai_domain_service import AIDomainService, ai_domain_service
from app.services.custom_field_service import CustomFieldService
from app.services.note_service import note_service
from app.services.notification_service import notification_service
from app.services.org_service import organization_service
from app.services.quote_service import QuoteService, quote_service

# Canonical pipeline stages (mirrors dashboard_service and the frontend STAGES constant).
DEAL_STAGE_CLOSED_WON = "Closed Won"
DEAL_STAGE_CLOSED_LOST = "Closed Lost"
CANONICAL_DEAL_STAGES = [
    "Prospecting",
    "Qualification",
    "Proposal",
    "Negotiation",
    DEAL_STAGE_CLOSED_WON,
    DEAL_STAGE_CLOSED_LOST,
]


def deal_to_dict(d: Deal) -> dict:
    return {
        "id": d.id,
        "title": d.title,
        "amount": d.amount,
        "stage": d.stage,
        "probability": d.probability,
        "expected_close_date": str(d.expected_close_date) if d.expected_close_date else None,
        "assigned_to": d.assigned_to,
        "company_id": d.company_id,
        "contact_id": d.contact_id,
        "custom_fields": d.custom_fields or {},
        "organization_id": d.organization_id,
        "created_at": str(d.created_at) if d.created_at else None,
    }


class DealService:
    """Business logic for the Deal domain."""

    def __init__(
        self,
        repository: DealRepository | None = None,
        quote_service_instance: QuoteService | None = None,
        setting_repository: SettingRepository | None = None,
        ai_service_instance: AIDomainService | None = None,
    ) -> None:
        self.repository = repository or DealRepository()
        self.quote_service = quote_service_instance or quote_service
        self.setting_repository = setting_repository or SettingRepository()
        self.custom_field_service = CustomFieldService(self.setting_repository)
        self.ai_service = ai_service_instance or ai_domain_service

    async def _commit(self, db: AsyncSession, error_message: str) -> None:
        try:
            await db.commit()
        except Exception as e:
            await db.rollback()
            raise APIException(
                status_code=status.HTTP_400_BAD_REQUEST, message=error_message
            ) from e

    async def require_deal(self, db: AsyncSession, deal_id: str) -> Deal:
        deal = await self.repository.get_by_id(db, deal_id)
        if not deal:
            raise NotFoundError(message=f"Deal '{deal_id}' not found")
        return deal

    async def _validate_stage(self, db: AsyncSession, stage: str, organization_id: str) -> None:
        """Allow canonical stages plus stages configured by the organization."""
        if stage in CANONICAL_DEAL_STAGES:
            return
        configured_stages = await self.repository.list_stages(db, organization_id=organization_id)
        if stage not in {s.name for s in configured_stages}:
            raise APIException(
                message=f"Invalid deal stage '{stage}'.",
                code="INVALID_DEAL_STAGE",
            )

    async def list_custom_fields(
        self, db: AsyncSession, current_user: User
    ) -> list[DealCustomFieldDefinition]:
        org_id = await organization_service.resolve_valid_org_id(db, current_user)
        return await self.custom_field_service.list_definitions(
            db, organization_id=org_id, entity_type="Deal"
        )

    async def _validate_custom_fields(
        self,
        db: AsyncSession,
        organization_id: str,
        values: dict[str, DealCustomFieldValue],
    ) -> dict[str, DealCustomFieldValue]:
        return await self.custom_field_service.validate_values(
            db,
            organization_id=organization_id,
            entity_type="Deal",
            values=values,
        )

    async def _guard_closed_won_transition(
        self, db: AsyncSession, deal: Deal, new_stage: str
    ) -> None:
        """Deals with an existing invoice must stay Closed Won (financial auditability)."""
        if deal.stage != DEAL_STAGE_CLOSED_WON or new_stage == DEAL_STAGE_CLOSED_WON:
            return
        invoice = await invoice_repository.get_by_deal(db, deal.id)
        if invoice is not None:
            raise ConflictError(
                message=(
                    f"Deal '{deal.title}' already has invoice "
                    f"'{invoice.invoice_number}' and cannot leave 'Closed Won'."
                ),
                code="DEAL_HAS_INVOICE",
            )

    async def list_deals(
        self,
        db: AsyncSession,
        *,
        organization_id: str | None = None,
        page: int = 1,
        limit: int = 20,
        search: str | None = None,
        stage: str | None = None,
    ) -> list[dict]:
        deals = await self.repository.list(
            db,
            organization_id=organization_id or "",
            page=page,
            limit=limit,
            search=search,
            stage=stage,
        )
        return [deal_to_dict(d) for d in deals]

    async def create_deal(
        self, db: AsyncSession, payload: DealCreate, current_user: User | None
    ) -> dict:
        org_id = await organization_service.resolve_valid_org_id(db, current_user)
        custom_fields = await self._validate_custom_fields(db, org_id, payload.custom_fields)

        assigned_user_id = payload.assigned_to
        if assigned_user_id:
            if not await self.repository.user_exists(db, assigned_user_id):
                assigned_user_id = current_user.id if current_user else None
        else:
            assigned_user_id = current_user.id if current_user else None

        if not assigned_user_id:
            assigned_user_id = await self.repository.first_user_id(db)

        comp_id = payload.company_id
        if comp_id and not await self.repository.company_exists(db, comp_id):
            comp_id = None

        cont_id = payload.contact_id
        if cont_id and not await self.repository.contact_exists(db, cont_id):
            cont_id = None

        deal = await self.repository.create(
            db,
            data={
                "organization_id": org_id,
                "title": payload.title,
                "amount": payload.amount,
                "stage": payload.stage or "Qualification",
                "probability": payload.probability if payload.probability is not None else 20.0,
                "assigned_to": assigned_user_id,
                "company_id": comp_id,
                "contact_id": cont_id,
                "custom_fields": custom_fields,
            },
        )
        await self._commit(db, "Failed to create deal")
        await db.refresh(deal)
        await notification_service.notify(
            db,
            event_name="deal.created",
            organization_id=deal.organization_id,
            actor_user_id=current_user.id if current_user else None,
            entity_type="deal",
            entity_id=deal.id,
            assigned_to=deal.assigned_to,
            data={
                "id": deal.id,
                "title": deal.title,
                "amount": deal.amount,
                "stage": deal.stage,
                "probability": deal.probability,
                "assigned_to": deal.assigned_to,
            },
        )
        return deal_to_dict(deal)

    async def get_deal_stages(self, db: AsyncSession, current_user: User) -> list[dict]:
        organization_id = await organization_service.resolve_valid_org_id(db, current_user)
        stages = await self.repository.list_stages(db, organization_id=organization_id)
        return [{"id": s.id, "name": s.name, "probability": s.default_probability} for s in stages]

    async def create_deal_stage(
        self,
        db: AsyncSession,
        *,
        name: str,
        probability: float,
        current_user: User,
    ) -> dict:
        organization_id = await organization_service.resolve_valid_org_id(db, current_user)
        await self.repository.create_stage(
            db,
            organization_id=organization_id,
            name=name,
            probability=probability,
        )
        await self._commit(db, "Failed to create pipeline stage")
        return {"message": f"Pipeline stage {name} created", "status": "success"}

    async def get_kanban_board(self, db: AsyncSession) -> dict:
        deals = await self.repository.list_all(db)
        board: dict = {}
        for d in deals:
            board.setdefault(d.stage, []).append({"id": d.id, "title": d.title, "amount": d.amount})
        return board

    async def get_win_loss_analytics(self) -> dict:
        return {"win_rate": 0.0, "won_count": 0, "lost_count": 0, "top_loss_reasons": []}

    async def export_deals_csv(self) -> dict:
        return {"download_url": "https://api.crm.com/exports/deals.csv"}

    async def import_deals_csv(self) -> dict:
        return {"message": "Import processing completed", "status": "success"}

    async def bulk_delete(self, db: AsyncSession, ids: list[str]) -> dict:
        deals = await self.repository.list_by_ids(db, ids)
        for deal in deals:
            await self.repository.delete(db, deal)
        await self._commit(db, "Failed to bulk delete deals")
        return {"affected_count": len(deals), "message": "Deals deleted successfully"}

    async def bulk_update_stage(self, db: AsyncSession, ids: list[str], stage: str) -> dict:
        deals = await self.repository.list_by_ids(db, ids)
        for organization_id in {deal.organization_id for deal in deals}:
            await self._validate_stage(db, stage, organization_id)
        for deal in deals:
            await self._guard_closed_won_transition(db, deal, stage)
            deal.stage = stage
        await self._commit(db, "Failed to bulk update deal stage")
        return {"affected_count": len(deals), "message": f"Updated stage to {stage}"}

    async def get_deal(self, db: AsyncSession, deal_id: str) -> dict:
        return deal_to_dict(await self.require_deal(db, deal_id))

    async def update_deal(self, db: AsyncSession, deal_id: str, payload: DealUpdate) -> dict:
        d = await self.require_deal(db, deal_id)

        prev_amount = d.amount
        prev_probability = d.probability

        if payload.stage is not None:
            await self._validate_stage(db, payload.stage, d.organization_id)
            await self._guard_closed_won_transition(db, d, payload.stage)
        if payload.title is not None:
            d.title = payload.title
        if payload.amount is not None:
            d.amount = payload.amount
        if payload.probability is not None:
            d.probability = payload.probability

        if (
            payload.assigned_to is not None
            and payload.assigned_to not in ("null", "None", "")
            and await self.repository.user_exists(db, payload.assigned_to)
        ):
            d.assigned_to = payload.assigned_to

        if payload.company_id is not None:
            if payload.company_id in ("null", "None", ""):
                d.company_id = None
            elif await self.repository.company_exists(db, payload.company_id):
                d.company_id = payload.company_id

        if payload.contact_id is not None:
            if payload.contact_id in ("null", "None", ""):
                d.contact_id = None
            elif await self.repository.contact_exists(db, payload.contact_id):
                d.contact_id = payload.contact_id

        if payload.custom_fields is not None:
            d.custom_fields = await self._validate_custom_fields(
                db, d.organization_id, payload.custom_fields
            )

        await self._commit(db, "Failed to update deal")
        await db.refresh(d)
        if d.amount != prev_amount:
            await notification_service.notify(
                db,
                event_name="deal.amount_changed",
                organization_id=d.organization_id,
                entity_type="deal",
                entity_id=d.id,
                assigned_to=d.assigned_to,
                data={
                    "id": d.id,
                    "title": d.title,
                    "old_amount": prev_amount,
                    "amount": d.amount,
                },
            )
        if d.probability != prev_probability:
            await notification_service.notify(
                db,
                event_name="deal.probability_changed",
                organization_id=d.organization_id,
                entity_type="deal",
                entity_id=d.id,
                assigned_to=d.assigned_to,
                data={
                    "id": d.id,
                    "title": d.title,
                    "old_probability": prev_probability,
                    "probability": d.probability,
                },
            )
        return deal_to_dict(d)

    async def delete_deal(self, db: AsyncSession, deal_id: str) -> dict:
        d = await self.require_deal(db, deal_id)
        await self.repository.delete(db, d)
        await self._commit(db, "Failed to delete deal")
        return {"message": f"Deal {deal_id} deleted successfully", "status": "success"}

    async def update_deal_stage(self, db: AsyncSession, deal_id: str, stage: str) -> dict:
        d = await self.require_deal(db, deal_id)
        await self._validate_stage(db, stage, d.organization_id)
        await self._guard_closed_won_transition(db, d, stage)
        d.stage = stage
        await self._commit(db, "Failed to update deal stage")
        await notification_service.notify(
            db,
            event_name="deal.stage_changed",
            organization_id=d.organization_id,
            entity_type="deal",
            entity_id=d.id,
            assigned_to=d.assigned_to,
            data={"id": d.id, "title": d.title, "stage": d.stage, "amount": d.amount},
        )
        return {"message": f"Deal {deal_id} moved to {stage}", "status": "success"}

    async def mark_deal_won(
        self, db: AsyncSession, deal_id: str, final_amount: float | None
    ) -> dict:
        d = await self.require_deal(db, deal_id)
        d.stage = DEAL_STAGE_CLOSED_WON
        d.probability = 100.0
        if final_amount:
            d.amount = final_amount
        await self._commit(db, "Failed to mark deal as won")
        await notification_service.notify(
            db,
            event_name="deal.won",
            organization_id=d.organization_id,
            entity_type="deal",
            entity_id=d.id,
            assigned_to=d.assigned_to,
            data={"id": d.id, "title": d.title, "amount": d.amount, "stage": d.stage},
        )
        return {"message": f"Deal {deal_id} marked as Closed Won!", "status": "success"}

    async def mark_deal_lost(self, db: AsyncSession, deal_id: str, reason: str) -> dict:
        d = await self.require_deal(db, deal_id)
        await self._guard_closed_won_transition(db, d, DEAL_STAGE_CLOSED_LOST)
        d.stage = DEAL_STAGE_CLOSED_LOST
        d.probability = 0.0
        # Persist the caller-supplied reason so win/loss and churn reports can
        # aggregate real loss reasons instead of placeholders.
        d.loss_reason = (reason or "").strip() or None
        await self._commit(db, "Failed to mark deal as lost")
        await notification_service.notify(
            db,
            event_name="deal.lost",
            organization_id=d.organization_id,
            entity_type="deal",
            entity_id=d.id,
            assigned_to=d.assigned_to,
            data={"id": d.id, "title": d.title, "amount": d.amount, "reason": reason},
        )
        return {"message": f"Deal {deal_id} marked as Lost due to: {reason}", "status": "success"}

    async def assign_deal(self, db: AsyncSession, deal_id: str, user_id: str) -> dict:
        d = await self.require_deal(db, deal_id)
        d.assigned_to = user_id
        await self._commit(db, "Failed to assign deal")
        await notification_service.notify(
            db,
            event_name="deal.assigned",
            organization_id=d.organization_id,
            entity_type="deal",
            entity_id=d.id,
            assigned_to=d.assigned_to,
            data={"id": d.id, "title": d.title, "assigned_to": d.assigned_to},
        )
        return {"message": f"Deal {deal_id} assigned to user {user_id}", "status": "success"}

    async def get_deal_products(self, db: AsyncSession, deal_id: str) -> list[dict]:
        deal_prods = await self.repository.list_deal_products(db, deal_id)
        result = []
        for dp in deal_prods:
            p = await self.repository.get_product(db, dp.product_id)
            sku_code = p.sku if p else "N/A"
            name_val = p.name if p else f"Product #{dp.product_id}"
            price_val = dp.unit_price or (p.price if p else 0.0)
            result.append(
                {
                    "id": dp.product_id,
                    "name": name_val,
                    "code": sku_code,
                    "sku": sku_code,
                    "price": price_val,
                    "unit_price": price_val,
                    "quantity": dp.quantity,
                    "category": "General",
                    "in_stock_quantity": p.in_stock_quantity if p else 100,
                    "is_active": p.is_active if p else True,
                }
            )
        return result

    async def _recalculate_deal_amount(
        self, db: AsyncSession, deal_id: str, *, force: bool
    ) -> None:
        all_dps = await self.repository.list_deal_products(db, deal_id)
        total = sum(item.quantity * (item.unit_price or 0.0) for item in all_dps)
        deal = await self.repository.get_by_id(db, deal_id)
        if deal and (force or total > 0):
            deal.amount = total
            await self._commit(db, "Failed to recalculate deal amount")

    async def add_deal_product(
        self,
        db: AsyncSession,
        *,
        deal_id: str,
        product_id: str,
        quantity: int,
        unit_price: float | None,
        custom_name: str | None,
    ) -> dict:
        deal = await self.require_deal(db, deal_id)
        p = await self.repository.get_product(db, product_id)

        if not p and custom_name:
            p = await self.repository.get_product_by_name(db, custom_name)
            if not p:
                sku_gen = f"SKU-{custom_name.replace(' ', '-').upper()[:10]}"
                p = await self.repository.create_product(
                    db,
                    organization_id=deal.organization_id,
                    name=custom_name,
                    sku=sku_gen,
                    price=unit_price or 0.0,
                )
                await db.commit()
                await db.refresh(p)
                product_id = p.id
            else:
                product_id = p.id

        price = unit_price if unit_price is not None else (p.price if p else 0.0)

        existing_dp = await self.repository.get_deal_product(
            db, deal_id=deal_id, product_id=product_id
        )
        if existing_dp:
            existing_dp.quantity += quantity
            if unit_price is not None:
                existing_dp.unit_price = unit_price
        else:
            await self.repository.create_deal_product(
                db, deal_id=deal_id, product_id=product_id, quantity=quantity, unit_price=price
            )

        await self._commit(db, "Failed to add product to deal")
        await self._recalculate_deal_amount(db, deal_id, force=False)
        return {"message": f"Added product item to deal {deal_id}", "status": "success"}

    async def remove_deal_product(self, db: AsyncSession, *, deal_id: str, product_id: str) -> dict:
        dp = await self.repository.get_deal_product(db, deal_id=deal_id, product_id=product_id)
        if dp:
            await self.repository.delete_deal_product(db, dp)
            await self._commit(db, "Failed to remove product from deal")
        await self._recalculate_deal_amount(db, deal_id, force=True)
        return {"message": f"Removed product {product_id} from deal {deal_id}", "status": "success"}

    async def get_deal_timeline(self, db: AsyncSession, deal_id: str) -> list:
        await self.require_deal(db, deal_id)
        return []

    async def get_deal_notes(
        self, db: AsyncSession, deal_id: str, current_user: User
    ) -> list[dict]:
        return await note_service.get_notes_by_entity(
            db, entity_type="deal", entity_id=deal_id, current_user=current_user
        )

    async def add_deal_note(
        self, db: AsyncSession, *, deal_id: str, content: str | None, current_user: User
    ) -> dict:
        return await note_service.add_for_entity(
            db,
            entity_type="deal",
            entity_id=deal_id,
            content=content or "Note",
            current_user=current_user,
        )

    async def get_deal_quotes(
        self, db: AsyncSession, deal_id: str, organization_id: str
    ) -> list[dict]:
        deal = await self.repository.get_by_id_scoped(
            db, deal_id=deal_id, organization_id=organization_id
        )
        if not deal:
            raise NotFoundError(message=f"Deal '{deal_id}' not found")
        return await self.quote_service.list_quotes_for_deal(
            db, deal_id=deal_id, organization_id=organization_id
        )

    async def predict_deal_win_rate(
        self, db: AsyncSession, deal_id: str, current_user: User
    ) -> dict:
        prediction = await self.ai_service.predict_deal_forecast(db, deal_id, current_user)
        return {
            "deal_id": deal_id,
            "predicted_probability": prediction["win_probability"],
            "key_drivers": prediction["key_drivers"],
            "ai_recommendation": prediction["next_action"],
            "risk_factors": prediction["risk_factors"],
            "run_id": prediction["run_id"],
        }

    async def clone_deal(self, db: AsyncSession, *, deal_id: str, new_title: str) -> dict:
        orig = await self.require_deal(db, deal_id)
        deal = await self.repository.create(
            db,
            data={
                "organization_id": orig.organization_id,
                "title": new_title,
                "amount": orig.amount,
                "stage": "Prospecting",
                "probability": 10.0,
                "assigned_to": orig.assigned_to,
            },
        )
        await self._commit(db, "Failed to clone deal")
        await db.refresh(deal)
        return {
            "id": deal.id,
            "title": deal.title,
            "amount": deal.amount,
            "stage": deal.stage,
            "probability": deal.probability,
            "expected_close_date": (
                deal.expected_close_date.isoformat() if deal.expected_close_date else None
            ),
            "assigned_to": deal.assigned_to,
            "organization_id": deal.organization_id,
            "created_at": deal.created_at.isoformat() if deal.created_at else None,
        }

    async def get_deal_commission(self, db: AsyncSession, deal_id: str) -> dict:
        d = await self.require_deal(db, deal_id)
        return {
            "deal_id": deal_id,
            "rep_id": d.assigned_to,
            "commission_rate_pct": 10.0,
            "estimated_commission": (d.amount or 0.0) * 0.1,
        }


deal_service = DealService()
