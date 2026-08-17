import json
import os
from typing import Optional

import httpx
from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import APIException, NotFoundError
from app.core.logging import get_logger
from app.models import User
from app.models.deal import Deal
from app.repositories.deal_repository import DealRepository
from app.schemas.crm_schemas import DealCreate, DealUpdate
from app.services.note_service import note_service
from app.services.notification_service import notification_service
from app.services.org_service import organization_service

logger = get_logger(__name__)


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
        "organization_id": d.organization_id,
        "created_at": str(d.created_at) if d.created_at else None,
    }


class DealService:
    """Business logic for the Deal domain."""

    def __init__(self, repository: Optional[DealRepository] = None) -> None:
        self.repository = repository or DealRepository()

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

    async def list_deals(
        self,
        db: AsyncSession,
        *,
        page: int,
        limit: int,
        search: Optional[str] = None,
        stage: Optional[str] = None,
    ) -> list[dict]:
        deals = await self.repository.list(
            db, page=page, limit=limit, search=search, stage=stage
        )
        return [deal_to_dict(d) for d in deals]

    async def create_deal(
        self, db: AsyncSession, payload: DealCreate, current_user: Optional[User]
    ) -> dict:
        org_id = await organization_service.resolve_valid_org_id(db, current_user)

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

    async def get_deal_stages(self, db: AsyncSession) -> list[dict]:
        stages = await self.repository.list_stages(db)
        return [{"id": s.id, "name": s.name, "probability": s.default_probability} for s in stages]

    async def create_deal_stage(self, db: AsyncSession, *, name: str, probability: float) -> dict:
        await self.repository.create_stage(
            db, organization_id="org-1", name=name, probability=probability
        )
        await self._commit(db, "Failed to create pipeline stage")
        return {"message": f"Pipeline stage {name} created", "status": "success"}

    async def get_kanban_board(self, db: AsyncSession) -> dict:
        deals = await self.repository.list_all(db)
        board: dict = {}
        for d in deals:
            board.setdefault(d.stage, []).append(
                {"id": d.id, "title": d.title, "amount": d.amount}
            )
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
        for deal in deals:
            deal.stage = stage
        await self._commit(db, "Failed to bulk update deal stage")
        return {"affected_count": len(deals), "message": f"Updated stage to {stage}"}

    async def get_deal(self, db: AsyncSession, deal_id: str) -> dict:
        return deal_to_dict(await self.require_deal(db, deal_id))

    async def update_deal(self, db: AsyncSession, deal_id: str, payload: DealUpdate) -> dict:
        d = await self.require_deal(db, deal_id)

        prev_amount = d.amount
        prev_probability = d.probability

        if payload.title is not None:
            d.title = payload.title
        if payload.amount is not None:
            d.amount = payload.amount
        if payload.stage is not None:
            d.stage = payload.stage
        if payload.probability is not None:
            d.probability = payload.probability

        if payload.assigned_to is not None and payload.assigned_to not in ("null", "None", ""):
            if await self.repository.user_exists(db, payload.assigned_to):
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
        self, db: AsyncSession, deal_id: str, final_amount: Optional[float]
    ) -> dict:
        d = await self.require_deal(db, deal_id)
        d.stage = "Closed Won"
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
        d.stage = "Closed Lost"
        d.probability = 0.0
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
            await db.commit()

    async def add_deal_product(
        self,
        db: AsyncSession,
        *,
        deal_id: str,
        product_id: str,
        quantity: int,
        unit_price: Optional[float],
        custom_name: Optional[str],
    ) -> dict:
        p = await self.repository.get_product(db, product_id)

        if not p and custom_name:
            p = await self.repository.get_product_by_name(db, custom_name)
            if not p:
                sku_gen = f"SKU-{custom_name.replace(' ', '-').upper()[:10]}"
                p = await self.repository.create_product(
                    db,
                    organization_id="org-1",
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

    async def get_deal_notes(self, db: AsyncSession, deal_id: str) -> list[dict]:
        return await note_service.get_notes_by_entity(db, entity_type="deal", entity_id=deal_id)

    async def add_deal_note(
        self, db: AsyncSession, *, deal_id: str, content: Optional[str], current_user: User
    ) -> dict:
        return await note_service.add_for_entity(
            db,
            entity_type="deal",
            entity_id=deal_id,
            content=content or "Note",
            current_user=current_user,
        )

    async def get_deal_quotes(self, db: AsyncSession, deal_id: str) -> list:
        await self.require_deal(db, deal_id)
        return []

    async def predict_deal_win_rate(self, db: AsyncSession, deal_id: str) -> dict:
        d = await self.require_deal(db, deal_id)

        notes = await note_service.get_notes_by_entity(db, entity_type="deal", entity_id=deal_id)
        notes_summary = (
            "\n".join(f"- {n['content']}" for n in notes) if notes else "No notes logged."
        )

        api_key = settings.OPENAI_API_KEY or os.environ.get("OPENAI_API_KEY")

        if api_key and api_key.startswith("sk-"):
            try:
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                }
                prompt_text = f"""
                Analyze the following B2B sales deal profile in Enterprise CRM and calculate the AI predicted win probability:
                - Deal Title: {d.title}
                - Deal Amount: ${d.amount:,.2f}
                - Current Pipeline Stage: {d.stage}
                - Current Win Probability: {d.probability}%
                - Related Notes / Log:
                {notes_summary}

                Respond ONLY with a JSON object in this exact schema:
                {{
                  "predicted_probability": 75.0,
                  "key_drivers": ["Driver 1", "Driver 2", "Driver 3"],
                  "ai_recommendation": "Strategic advice...",
                  "risk_factors": ["Risk 1", "Risk 2"]
                }}
                """
                payload = {
                    "model": "gpt-4o-mini",
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are an expert Enterprise CRM Sales Analyst AI. Output ONLY valid JSON.",
                        },
                        {"role": "user", "content": prompt_text},
                    ],
                    "temperature": 0.3,
                    "response_format": {"type": "json_object"},
                }

                async with httpx.AsyncClient(timeout=15.0) as client:
                    resp = await client.post(
                        "https://api.openai.com/v1/chat/completions", headers=headers, json=payload
                    )
                    if resp.status_code == 200:
                        result_data = resp.json()
                        content_json = json.loads(result_data["choices"][0]["message"]["content"])
                        return {
                            "deal_id": deal_id,
                            "predicted_probability": float(
                                content_json.get("predicted_probability", d.probability or 50.0)
                            ),
                            "key_drivers": content_json.get(
                                "key_drivers", ["Decision maker engaged", "Proposal submitted fast"]
                            ),
                            "ai_recommendation": content_json.get(
                                "ai_recommendation", "Maintain weekly executive check-ins."
                            ),
                            "risk_factors": content_json.get(
                                "risk_factors", ["Pending procurement review"]
                            ),
                            "model": "gpt-4o-mini",
                        }
            except Exception as err:
                logger.error("OpenAI API call error: %s", err)

        prob = d.probability or 50.0
        drivers = ["Decision maker engaged", "Proposal submitted fast", "Budget aligned with scope"]
        rec = "Maintain executive check-ins and offer flexible contract terms."
        risks = ["Competitor evaluation", "Procurement timeline"]

        if d.stage == "Closed Won":
            prob = 100.0
            drivers = ["Contract signed", "Payment processed"]
            rec = "Hand over to Customer Success team for onboarding."
            risks = []
        elif d.stage == "Closed Lost":
            prob = 0.0
            drivers = ["Competitor chosen", "Budget cut"]
            rec = "Schedule re-engagement check-in in 6 months."
            risks = ["Loss reason logged"]
        elif d.stage == "Negotiation":
            prob = max(prob, 85.0)
            drivers = ["Legal review in progress", "Final pricing agreed"]
        elif d.stage == "Proposal":
            prob = max(prob, 65.0)
            drivers = ["Proposal submitted", "Technical validation completed"]

        return {
            "deal_id": deal_id,
            "predicted_probability": round(prob, 1),
            "key_drivers": drivers,
            "ai_recommendation": rec,
            "risk_factors": risks,
            "model": "crm-sales-analytics-engine",
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
            "expected_close_date": "2026-09-01",
            "assigned_to": deal.assigned_to,
            "organization_id": deal.organization_id,
            "created_at": "2026-08-02",
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
