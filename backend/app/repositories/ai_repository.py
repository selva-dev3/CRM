from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    ActivityLog,
    AIAction,
    AIConversation,
    AIGeneratedContent,
    AILeadScore,
    AIOrganizationConfig,
    AIPrompt,
    AIRun,
    AITranscript,
    CallLog,
    Company,
    Contact,
    Deal,
    DealActivity,
    DealProduct,
    Lead,
    Meeting,
    OrganizationSubscription,
    SystemSetting,
    Task,
    User,
)


class AIRepository:
    """Tenant-scoped query and persistence layer for AI features."""

    async def get_lead(
        self, db: AsyncSession, *, lead_id: str, organization_id: str
    ) -> Lead | None:
        result = await db.execute(
            select(Lead).where(
                Lead.id == lead_id,
                Lead.organization_id == organization_id,
            )
        )
        return result.scalars().first()

    async def list_leads(
        self, db: AsyncSession, *, organization_id: str, limit: int = 500
    ) -> Sequence[Lead]:
        result = await db.execute(
            select(Lead)
            .where(Lead.organization_id == organization_id)
            .order_by(Lead.created_at.desc())
            .limit(limit)
        )
        return result.scalars().all()

    async def get_deal(
        self, db: AsyncSession, *, deal_id: str, organization_id: str
    ) -> Deal | None:
        result = await db.execute(
            select(Deal).where(
                Deal.id == deal_id,
                Deal.organization_id == organization_id,
            )
        )
        return result.scalars().first()

    async def get_company(
        self, db: AsyncSession, *, company_id: str, organization_id: str
    ) -> Company | None:
        result = await db.execute(
            select(Company).where(
                Company.id == company_id,
                Company.organization_id == organization_id,
            )
        )
        return result.scalars().first()

    async def get_contact(
        self, db: AsyncSession, *, contact_id: str, organization_id: str
    ) -> Contact | None:
        result = await db.execute(
            select(Contact).where(
                Contact.id == contact_id,
                Contact.organization_id == organization_id,
            )
        )
        return result.scalars().first()

    async def get_deal_signals(
        self, db: AsyncSession, *, deal_id: str, organization_id: str
    ) -> dict[str, object]:
        activities = (
            (
                await db.execute(
                    select(DealActivity)
                    .join(Deal, Deal.id == DealActivity.deal_id)
                    .where(
                        DealActivity.deal_id == deal_id,
                        Deal.organization_id == organization_id,
                    )
                    .order_by(DealActivity.timestamp.desc())
                    .limit(20)
                )
            )
            .scalars()
            .all()
        )
        return {
            "recent_activities": [
                {"action": item.action, "timestamp": item.timestamp} for item in activities
            ]
        }

    async def get_pricing_signals(
        self, db: AsyncSession, *, deal_id: str, organization_id: str
    ) -> dict[str, object]:
        products = (
            (
                await db.execute(
                    select(DealProduct)
                    .join(Deal, Deal.id == DealProduct.deal_id)
                    .where(
                        DealProduct.deal_id == deal_id,
                        Deal.organization_id == organization_id,
                    )
                )
            )
            .scalars()
            .all()
        )
        history = await db.execute(
            select(
                func.avg(Deal.amount).filter(Deal.stage == "Closed Won"),
                func.avg(Deal.amount).filter(Deal.stage == "Closed Lost"),
                func.count(Deal.id).filter(Deal.stage == "Closed Won"),
                func.count(Deal.id).filter(Deal.stage == "Closed Lost"),
            ).where(Deal.organization_id == organization_id)
        )
        won_average, lost_average, won_count, lost_count = history.one()
        return {
            "products": [
                {
                    "product_id": item.product_id,
                    "quantity": item.quantity,
                    "unit_price": item.unit_price,
                }
                for item in products
            ],
            "historical_outcomes": {
                "won_average_amount": float(won_average) if won_average is not None else None,
                "lost_average_amount": float(lost_average) if lost_average is not None else None,
                "won_count": int(won_count),
                "lost_count": int(lost_count),
            },
            "margin_data_available": False,
        }

    async def get_meeting(
        self, db: AsyncSession, *, meeting_id: str, organization_id: str
    ) -> Meeting | None:
        result = await db.execute(
            select(Meeting).where(
                Meeting.id == meeting_id,
                Meeting.organization_id == organization_id,
            )
        )
        return result.scalars().first()

    async def get_call(
        self, db: AsyncSession, *, call_id: str, organization_id: str
    ) -> CallLog | None:
        result = await db.execute(
            select(CallLog).where(
                CallLog.id == call_id,
                CallLog.organization_id == organization_id,
            )
        )
        return result.scalars().first()

    async def get_user(
        self, db: AsyncSession, *, user_id: str, organization_id: str
    ) -> User | None:
        result = await db.execute(
            select(User).where(
                User.id == user_id,
                User.organization_id == organization_id,
            )
        )
        return result.scalars().first()

    async def get_rep_metrics(
        self, db: AsyncSession, *, user_id: str, organization_id: str
    ) -> dict[str, object]:
        result = await db.execute(
            select(
                func.count(Deal.id),
                func.count(Deal.id).filter(Deal.stage == "Closed Won"),
                func.count(Deal.id).filter(Deal.stage == "Closed Lost"),
                func.coalesce(func.sum(Deal.amount).filter(Deal.stage == "Closed Won"), 0.0),
            ).where(
                Deal.organization_id == organization_id,
                Deal.assigned_to == user_id,
            )
        )
        total, won, lost, won_revenue = result.one()
        activity_count = (
            await db.execute(
                select(func.count(ActivityLog.id)).where(
                    ActivityLog.organization_id == organization_id,
                    ActivityLog.user_id == user_id,
                )
            )
        ).scalar_one()
        return {
            "deal_count": int(total),
            "won_count": int(won),
            "lost_count": int(lost),
            "won_revenue": float(won_revenue),
            "activity_count": int(activity_count),
        }

    async def get_lead_assignment_candidates(
        self,
        db: AsyncSession,
        *,
        organization_id: str,
        limit: int = 25,
    ) -> list[dict[str, object]]:
        result = await db.execute(
            select(
                User.id,
                User.name,
                func.count(Deal.id).label("deal_count"),
                func.count(Deal.id).filter(Deal.stage == "Closed Won").label("won_count"),
                func.count(Deal.id)
                .filter(Deal.stage.not_in(("Closed Won", "Closed Lost")))
                .label("open_deal_count"),
            )
            .outerjoin(
                Deal,
                (Deal.assigned_to == User.id) & (Deal.organization_id == organization_id),
            )
            .where(
                User.organization_id == organization_id,
                User.is_active.is_(True),
            )
            .group_by(User.id, User.name)
            .limit(limit)
        )
        return [
            {
                "id": row.id,
                "name": row.name,
                "deal_count": int(row.deal_count),
                "won_count": int(row.won_count),
                "open_deal_count": int(row.open_deal_count),
            }
            for row in result.all()
        ]

    async def list_cleaning_records(
        self,
        db: AsyncSession,
        *,
        organization_id: str,
        entity_type: str,
        limit: int = 500,
    ) -> Sequence[Lead | Contact | Company]:
        model = {"lead": Lead, "contact": Contact, "company": Company}[entity_type]
        result = await db.execute(
            select(model).where(model.organization_id == organization_id).limit(limit)
        )
        return result.scalars().all()

    async def get_customer_context(
        self,
        db: AsyncSession,
        *,
        entity_type: str,
        entity_id: str,
        organization_id: str,
        include_deals: bool,
        include_calls: bool,
    ) -> dict[str, object] | None:
        if entity_type == "company":
            entity = await self.get_company(
                db, company_id=entity_id, organization_id=organization_id
            )
            company_id = entity_id
        else:
            result = await db.execute(
                select(Contact).where(
                    Contact.id == entity_id,
                    Contact.organization_id == organization_id,
                )
            )
            entity = result.scalars().first()
            company_id = entity.company_id if entity else None
        if not entity:
            return None
        context: dict[str, object] = {
            "entity": {
                "id": entity.id,
                "name": entity.name,
                "updated_at": entity.updated_at,
            }
        }
        if include_deals and company_id:
            deals = (
                (
                    await db.execute(
                        select(Deal)
                        .where(
                            Deal.organization_id == organization_id,
                            Deal.company_id == company_id,
                        )
                        .order_by(Deal.updated_at.desc())
                        .limit(20)
                    )
                )
                .scalars()
                .all()
            )
            context["deals"] = [
                {
                    "id": deal.id,
                    "title": deal.title,
                    "amount": deal.amount,
                    "stage": deal.stage,
                    "updated_at": deal.updated_at,
                }
                for deal in deals
            ]
        if include_calls:
            contact_ids = select(Contact.id).where(
                Contact.organization_id == organization_id,
                (
                    Contact.id == entity_id
                    if entity_type == "contact"
                    else Contact.company_id == company_id
                ),
            )
            calls = (
                (
                    await db.execute(
                        select(CallLog)
                        .where(
                            CallLog.organization_id == organization_id,
                            CallLog.contact_id.in_(contact_ids),
                        )
                        .order_by(CallLog.timestamp.desc())
                        .limit(20)
                    )
                )
                .scalars()
                .all()
            )
            context["calls"] = [
                {
                    "id": call.id,
                    "type": call.call_type,
                    "disposition": call.disposition,
                    "notes": call.notes,
                    "timestamp": call.timestamp,
                }
                for call in calls
            ]
        return context

    async def get_conversation(
        self,
        db: AsyncSession,
        *,
        conversation_id: str,
        organization_id: str,
        user_id: str,
    ) -> AIConversation | None:
        result = await db.execute(
            select(AIConversation).where(
                AIConversation.id == conversation_id,
                AIConversation.organization_id == organization_id,
                AIConversation.user_id == user_id,
            )
        )
        return result.scalars().first()

    async def create_action(
        self,
        db: AsyncSession,
        *,
        run_id: str,
        organization_id: str,
        user_id: str,
        action_type: str,
        title: str,
        payload_json: str,
        expires_at: datetime,
    ) -> AIAction:
        action = AIAction(
            run_id=run_id,
            organization_id=organization_id,
            user_id=user_id,
            action_type=action_type,
            title=title,
            payload_json=payload_json,
            expires_at=expires_at,
        )
        db.add(action)
        await db.flush()
        return action

    async def get_pending_action(
        self,
        db: AsyncSession,
        *,
        action_id: str,
        organization_id: str,
        user_id: str,
    ) -> AIAction | None:
        result = await db.execute(
            select(AIAction)
            .where(
                AIAction.id == action_id,
                AIAction.organization_id == organization_id,
                AIAction.user_id == user_id,
                AIAction.status == "pending",
            )
            .with_for_update()
        )
        return result.scalars().first()

    async def create_transcript(self, db: AsyncSession, **data: object) -> AITranscript:
        transcript = AITranscript(**data)
        db.add(transcript)
        await db.flush()
        return transcript

    async def search_transcripts(
        self,
        db: AsyncSession,
        *,
        organization_id: str,
        query: str,
        allowed_source_types: set[str],
        allow_unlinked: bool,
        limit: int = 20,
    ) -> Sequence[AITranscript]:
        statement = select(AITranscript).where(
            AITranscript.organization_id == organization_id,
            AITranscript.transcript_text.ilike(f"%{query.strip()}%"),
        )
        source_conditions = []
        if allow_unlinked:
            source_conditions.append(AITranscript.source_type.is_(None))
        if allowed_source_types:
            source_conditions.append(AITranscript.source_type.in_(allowed_source_types))
        if not source_conditions:
            return []
        statement = statement.where(or_(*source_conditions))
        result = await db.execute(statement.order_by(AITranscript.created_at.desc()).limit(limit))
        return result.scalars().all()

    async def get_global_feature_setting(self, db: AsyncSession) -> SystemSetting | None:
        result = await db.execute(
            select(SystemSetting).where(SystemSetting.key == "ai_features_enabled")
        )
        return result.scalars().first()

    async def get_organization_config(
        self, db: AsyncSession, organization_id: str
    ) -> AIOrganizationConfig | None:
        return await db.get(AIOrganizationConfig, organization_id)

    async def set_organization_model(
        self,
        db: AsyncSession,
        *,
        organization_id: str,
        provider: str,
        model_name: str,
    ) -> AIOrganizationConfig:
        config = await db.get(AIOrganizationConfig, organization_id)
        if not config:
            config = AIOrganizationConfig(organization_id=organization_id)
            db.add(config)
        config.provider = provider
        config.model_name = model_name
        await db.flush()
        return config

    async def update_organization_config(
        self,
        db: AsyncSession,
        *,
        organization_id: str,
        enabled: bool | None,
        monthly_cost_limit_usd: float | None,
        icp_profile_json: str | None,
        update_icp_profile: bool,
    ) -> AIOrganizationConfig:
        config = await db.get(AIOrganizationConfig, organization_id)
        if not config:
            config = AIOrganizationConfig(organization_id=organization_id)
            db.add(config)
        if enabled is not None:
            config.enabled = enabled
        if monthly_cost_limit_usd is not None:
            config.monthly_cost_limit_usd = monthly_cost_limit_usd
        if update_icp_profile:
            config.icp_profile_json = icp_profile_json
        await db.flush()
        return config

    async def get_subscription_for_update(
        self, db: AsyncSession, organization_id: str
    ) -> OrganizationSubscription | None:
        result = await db.execute(
            select(OrganizationSubscription)
            .where(OrganizationSubscription.organization_id == organization_id)
            .with_for_update()
        )
        return result.scalars().first()

    async def monthly_cost(self, db: AsyncSession, organization_id: str) -> float:
        now = datetime.now(UTC)
        month_start = datetime(now.year, now.month, 1, tzinfo=UTC)
        result = await db.execute(
            select(func.coalesce(func.sum(AIRun.estimated_cost_usd), 0.0)).where(
                AIRun.organization_id == organization_id,
                AIRun.status == "succeeded",
                AIRun.created_at >= month_start,
            )
        )
        return float(result.scalar_one())

    async def recent_run_count(
        self, db: AsyncSession, organization_id: str, since: datetime
    ) -> int:
        result = await db.execute(
            select(func.count(AIRun.id)).where(
                AIRun.organization_id == organization_id,
                AIRun.created_at >= since,
            )
        )
        return int(result.scalar_one())

    async def create_run(self, db: AsyncSession, **data: object) -> AIRun:
        run = AIRun(**data)
        db.add(run)
        await db.flush()
        return run

    async def usage_totals(self, db: AsyncSession, organization_id: str) -> dict[str, float | int]:
        now = datetime.now(UTC)
        month_start = datetime(now.year, now.month, 1, tzinfo=UTC)
        result = await db.execute(
            select(
                func.coalesce(func.sum(AIRun.total_tokens), 0),
                func.coalesce(func.sum(AIRun.estimated_cost_usd), 0.0),
                func.count(AIRun.id),
            ).where(
                AIRun.organization_id == organization_id,
                AIRun.created_at >= month_start,
            )
        )
        tokens, cost, request_count = result.one()
        return {
            "tokens_used_this_month": int(tokens),
            "estimated_cost_usd": float(cost),
            "request_count": int(request_count),
        }

    async def save_lead_score(
        self,
        db: AsyncSession,
        *,
        lead: Lead,
        score: float,
        confidence: float,
        reasons_json: str,
    ) -> AILeadScore:
        lead.score = score
        record = AILeadScore(
            lead_id=lead.id,
            score=score,
            confidence=confidence,
            reasons_json=reasons_json,
        )
        db.add(record)
        return record

    async def create_generated_content(
        self,
        db: AsyncSession,
        *,
        organization_id: str,
        user_id: str,
        content_type: str,
        generated_text: str,
    ) -> AIGeneratedContent:
        content = AIGeneratedContent(
            organization_id=organization_id,
            user_id=user_id,
            content_type=content_type,
            generated_text=generated_text,
        )
        db.add(content)
        return content

    async def get_latest_generated_content(
        self,
        db: AsyncSession,
        *,
        organization_id: str,
        content_type: str,
    ) -> AIGeneratedContent | None:
        result = await db.execute(
            select(AIGeneratedContent)
            .where(
                AIGeneratedContent.organization_id == organization_id,
                AIGeneratedContent.content_type == content_type,
            )
            .order_by(AIGeneratedContent.created_at.desc())
            .limit(1)
        )
        return result.scalars().first()

    async def create_conversation(
        self,
        db: AsyncSession,
        *,
        organization_id: str,
        user_id: str,
        title: str,
        model_name: str,
    ) -> AIConversation:
        conversation = AIConversation(
            organization_id=organization_id,
            user_id=user_id,
            title=title,
            model_name=model_name,
        )
        db.add(conversation)
        await db.flush()
        return conversation

    async def create_prompt(
        self,
        db: AsyncSession,
        *,
        conversation_id: str,
        user_prompt: str,
        ai_response: str,
        tokens_used: int,
    ) -> AIPrompt:
        prompt = AIPrompt(
            conversation_id=conversation_id,
            user_prompt=user_prompt,
            ai_response=ai_response,
            tokens_used=tokens_used,
        )
        db.add(prompt)
        return prompt

    async def search_context(
        self,
        db: AsyncSession,
        *,
        organization_id: str,
        query: str,
        allowed_modules: set[str],
        limit_per_module: int = 5,
    ) -> dict[str, list[dict[str, object]]]:
        pattern = f"%{query.strip()}%"
        context: dict[str, list[dict[str, object]]] = {}

        if "leads" in allowed_modules:
            result = await db.execute(
                select(Lead)
                .where(
                    Lead.organization_id == organization_id,
                    Lead.contact_name.ilike(pattern)
                    | Lead.company.ilike(pattern)
                    | Lead.title.ilike(pattern),
                )
                .limit(limit_per_module)
            )
            context["leads"] = [
                {"id": row.id, "title": row.title, "company": row.company, "status": row.status}
                for row in result.scalars().all()
            ]
        if "contacts" in allowed_modules:
            result = await db.execute(
                select(Contact)
                .where(
                    Contact.organization_id == organization_id,
                    Contact.name.ilike(pattern) | Contact.email.ilike(pattern),
                )
                .limit(limit_per_module)
            )
            context["contacts"] = [
                {"id": row.id, "name": row.name, "email": row.email, "position": row.position}
                for row in result.scalars().all()
            ]
        if "companies" in allowed_modules:
            result = await db.execute(
                select(Company)
                .where(
                    Company.organization_id == organization_id,
                    Company.name.ilike(pattern),
                )
                .limit(limit_per_module)
            )
            context["companies"] = [
                {"id": row.id, "name": row.name, "industry": row.industry}
                for row in result.scalars().all()
            ]
        if "deals" in allowed_modules:
            result = await db.execute(
                select(Deal)
                .where(Deal.organization_id == organization_id, Deal.title.ilike(pattern))
                .limit(limit_per_module)
            )
            context["deals"] = [
                {
                    "id": row.id,
                    "title": row.title,
                    "stage": row.stage,
                    "amount": row.amount,
                    "probability": row.probability,
                }
                for row in result.scalars().all()
            ]
        if "tasks" in allowed_modules:
            result = await db.execute(
                select(Task)
                .where(Task.organization_id == organization_id, Task.title.ilike(pattern))
                .limit(limit_per_module)
            )
            context["tasks"] = [
                {"id": row.id, "title": row.title, "status": row.status, "priority": row.priority}
                for row in result.scalars().all()
            ]
        if "calls" in allowed_modules:
            result = await db.execute(
                select(CallLog)
                .where(CallLog.organization_id == organization_id, CallLog.notes.ilike(pattern))
                .limit(limit_per_module)
            )
            context["calls"] = [
                {"id": row.id, "type": row.call_type, "notes": row.notes}
                for row in result.scalars().all()
            ]
        if "meetings" in allowed_modules:
            result = await db.execute(
                select(Meeting)
                .where(Meeting.organization_id == organization_id, Meeting.title.ilike(pattern))
                .limit(limit_per_module)
            )
            context["meetings"] = [
                {"id": row.id, "title": row.title, "start_time": str(row.start_time)}
                for row in result.scalars().all()
            ]
        return context

    async def execute_search_plan(
        self,
        db: AsyncSession,
        *,
        organization_id: str,
        entity_type: str,
        text_query: str | None,
        status: str | None,
        inactive_days: int | None,
        minimum_open_deal_amount: float | None,
        limit: int,
    ) -> list[dict[str, object]]:
        pattern = f"%{(text_query or '').strip()}%"
        cutoff = datetime.now(UTC) - timedelta(days=inactive_days or 0)

        if entity_type == "company":
            last_call = (
                select(func.max(CallLog.timestamp))
                .join(Contact, Contact.id == CallLog.contact_id)
                .where(
                    Contact.organization_id == organization_id,
                    Contact.company_id == Company.id,
                )
                .correlate(Company)
                .scalar_subquery()
            )
            query = (
                select(
                    Company,
                    func.coalesce(func.sum(Deal.amount), 0.0).label("open_deal_value"),
                    last_call.label("last_contact_at"),
                )
                .outerjoin(
                    Deal,
                    (Deal.company_id == Company.id)
                    & Deal.stage.not_in(("Closed Won", "Closed Lost")),
                )
                .where(Company.organization_id == organization_id)
                .group_by(Company.id)
                .limit(limit)
            )
            if text_query:
                query = query.where(Company.name.ilike(pattern))
            if inactive_days:
                query = query.where(or_(last_call.is_(None), last_call < cutoff))
            if minimum_open_deal_amount is not None:
                query = query.having(
                    func.coalesce(func.sum(Deal.amount), 0.0) >= minimum_open_deal_amount
                )
            rows = (await db.execute(query)).all()
            return [
                {
                    "id": company.id,
                    "name": company.name,
                    "industry": company.industry,
                    "open_deal_value": float(open_deal_value),
                    "last_contact_at": str(last_contact_at) if last_contact_at else None,
                }
                for company, open_deal_value, last_contact_at in rows
            ]

        models = {
            "lead": Lead,
            "contact": Contact,
            "deal": Deal,
            "task": Task,
        }
        model = models[entity_type]
        query = select(model).where(model.organization_id == organization_id)
        searchable = {
            "lead": (Lead.title, Lead.company, Lead.contact_name),
            "contact": (Contact.name, Contact.email),
            "deal": (Deal.title,),
            "task": (Task.title,),
        }
        if text_query:
            conditions = [column.ilike(pattern) for column in searchable[entity_type]]
            query = query.where(or_(*conditions))
        if status and hasattr(model, "status"):
            query = query.where(model.status == status)
        if inactive_days and hasattr(model, "updated_at"):
            query = query.where(model.updated_at < cutoff)
        if entity_type == "deal" and minimum_open_deal_amount is not None:
            query = query.where(
                Deal.amount >= minimum_open_deal_amount,
                Deal.stage.not_in(("Closed Won", "Closed Lost")),
            )
        rows = (await db.execute(query.limit(limit))).scalars().all()
        fields = {
            "lead": ("id", "title", "company", "status", "score", "updated_at"),
            "contact": ("id", "name", "position", "company_id", "updated_at"),
            "deal": ("id", "title", "amount", "stage", "probability", "updated_at"),
            "task": ("id", "title", "status", "priority", "due_date", "updated_at"),
        }
        return [
            {
                field: str(value) if isinstance(value, datetime) else value
                for field in fields[entity_type]
                if (value := getattr(row, field, None)) is not None
            }
            for row in rows
        ]
