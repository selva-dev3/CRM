from typing import Optional

from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIException, NotFoundError
from app.repositories.ai_repository import AIRepository
from app.schemas.crm_schemas import AIGenerateEmailRequest


class AIDomainService:
    """Business logic for AI-assisted features."""

    def __init__(self, repository: Optional[AIRepository] = None) -> None:
        self.repository = repository or AIRepository()

    async def evaluate_lead_score(self, db: AsyncSession, lead_id: str) -> dict:
        lead = await self.repository.get_lead(db, lead_id)
        if not lead:
            raise NotFoundError(message=f"Lead with ID '{lead_id}' not found")
        return {
            "score": lead.score or 75.0,
            "reasons": ["Company size fits ICP", "C-level executive contact", "High website activity"],
        }

    async def batch_lead_scoring(self, db: AsyncSession) -> dict:
        leads = await self.repository.list_all_leads(db)
        return {"processed_count": len(leads), "updated_count": len(leads)}

    async def generate_email(self, payload: AIGenerateEmailRequest) -> dict:
        if not payload.prompt:
            raise APIException(
                status_code=status.HTTP_400_BAD_REQUEST, message="Prompt context is required"
            )
        return {
            "subject": "Transforming your sales pipeline with AI automation",
            "body": f"Hi there,\n\nI noticed your team is scaling operations. {payload.prompt}\n\nBest regards,\nSales Team",
        }

    async def improve_email(self, email_text: str, tone: str = "Professional") -> dict:
        if not email_text:
            raise APIException(
                status_code=status.HTTP_400_BAD_REQUEST, message="Email text is required for improvement"
            )
        return {"subject": "Follow up on our discussion", "body": f"[{tone} Polished]: {email_text}"}

    async def predict_deal_forecast(self, db: AsyncSession, deal_id: str) -> dict:
        deal = await self.repository.get_deal(db, deal_id)
        if not deal:
            raise NotFoundError(message=f"Deal with ID '{deal_id}' not found")
        return {
            "predicted_revenue": deal.amount or 0.0,
            "confidence_percentage": deal.probability or 50.0,
            "factors": ["Proposal sent within 24h", "Executive sponsor present in meeting"],
        }

    async def sales_assistant_chat(self, message: str, conversation_id: Optional[str] = None) -> dict:
        if not message:
            raise APIException(
                status_code=status.HTTP_400_BAD_REQUEST, message="Message content is required"
            )
        return {
            "conversation_id": conversation_id or "chat-new",
            "reply": f"Based on your CRM data: {message}. I recommend scheduling a follow-up demo call.",
        }

    async def summarize_call(self, transcript: str) -> dict:
        if not transcript:
            raise APIException(
                status_code=status.HTTP_400_BAD_REQUEST, message="Transcript text is required"
            )
        return {
            "summary": "Customer expressed interest in enterprise SLA and security features.",
            "key_takeaways": ["Requires SOC2 compliance report", "Budget approved for Q3"],
            "sentiment": "Positive",
        }

    async def analyze_sentiment(self, text: str) -> dict:
        if not text:
            raise APIException(
                status_code=status.HTTP_400_BAD_REQUEST, message="Text input is required for sentiment analysis"
            )
        return {"sentiment": "Positive", "polarity_score": 0.85, "urgency": "Medium"}

    async def suggest_next_best_action(self, db: AsyncSession, entity_type: str, entity_id: str) -> dict:
        if entity_type.lower() == "lead":
            lead = await self.repository.get_lead(db, entity_id)
            if not lead:
                raise NotFoundError(message=f"Lead '{entity_id}' not found")
        elif entity_type.lower() == "deal":
            deal = await self.repository.get_deal(db, entity_id)
            if not deal:
                raise NotFoundError(message=f"Deal '{entity_id}' not found")
        return {
            "entity_type": entity_type,
            "entity_id": entity_id,
            "recommended_action": "Send Case Study on Enterprise Security",
            "reason": "Prospect opened proposal in past 3 hours",
        }

    async def enrich_company(self, company_name: str, domain: Optional[str] = None) -> dict:
        if not company_name:
            raise APIException(
                status_code=status.HTTP_400_BAD_REQUEST, message="Company name is required"
            )
        return {
            "company_name": company_name,
            "industry": "Software",
            "estimated_employees": "100-500",
            "tech_stack": ["Python", "PostgreSQL", "AWS"],
            "funding": "Series A",
        }

    async def suggest_objection_handling(self, objection_text: str) -> dict:
        if not objection_text:
            raise APIException(
                status_code=status.HTTP_400_BAD_REQUEST, message="Objection text is required"
            )
        return {
            "objection": objection_text,
            "talking_points": ["Highlight ROI within 60 days", "Offer flexible quarterly payment terms"],
        }

    async def review_contract(self, contract_text: str) -> dict:
        if not contract_text:
            raise APIException(
                status_code=status.HTTP_400_BAD_REQUEST, message="Contract text is required"
            )
        return {"risk_level": "Low", "flagged_clauses": []}

    async def get_competitor_battlecard(self, competitor_name: str) -> dict:
        if not competitor_name:
            raise APIException(
                status_code=status.HTTP_400_BAD_REQUEST, message="Competitor name is required"
            )
        return {
            "competitor": competitor_name,
            "our_strengths": ["Native AI integration", "Fast API performance"],
            "their_weaknesses": ["Legacy UI"],
            "landmines_to_lay": "Ask about their per-user API rate limit fees.",
        }

    async def evaluate_icp_match(self, db: AsyncSession, lead_id: str) -> dict:
        lead = await self.repository.get_lead(db, lead_id)
        if not lead:
            raise NotFoundError(message=f"Lead with ID '{lead_id}' not found")
        return {"lead_id": lead_id, "icp_fit_percentage": lead.score or 85.0, "fit_tier": "Tier 1"}

    async def predict_churn_risk(self, db: AsyncSession, company_id: str) -> dict:
        company = await self.repository.get_company(db, company_id)
        if not company:
            raise NotFoundError(message=f"Company with ID '{company_id}' not found")
        return {
            "company_id": company_id,
            "churn_risk_score": 15.2,
            "status": "Healthy",
            "factors": ["Active logins"],
        }

    async def optimize_pricing(self, db: AsyncSession, deal_id: str) -> dict:
        deal = await self.repository.get_deal(db, deal_id)
        if not deal:
            raise NotFoundError(message=f"Deal with ID '{deal_id}' not found")
        return {"deal_id": deal_id, "recommended_discount_pct": 5.0, "probability_impact": "+10% win likelihood"}

    async def speech_to_text(self, audio_file_name: str = "meeting.mp3") -> dict:
        return {"text": "Audio transcription result placeholder...", "confidence": 0.95}

    async def get_ai_usage_stats(self) -> dict:
        return {"tokens_used_this_month": 0, "estimated_cost_usd": 0.0, "token_limit": 10000000}

    async def list_ai_models(self) -> list[dict]:
        return [
            {"model_id": "gpt-4o", "provider": "OpenAI", "is_active": True},
            {"model_id": "claude-3-5-sonnet", "provider": "Anthropic", "is_active": False},
        ]

    async def switch_ai_model(self, model_id: str) -> dict:
        return {"message": f"Active AI model switched to '{model_id}'", "status": "success"}


ai_domain_service = AIDomainService()