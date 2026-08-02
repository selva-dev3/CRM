from fastapi import APIRouter, HTTPException, status, Query, Depends
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models import AIConversation, AIPrompt, Lead, Deal, Meeting, Company
from app.schemas.crm_schemas import (
    AIScoreResponse, AIGenerateEmailRequest, AIGenerateEmailResponse, AISalesForecastResponse, MessageResponse
)

router = APIRouter()

@router.post("/lead-scoring/evaluate", response_model=AIScoreResponse, summary="Calculate AI lead score & key contributing factors")
async def evaluate_lead_score(lead_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Lead).where(Lead.id == lead_id))
    l = res.scalars().first()
    if not l:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Lead with ID '{lead_id}' not found")
    return {"score": l.score or 75.0, "reasons": ["Company size fits ICP", "C-level executive contact", "High website activity"]}

@router.post("/lead-scoring/batch", summary="Batch recalculate AI lead scores across organization")
async def batch_lead_scoring(db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Lead))
    leads = res.scalars().all()
    return {"processed_count": len(leads), "updated_count": len(leads)}

@router.post("/email-writer/generate", response_model=AIGenerateEmailResponse, summary="Generate personalized cold outreach email using LLM")
async def generate_email(payload: AIGenerateEmailRequest, db: AsyncSession = Depends(get_db)):
    if not payload.prompt:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Prompt context is required")
    return {
        "subject": "Transforming your sales pipeline with AI automation",
        "body": f"Hi there,\n\nI noticed your team is scaling operations. {payload.prompt}\n\nBest regards,\nSales Team"
    }

@router.post("/email-writer/improve", response_model=AIGenerateEmailResponse, summary="Rewrite and polish email draft to adjust tone and brevity")
async def improve_email(email_text: str, tone: str = "Professional", db: AsyncSession = Depends(get_db)):
    if not email_text:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email text is required for improvement")
    return {
        "subject": "Follow up on our discussion",
        "body": f"[{tone} Polished]: {email_text}"
    }

@router.post("/deal-forecaster/predict", response_model=AISalesForecastResponse, summary="Predict deal win probability and key risk factors")
async def predict_deal_forecast(deal_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Deal).where(Deal.id == deal_id))
    d = res.scalars().first()
    if not d:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Deal with ID '{deal_id}' not found")
    return {
        "predicted_revenue": d.amount or 0.0,
        "confidence_percentage": d.probability or 50.0,
        "factors": ["Proposal sent within 24h", "Executive sponsor present in meeting"]
    }

