from decimal import Decimal
from uuid import NAMESPACE_URL, uuid5

from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIException, ConflictError, NotFoundError
from app.models import User
from app.models.deal import Deal
from app.repositories.deal_repository import DealRepository
from app.repositories.invoice_repository import invoice_repository
from app.repositories.project_repository import ProjectRepository
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
from app.services.sales_totals import calculate_line, decimal_value, rounded_value

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
        "project_id": getattr(d, "project_id", None),
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
        project_repository: ProjectRepository | None = None,
    ) -> None:
        self.repository = repository or DealRepository()
        self.quote_service = quote_service_instance or quote_service
        self.setting_repository = setting_repository or SettingRepository()
        self.custom_field_service = CustomFieldService(self.setting_repository)
        self.ai_service = ai_service_instance or ai_domain_service
        self.project_repository = project_repository or ProjectRepository()

    async def _validate_project(
        self, db: AsyncSession, project_id: str | None, organization_id: str
    ) -> str | None:
        if not project_id or project_id in {"null", "None"}:
            return None
        project = await self.project_repository.get(
            db, project_id=project_id, organization_id=organization_id
        )
        if not project:
            raise NotFoundError(message=f"Project '{project_id}' not found")
        return project.id

    async def _commit(self, db: AsyncSession, error_message: str) -> None:
        try:
            await db.commit()
        except Exception as e:
            await db.rollback()
            raise APIException(
                status_code=status.HTTP_400_BAD_REQUEST, message=error_message
            ) from e

    async def require_deal(
        self, db: AsyncSession, deal_id: str, *, organization_id: str, lock: bool = False
    ) -> Deal:
        deal = await self.repository.get_by_id_scoped(
            db, deal_id=deal_id, organization_id=organization_id, lock=lock
        )
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

    async def _validate_customer_links(
        self,
        db: AsyncSession,
        *,
        organization_id: str,
        company_id: str | None,
        contact_id: str | None,
    ) -> None:
        if company_id and not await self.repository.company_exists(
            db, company_id, organization_id=organization_id
        ):
            raise NotFoundError(message="Company not found")
        if not contact_id:
            return
        if not company_id:
            raise APIException(
                message="Select a company before selecting a contact",
                code="DEAL_COMPANY_REQUIRED",
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            )
        if not await self.repository.contact_exists(
            db, contact_id, organization_id=organization_id
        ):
            raise NotFoundError(message="Contact not found")
        if not await self.repository.contact_belongs_to_company(
            db,
            contact_id,
            company_id,
            organization_id=organization_id,
        ):
            raise APIException(
                message="The selected contact is not linked to the selected company",
                code="DEAL_CONTACT_COMPANY_MISMATCH",
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            )

    async def _guard_closed_won_transition(
        self, db: AsyncSession, deal: Deal, new_stage: str
    ) -> None:
        """Deals with an existing invoice must stay Closed Won (financial auditability)."""
        if deal.stage != DEAL_STAGE_CLOSED_WON or new_stage == DEAL_STAGE_CLOSED_WON:
            return
        invoice = await invoice_repository.get_by_deal_scoped(
            db, deal_id=deal.id, organization_id=deal.organization_id
        )
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

    async def create_deal(self, db: AsyncSession, payload: DealCreate, current_user: User) -> dict:
        if payload.stage == DEAL_STAGE_CLOSED_WON:
            raise APIException(
                message="Create the deal and add products before marking it Closed Won"
            )
        org_id = await organization_service.resolve_valid_org_id(db, current_user)
        custom_fields = await self._validate_custom_fields(db, org_id, payload.custom_fields)
        project_id = await self._validate_project(db, payload.project_id, org_id)

        assigned_user_id = payload.assigned_to
        if assigned_user_id:
            if not await self.repository.user_exists(db, assigned_user_id, organization_id=org_id):
                raise NotFoundError(message="Assigned user not found")
        else:
            assigned_user_id = current_user.id

        comp_id = payload.company_id
        cont_id = payload.contact_id
        await self._validate_customer_links(
            db,
            organization_id=org_id,
            company_id=comp_id,
            contact_id=cont_id,
        )

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
                "project_id": project_id,
                "custom_fields": custom_fields,
            },
        )
        await db.flush()
        await self.repository.create_initial_stage_history(db, deal=deal, actor_id=current_user.id)
        await self.repository.add_activity(
            db, deal_id=deal.id, action="Deal created", actor_id=current_user.id
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

    async def get_kanban_board(self, db: AsyncSession, *, organization_id: str) -> dict:
        deals = await self.repository.list_all(db, organization_id=organization_id)
        board: dict = {}
        for d in deals:
            board.setdefault(d.stage, []).append({"id": d.id, "title": d.title, "amount": d.amount})
        return board

    async def get_win_loss_analytics(self, db: AsyncSession, *, organization_id: str) -> dict:
        deals = await self.repository.list_all(db, organization_id=organization_id)
        won = [deal for deal in deals if deal.stage == DEAL_STAGE_CLOSED_WON]
        lost = [deal for deal in deals if deal.stage == DEAL_STAGE_CLOSED_LOST]
        decided = len(won) + len(lost)
        reasons: dict[str, int] = {}
        for deal in lost:
            reason = (deal.loss_reason or "Unspecified").strip()
            reasons[reason] = reasons.get(reason, 0) + 1
        return {
            "win_rate": round((len(won) / decided) * 100, 2) if decided else 0.0,
            "won_count": len(won),
            "lost_count": len(lost),
            "top_loss_reasons": [
                {"reason": reason, "count": count}
                for reason, count in sorted(reasons.items(), key=lambda item: (-item[1], item[0]))
            ],
        }

    async def export_deals_csv(self) -> dict:
        raise APIException(
            message="Deal CSV export is not implemented",
            code="DEAL_EXPORT_UNAVAILABLE",
            status_code=501,
        )

    async def import_deals_csv(self) -> dict:
        raise APIException(
            message="Deal CSV import is not implemented",
            code="DEAL_IMPORT_UNAVAILABLE",
            status_code=501,
        )

    async def bulk_delete(self, db: AsyncSession, ids: list[str], *, organization_id: str) -> dict:
        deals = await self.repository.list_by_ids(db, ids, organization_id=organization_id)
        for deal in deals:
            await self.repository.delete(db, deal)
        await self._commit(db, "Failed to bulk delete deals")
        return {"affected_count": len(deals), "message": "Deals deleted successfully"}

    async def bulk_update_stage(
        self, db: AsyncSession, ids: list[str], stage: str, *, organization_id: str, actor_id: str
    ) -> dict:
        try:
            await self._validate_stage(db, stage, organization_id)
            for deal_id in sorted(set(ids)):
                deal = await self.repository.get_by_id_scoped(
                    db,
                    deal_id=deal_id,
                    organization_id=organization_id,
                    lock=True,
                )
                if not deal:
                    raise NotFoundError(message="Deal not found")
                if stage == DEAL_STAGE_CLOSED_WON:
                    await self._apply_won(db, deal, actor_id)
                else:
                    await self._guard_closed_won_transition(db, deal, stage)
                    await self.repository.transition_stage(
                        db, deal=deal, stage=stage, actor_id=actor_id
                    )
            await db.commit()
            return {"affected_count": len(set(ids)), "message": f"Updated stage to {stage}"}
        except Exception:
            await db.rollback()
            raise

    async def get_deal(self, db: AsyncSession, deal_id: str, *, organization_id: str) -> dict:
        return deal_to_dict(await self.require_deal(db, deal_id, organization_id=organization_id))

    async def update_deal(
        self,
        db: AsyncSession,
        deal_id: str,
        payload: DealUpdate,
        *,
        organization_id: str | None = None,
        actor_id: str | None = None,
    ) -> dict:
        if not organization_id:
            raise APIException(message="Organization is required", status_code=403)
        d = await self.repository.get_by_id_scoped(
            db,
            deal_id=deal_id,
            organization_id=organization_id,
            lock=True,
        )
        if not d:
            raise NotFoundError(message="Deal not found")
        if payload.stage == DEAL_STAGE_CLOSED_WON:
            if not organization_id or not actor_id:
                raise APIException(message="Organization and actor are required to close a deal")
            if payload.model_fields_set - {"stage", "amount"}:
                raise APIException(
                    message="Save other deal changes before marking it Closed Won",
                    code="MIXED_DEAL_CLOSE_UPDATE",
                    status_code=409,
                )
            await self.mark_deal_won(
                db, deal_id, None, organization_id=organization_id, actor_id=actor_id
            )
            return deal_to_dict(d)

        prev_amount = d.amount
        prev_probability = d.probability

        if payload.stage is not None:
            await self._validate_stage(db, payload.stage, d.organization_id)
            await self._guard_closed_won_transition(db, d, payload.stage)
            await self.repository.transition_stage(
                db, deal=d, stage=payload.stage, actor_id=actor_id
            )
        if payload.title is not None:
            d.title = payload.title
        if payload.amount is not None:
            d.amount = payload.amount
        if payload.probability is not None:
            d.probability = payload.probability

        if (
            payload.assigned_to is not None
            and payload.assigned_to not in ("null", "None", "")
            and await self.repository.user_exists(
                db, payload.assigned_to, organization_id=d.organization_id
            )
        ):
            d.assigned_to = payload.assigned_to

        customer_fields = payload.model_fields_set & {"company_id", "contact_id"}
        if customer_fields:
            company_id = d.company_id
            contact_id = d.contact_id
            if "company_id" in customer_fields:
                company_id = (
                    None if payload.company_id in (None, "null", "None", "") else payload.company_id
                )
            if "contact_id" in customer_fields:
                contact_id = (
                    None if payload.contact_id in (None, "null", "None", "") else payload.contact_id
                )
            await self._validate_customer_links(
                db,
                organization_id=d.organization_id,
                company_id=company_id,
                contact_id=contact_id,
            )
            d.company_id = company_id
            d.contact_id = contact_id

        if payload.project_id is not None:
            d.project_id = await self._validate_project(db, payload.project_id, d.organization_id)

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

    async def delete_deal(self, db: AsyncSession, deal_id: str, *, organization_id: str) -> dict:
        d = await self.require_deal(db, deal_id, organization_id=organization_id)
        await self.repository.delete(db, d)
        await self._commit(db, "Failed to delete deal")
        return {"message": f"Deal {deal_id} deleted successfully", "status": "success"}

    async def update_deal_stage(
        self, db: AsyncSession, deal_id: str, stage: str, *, organization_id: str, actor_id: str
    ) -> dict:
        if stage == DEAL_STAGE_CLOSED_WON:
            return await self.mark_deal_won(
                db, deal_id, None, organization_id=organization_id, actor_id=actor_id
            )
        d = await self.repository.get_by_id_scoped(
            db,
            deal_id=deal_id,
            organization_id=organization_id,
            lock=True,
        )
        if not d:
            raise NotFoundError(message="Deal not found")
        await self._validate_stage(db, stage, d.organization_id)
        await self._guard_closed_won_transition(db, d, stage)
        changed = await self.repository.transition_stage(db, deal=d, stage=stage, actor_id=actor_id)
        if not changed:
            return {"message": f"Deal {deal_id} is already in {stage}", "status": "success"}
        await self.repository.add_activity(
            db,
            deal_id=d.id,
            action=f"Stage changed to {stage}",
            actor_id=actor_id,
        )
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
        self,
        db: AsyncSession,
        deal_id: str,
        final_amount: float | None,
        *,
        organization_id: str,
        actor_id: str,
    ) -> dict:
        try:
            d = await self.repository.get_by_id_scoped(
                db,
                deal_id=deal_id,
                organization_id=organization_id,
                lock=True,
            )
            if not d:
                raise NotFoundError(message="Deal not found")
            quote = await self._apply_won(db, d, actor_id)
            await db.commit()
            return {
                "message": "Deal won; quote created",
                "status": "success",
                "deal_id": d.id,
                "stage": d.stage,
                "quote_id": quote.id,
                "quote_status": quote.status,
            }
        except Exception:
            await db.rollback()
            raise

    async def _apply_won(self, db: AsyncSession, deal: Deal, actor_id: str):
        was_won = deal.stage == DEAL_STAGE_CLOSED_WON
        if not was_won:
            await self.repository.transition_stage(
                db, deal=deal, stage=DEAL_STAGE_CLOSED_WON, actor_id=actor_id
            )
        await self.repository.set_won(db, deal, deal.amount)
        quote = await self.quote_service.create_from_won_deal(db, deal=deal, actor_id=actor_id)
        await self.repository.set_won(db, deal, float(quote.total_amount))
        if not was_won:
            await self.repository.add_activity(
                db,
                deal_id=deal.id,
                action=f"Deal won; quote {quote.quote_number} created",
                actor_id=actor_id,
            )
        return quote

    async def mark_deal_lost(
        self,
        db: AsyncSession,
        deal_id: str,
        reason: str,
        *,
        organization_id: str,
        actor_id: str | None = None,
    ) -> dict:
        d = await self.require_deal(db, deal_id, organization_id=organization_id, lock=True)
        await self._guard_closed_won_transition(db, d, DEAL_STAGE_CLOSED_LOST)
        await self.repository.transition_stage(
            db, deal=d, stage=DEAL_STAGE_CLOSED_LOST, actor_id=actor_id
        )
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

    async def assign_deal(
        self, db: AsyncSession, deal_id: str, user_id: str, *, organization_id: str
    ) -> dict:
        d = await self.require_deal(db, deal_id, organization_id=organization_id, lock=True)
        if not await self.repository.user_exists(db, user_id, organization_id=organization_id):
            raise NotFoundError(message="Assigned user not found")
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

    async def get_deal_products(
        self, db: AsyncSession, deal_id: str, *, organization_id: str
    ) -> list[dict]:
        await self.require_deal(db, deal_id, organization_id=organization_id)
        deal_prods = await self.repository.list_deal_products(
            db, deal_id, organization_id=organization_id
        )
        result = []
        for dp in deal_prods:
            p = await self.repository.get_product_scoped(
                db, product_id=dp.product_id, organization_id=organization_id
            )
            sku_code = p.sku if p else ""
            name_val = p.name if p else dp.product_name or "Deleted product"
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
                    "category": "",
                    "in_stock_quantity": p.in_stock_quantity if p else 0,
                    "is_active": p.is_active if p else False,
                }
            )
        return result

    async def _recalculate_deal_amount(
        self, db: AsyncSession, deal_id: str, *, organization_id: str, force: bool
    ) -> None:
        all_dps = await self.repository.list_deal_products(
            db, deal_id, organization_id=organization_id
        )
        total = sum(
            (item.quantity * decimal_value(item.unit_price or 0) for item in all_dps),
            Decimal(0),
        )
        deal = await self.repository.get_by_id_scoped(
            db, deal_id=deal_id, organization_id=organization_id
        )
        if deal and (force or total > 0):
            deal.amount = float(total)
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
        organization_id: str,
        discount_percent: float = 0,
        tax_percent: float = 0,
    ) -> dict:
        try:
            deal = await self._mutable_sales_deal(db, deal_id, organization_id)
            p = await self.repository.get_product_scoped(
                db,
                product_id=product_id,
                organization_id=organization_id,
            )
            if not p and not product_id and custom_name and custom_name.strip():
                validated_price = float(decimal_value(unit_price))
                sku = f"CUSTOM-{uuid5(NAMESPACE_URL, organization_id + ':' + custom_name.strip().casefold()).hex}"
                p = await self.repository.get_product_by_sku(
                    db, organization_id=organization_id, sku=sku
                )
                if not p:
                    p = await self.repository.create_product(
                        db,
                        organization_id=organization_id,
                        name=custom_name.strip(),
                        sku=sku,
                        price=validated_price,
                    )
                    await db.flush()
            if not p or p.organization_id != organization_id:
                raise NotFoundError(message="Product not found")
            if not p.is_active:
                raise APIException(message="Inactive products cannot be added to a deal")
            price = unit_price if unit_price is not None else p.price
            calculate_line(quantity, price, discount_percent, tax_percent)
            line = await self.repository.get_deal_product(
                db,
                deal_id=deal_id,
                product_id=p.id,
                organization_id=organization_id,
            )
            if not line:
                line = await self.repository.create_deal_product(
                    db, deal_id=deal_id, product_id=p.id, quantity=quantity, unit_price=price
                )
            # Upsert absolute quantity, rather than incrementing on a retried request.
            await self.repository.save_product_snapshot(
                db,
                line,
                product_name=p.name,
                quantity=quantity,
                unit_price=rounded_value(price),
                discount_percent=rounded_value(discount_percent, maximum=Decimal(100)),
                tax_percent=rounded_value(tax_percent, maximum=Decimal(100)),
            )
            await db.flush()
            await self._update_sales_total(db, deal)
            await db.commit()
            return {"message": "Deal product saved", "status": "success"}
        except Exception:
            await db.rollback()
            raise

    async def _mutable_sales_deal(
        self, db: AsyncSession, deal_id: str, organization_id: str
    ) -> Deal:
        deal = await self.repository.get_by_id_scoped(
            db, deal_id=deal_id, organization_id=organization_id, lock=True
        )
        if not deal:
            raise NotFoundError(message="Deal not found")
        quote = await self.quote_service.repository.get_automatic(
            db, deal_id=deal_id, organization_id=organization_id
        )
        if deal.stage == DEAL_STAGE_CLOSED_WON or quote:
            raise ConflictError(message="Products on a closed or quoted deal cannot be changed")
        return deal

    async def _update_sales_total(self, db: AsyncSession, deal: Deal) -> None:
        lines = await self.repository.list_deal_products(
            db, deal.id, organization_id=deal.organization_id
        )
        total = sum(
            (
                calculate_line(
                    line.quantity,
                    line.unit_price,
                    line.discount_percent or 0,
                    line.tax_percent or 0,
                ).total
                for line in lines
            ),
            Decimal(0),
        )
        await self.repository.set_amount(db, deal, float(decimal_value(total)))

    async def remove_deal_product(
        self, db: AsyncSession, *, deal_id: str, product_id: str, organization_id: str
    ) -> dict:
        try:
            deal = await self._mutable_sales_deal(db, deal_id, organization_id)
            dp = await self.repository.get_deal_product(
                db,
                deal_id=deal_id,
                product_id=product_id,
                organization_id=organization_id,
            )
            if dp:
                await self.repository.delete_deal_product(db, dp)
            await db.flush()
            await self._update_sales_total(db, deal)
            await db.commit()
            return {"message": "Deal product removed", "status": "success"}
        except Exception:
            await db.rollback()
            raise

    async def get_deal_timeline(
        self, db: AsyncSession, deal_id: str, *, organization_id: str
    ) -> list:
        await self.require_deal(db, deal_id, organization_id=organization_id)
        activities = await self.repository.list_activities(
            db, deal_id=deal_id, organization_id=organization_id
        )
        return [
            {
                "id": activity.id,
                "action": activity.action,
                "performed_by": activity.performed_by,
                "timestamp": (activity.timestamp.isoformat() if activity.timestamp else None),
            }
            for activity in activities
        ]

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

    async def clone_deal(
        self, db: AsyncSession, *, deal_id: str, new_title: str, organization_id: str
    ) -> dict:
        orig = await self.require_deal(db, deal_id, organization_id=organization_id)
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

    async def get_deal_commission(
        self, db: AsyncSession, deal_id: str, *, organization_id: str
    ) -> dict:
        d = await self.require_deal(db, deal_id, organization_id=organization_id)
        return {
            "deal_id": deal_id,
            "rep_id": d.assigned_to,
            "commission_rate_pct": 10.0,
            "estimated_commission": (d.amount or 0.0) * 0.1,
        }


deal_service = DealService()
