from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import require_permission
from app.db.session import get_db
from app.schemas.crm_schemas import (
    AIGenerateEmailRequest,
    AIGenerateEmailResponse,
    AISalesForecastResponse,
    AIScoreResponse,
    MessageResponse,
)
from app.services.ai_domain_service import ai_domain_service

router = APIRouter()


@router.post(
    "/lead-scoring/evaluate",
    response_model=AIScoreResponse,
    summary="Calculate AI lead score & key contributing factors",
    dependencies=[Depends(require_permission("ai:generate"))],
)
async def evaluate_lead_score(lead_id: str, db: AsyncSession = Depends(get_db)):
    return await ai_domain_service.evaluate_lead_score(db, lead_id)


@router.post("/lead-scoring/batch", summary="Batch recalculate AI lead scores across organization", dependencies=[Depends(require_permission("ai:generate"))])
async def batch_lead_scoring(db: AsyncSession = Depends(get_db)):
    return await ai_domain_service.batch_lead_scoring(db)


@router.post(
    "/email-writer/generate",
    response_model=AIGenerateEmailResponse,
    summary="Generate personalized cold outreach email using LLM",
    dependencies=[Depends(require_permission("ai:generate"))],
)
async def generate_email(payload: AIGenerateEmailRequest, db: AsyncSession = Depends(get_db)):
    return await ai_domain_service.generate_email(payload)


@router.post(
    "/email-writer/improve",
    response_model=AIGenerateEmailResponse,
    summary="Rewrite and polish email draft to adjust tone and brevity",
    dependencies=[Depends(require_permission("ai:generate"))],
)
async def improve_email(email_text: str, tone: str = "Professional", db: AsyncSession = Depends(get_db)):
    return await ai_domain_service.improve_email(email_text, tone)


@router.post(
    "/deal-forecaster/predict",
    response_model=AISalesForecastResponse,
    summary="Predict deal win probability and key risk factors",
    dependencies=[Depends(require_permission("ai:generate"))],
)
async def predict_deal_forecast(deal_id: str, db: AsyncSession = Depends(get_db)):
    return await ai_domain_service.predict_deal_forecast(db, deal_id)


@router.post("/sales-assistant/chat", summary="Query interactive AI Sales Assistant for advice & answers", dependencies=[Depends(require_permission("ai:generate"))])
async def sales_assistant_chat(
    message: str, conversation_id: Optional[str] = None, db: AsyncSession = Depends(get_db)
):
    return await ai_domain_service.sales_assistant_chat(message, conversation_id)


@router.post("/call-summarizer/summarize", summary="Generate AI summary & key takeaways from call transcript", dependencies=[Depends(require_permission("ai:generate"))])
async def summarize_call(transcript: str, db: AsyncSession = Depends(get_db)):
    return await ai_domain_service.summarize_call(transcript)


@router.post("/sentiment-analyzer/analyze", summary="Analyze customer text or message sentiment", dependencies=[Depends(require_permission("ai:generate"))])
async def analyze_sentiment(text: str, db: AsyncSession = Depends(get_db)):
    return await ai_domain_service.analyze_sentiment(text)


@router.post("/next-best-action/suggest", summary="Recommend Next Best Action for sales rep on lead or deal", dependencies=[Depends(require_permission("ai:generate"))])
async def suggest_next_best_action(entity_type: str, entity_id: str, db: AsyncSession = Depends(get_db)):
    return await ai_domain_service.suggest_next_best_action(db, entity_type, entity_id)


@router.post("/company-enricher/enrich", summary="AI research and auto-enrich company firmographics", dependencies=[Depends(require_permission("ai:generate"))])
async def enrich_company(company_name: str, domain: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    return await ai_domain_service.enrich_company(company_name, domain)


@router.post("/objection-handler/suggest", summary="Generate AI response strategies for customer objections", dependencies=[Depends(require_permission("ai:generate"))])
async def suggest_objection_handling(objection_text: str, db: AsyncSession = Depends(get_db)):
    return await ai_domain_service.suggest_objection_handling(objection_text)


@router.post("/contract-analyzer/review", summary="AI contract review for risk clauses and compliance", dependencies=[Depends(require_permission("ai:generate"))])
async def review_contract(contract_text: str, db: AsyncSession = Depends(get_db)):
    return await ai_domain_service.review_contract(contract_text)


@router.post("/competitor-intelligence/battlecard", summary="Generate AI competitor battlecard & positioning points", dependencies=[Depends(require_permission("ai:generate"))])
async def get_competitor_battlecard(competitor_name: str, db: AsyncSession = Depends(get_db)):
    return await ai_domain_service.get_competitor_battlecard(competitor_name)


@router.post("/icp-matcher/evaluate", summary="Evaluate lead match score against Ideal Customer Profile", dependencies=[Depends(require_permission("ai:generate"))])
async def evaluate_icp_match(lead_id: str, db: AsyncSession = Depends(get_db)):
    return await ai_domain_service.evaluate_icp_match(db, lead_id)


@router.post("/churn-predictor/evaluate", summary="Predict customer churn risk score for account", dependencies=[Depends(require_permission("ai:generate"))])
async def predict_churn_risk(company_id: str, db: AsyncSession = Depends(get_db)):
    return await ai_domain_service.predict_churn_risk(db, company_id)


@router.post("/pricing-optimizer/suggest", summary="AI discount & price optimization recommendation", dependencies=[Depends(require_permission("ai:generate"))])
async def optimize_pricing(deal_id: str, db: AsyncSession = Depends(get_db)):
    return await ai_domain_service.optimize_pricing(db, deal_id)


@router.post("/transcription/speech-to-text", summary="Transcribe speech audio file to text using Whisper AI model", dependencies=[Depends(require_permission("ai:generate"))])
async def speech_to_text(audio_file_name: str = "meeting.mp3", db: AsyncSession = Depends(get_db)):
    return await ai_domain_service.speech_to_text(audio_file_name)


@router.get("/usage-stats", summary="Get AI API token usage & budget consumption statistics", dependencies=[Depends(require_permission("ai:read"))])
async def get_ai_usage_stats(db: AsyncSession = Depends(get_db)):
    return await ai_domain_service.get_ai_usage_stats()


@router.get("/models", summary="List available AI model options", dependencies=[Depends(require_permission("ai:read"))])
async def list_ai_models(db: AsyncSession = Depends(get_db)):
    return await ai_domain_service.list_ai_models()


@router.post("/models/switch", response_model=MessageResponse, summary="Switch default active AI model provider", dependencies=[Depends(require_permission("ai:read"))])
async def switch_ai_model(model_id: str, db: AsyncSession = Depends(get_db)):
    return await ai_domain_service.switch_ai_model(model_id)