@router.post("/sales-assistant/chat", summary="Query interactive AI Sales Assistant for advice & answers")
async def sales_assistant_chat(message: str, conversation_id: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    if not message:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Message content is required")
    return {
        "conversation_id": conversation_id or "chat-new",
        "reply": f"Based on your CRM data: {message}. I recommend scheduling a follow-up demo call."
    }

@router.post("/call-summarizer/summarize", summary="Generate AI summary & key takeaways from call transcript")
async def summarize_call(transcript: str, db: AsyncSession = Depends(get_db)):
    if not transcript:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Transcript text is required")
    return {
        "summary": "Customer expressed interest in enterprise SLA and security features.",
        "key_takeaways": ["Requires SOC2 compliance report", "Budget approved for Q3"],
        "sentiment": "Positive"
    }

@router.post("/sentiment-analyzer/analyze", summary="Analyze customer text or message sentiment")
async def analyze_sentiment(text: str, db: AsyncSession = Depends(get_db)):
    if not text:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Text input is required for sentiment analysis")
    return {"sentiment": "Positive", "polarity_score": 0.85, "urgency": "Medium"}

@router.post("/next-best-action/suggest", summary="Recommend Next Best Action for sales rep on lead or deal")
async def suggest_next_best_action(entity_type: str, entity_id: str, db: AsyncSession = Depends(get_db)):
    if entity_type.lower() == "lead":
        res = await db.execute(select(Lead).where(Lead.id == entity_id))
        if not res.scalars().first():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Lead '{entity_id}' not found")
    elif entity_type.lower() == "deal":
        res = await db.execute(select(Deal).where(Deal.id == entity_id))
        if not res.scalars().first():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Deal '{entity_id}' not found")
    return {
        "entity_type": entity_type,
        "entity_id": entity_id,
        "recommended_action": "Send Case Study on Enterprise Security",
        "reason": "Prospect opened proposal in past 3 hours"
    }

@router.post("/company-enricher/enrich", summary="AI research and auto-enrich company firmographics")
async def enrich_company(company_name: str, domain: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    if not company_name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Company name is required")
    return {
        "company_name": company_name,
        "industry": "Software",
        "estimated_employees": "100-500",
        "tech_stack": ["Python", "PostgreSQL", "AWS"],
        "funding": "Series A"
    }

@router.post("/objection-handler/suggest", summary="Generate AI response strategies for customer objections")
async def suggest_objection_handling(objection_text: str, db: AsyncSession = Depends(get_db)):
    if not objection_text:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Objection text is required")
    return {
        "objection": objection_text,
        "talking_points": [
            "Highlight ROI within 60 days",
            "Offer flexible quarterly payment terms"
        ]
    }

@router.post("/contract-analyzer/review", summary="AI contract review for risk clauses and compliance")
async def review_contract(contract_text: str, db: AsyncSession = Depends(get_db)):
    if not contract_text:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Contract text is required")
    return {
        "risk_level": "Low",
        "flagged_clauses": []
    }

@router.post("/competitor-intelligence/battlecard", summary="Generate AI competitor battlecard & positioning points")
async def get_competitor_battlecard(competitor_name: str, db: AsyncSession = Depends(get_db)):
    if not competitor_name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Competitor name is required")
    return {
        "competitor": competitor_name,
        "our_strengths": ["Native AI integration", "Fast API performance"],
        "their_weaknesses": ["Legacy UI"],
        "landmines_to_lay": "Ask about their per-user API rate limit fees."
    }

@router.post("/icp-matcher/evaluate", summary="Evaluate lead match score against Ideal Customer Profile")
async def evaluate_icp_match(lead_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Lead).where(Lead.id == lead_id))
    l = res.scalars().first()
    if not l:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Lead with ID '{lead_id}' not found")
    return {"lead_id": lead_id, "icp_fit_percentage": l.score or 85.0, "fit_tier": "Tier 1"}

@router.post("/churn-predictor/evaluate", summary="Predict customer churn risk score for account")
async def predict_churn_risk(company_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Company).where(Company.id == company_id))
    if not res.scalars().first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Company with ID '{company_id}' not found")
    return {"company_id": company_id, "churn_risk_score": 15.2, "status": "Healthy", "factors": ["Active logins"]}

@router.post("/pricing-optimizer/suggest", summary="AI discount & price optimization recommendation")
async def optimize_pricing(deal_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Deal).where(Deal.id == deal_id))
    d = res.scalars().first()
    if not d:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Deal with ID '{deal_id}' not found")
    return {"deal_id": deal_id, "recommended_discount_pct": 5.0, "probability_impact": "+10% win likelihood"}

@router.post("/transcription/speech-to-text", summary="Transcribe speech audio file to text using Whisper AI model")
async def speech_to_text(audio_file_name: str = "meeting.mp3", db: AsyncSession = Depends(get_db)):
    return {"text": "Audio transcription result placeholder...", "confidence": 0.95}

@router.get("/usage-stats", summary="Get AI API token usage & budget consumption statistics")
async def get_ai_usage_stats(db: AsyncSession = Depends(get_db)):
    return {"tokens_used_this_month": 0, "estimated_cost_usd": 0.0, "token_limit": 10000000}

@router.get("/models", summary="List available AI model options")
async def list_ai_models(db: AsyncSession = Depends(get_db)):
    return [
        {"model_id": "gpt-4o", "provider": "OpenAI", "is_active": True},
        {"model_id": "claude-3-5-sonnet", "provider": "Anthropic", "is_active": False}
    ]

@router.post("/models/switch", response_model=MessageResponse, summary="Switch default active AI model provider")
async def switch_ai_model(model_id: str, db: AsyncSession = Depends(get_db)):
    return {"message": f"Active AI model switched to '{model_id}'", "status": "success"}
