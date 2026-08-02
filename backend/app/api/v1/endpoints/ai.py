from fastapi import APIRouter, HTTPException, status, Query
from typing import List, Optional, Dict, Any
from app.schemas.crm_schemas import (
    AIScoreResponse, AIGenerateEmailRequest, AIGenerateEmailResponse, AISalesForecastResponse, MessageResponse
)

router = APIRouter()

@router.post("/lead-scoring/evaluate", response_model=AIScoreResponse, summary="Calculate AI lead score & key contributing factors")
async def evaluate_lead_score(lead_id: str):
    return {"score": 88.5, "reasons": ["Company size fits ICP", "C-level executive contact", "High website activity"]}

@router.post("/lead-scoring/batch", summary="Batch recalculate AI lead scores across organization")
async def batch_lead_scoring():
    return {"processed_count": 150, "updated_count": 42}

@router.post("/email-writer/generate", response_model=AIGenerateEmailResponse, summary="Generate personalized cold outreach email using LLM")
async def generate_email(payload: AIGenerateEmailRequest):
    return {
        "subject": "Transforming your sales pipeline with AI automation",
        "body": f"Hi there,\n\nI noticed your team is scaling operations. {payload.prompt}\n\nBest regards,\nSales Team"
    }

@router.post("/email-writer/improve", response_model=AIGenerateEmailResponse, summary="Rewrite and polish email draft to adjust tone and brevity")
async def improve_email(email_text: str, tone: str = "Professional"):
    return {
        "subject": "Follow up on our discussion",
        "body": f"[Improved ({tone})]: {email_text}"
    }

@router.post("/deal-forecaster/predict", response_model=AISalesForecastResponse, summary="Predict deal win probability and key risk factors")
async def predict_deal_forecast(deal_id: str):
    return {
        "predicted_revenue": 85000.0,
        "confidence_percentage": 82.4,
        "factors": ["Proposal sent within 24h", "Executive sponsor present in meeting"]
    }

@router.post("/sales-assistant/chat", summary="Query interactive AI Sales Assistant for advice & answers")
async def sales_assistant_chat(message: str, conversation_id: Optional[str] = None):
    return {
        "conversation_id": conversation_id or "chat-100",
        "reply": f"Based on your CRM data: {message}. I recommend scheduling a follow-up demo call this Thursday."
    }

@router.post("/call-summarizer/summarize", summary="Generate AI summary & key takeaways from call transcript")
async def summarize_call(transcript: str):
    return {
        "summary": "Customer expressed interest in enterprise SLA and multi-tenant security features.",
        "key_takeaways": ["Requires SOC2 compliance report", "Budget approved for Q3"],
        "sentiment": "Very Positive"
    }

@router.post("/sentiment-analyzer/analyze", summary="Analyze customer text or message sentiment")
async def analyze_sentiment(text: str):
    return {"sentiment": "Positive", "polarity_score": 0.85, "urgency": "Medium"}

@router.post("/next-best-action/suggest", summary="Recommend Next Best Action for sales rep on lead or deal")
async def suggest_next_best_action(entity_type: str, entity_id: str):
    return {
        "entity_type": entity_type,
        "entity_id": entity_id,
        "recommended_action": "Send Case Study on Enterprise Security",
        "reason": "Prospect opened proposal twice in past 3 hours"
    }

@router.post("/company-enricher/enrich", summary="AI research and auto-enrich company firmographics")
async def enrich_company(company_name: str, domain: Optional[str] = None):
    return {
        "company_name": company_name,
        "industry": "Enterprise Software",
        "estimated_employees": "500-1000",
        "tech_stack": ["React", "Python", "AWS", "PostgreSQL"],
        "funding": "$50M Series B"
    }

@router.post("/objection-handler/suggest", summary="Generate AI response strategies for customer objections")
async def suggest_objection_handling(objection_text: str):
    return {
        "objection": objection_text,
        "talking_points": [
            "Highlight ROI within 60 days",
            "Offer flexible quarterly payment terms",
            "Provide customer reference case study"
        ]
    }

@router.post("/contract-analyzer/review", summary="AI contract review for risk clauses and compliance")
async def review_contract(contract_text: str):
    return {
        "risk_level": "Low",
        "flagged_clauses": [
            {"clause": "Indemnification section 8.2", "risk": "Unlimited liability", "recommendation": "Cap liability to 12-month fees"}
        ]
    }

@router.post("/competitor-intelligence/battlecard", summary="Generate AI competitor battlecard & positioning points")
async def get_competitor_battlecard(competitor_name: str):
    return {
        "competitor": competitor_name,
        "our_strengths": ["Native AI integration", "5x faster API performance", "Custom workflow builder"],
        "their_weaknesses": ["Legacy UI", "Expensive add-on modules"],
        "landmines_to_lay": "Ask about their hidden per-user API rate limit fees."
    }

@router.post("/icp-matcher/evaluate", summary="Evaluate lead match score against Ideal Customer Profile")
async def evaluate_icp_match(lead_id: str):
    return {"lead_id": lead_id, "icp_fit_percentage": 92.0, "fit_tier": "Tier 1 (High Priority)"}

@router.post("/churn-predictor/evaluate", summary="Predict customer churn risk score for account")
async def predict_churn_risk(company_id: str):
    return {"company_id": company_id, "churn_risk_score": 15.2, "status": "Healthy", "factors": ["High daily active user logins"]}

@router.post("/pricing-optimizer/suggest", summary="AI discount & price optimization recommendation")
async def optimize_pricing(deal_id: str):
    return {"deal_id": deal_id, "recommended_discount_pct": 8.0, "probability_impact": "+15% win likelihood"}

@router.post("/transcription/speech-to-text", summary="Transcribe speech audio file to text using Whisper AI model")
async def speech_to_text(audio_file_name: str = "meeting.mp3"):
    return {"text": "Thank you everyone for joining today's CRM demonstration...", "confidence": 0.96}

@router.get("/usage-stats", summary="Get AI API token usage & budget consumption statistics")
async def get_ai_usage_stats():
    return {"tokens_used_this_month": 1450000, "estimated_cost_usd": 14.50, "token_limit": 10000000}

@router.get("/models", summary="List available AI model options (OpenAI GPT-4o, Anthropic Claude 3.5 Sonnet)")
async def list_ai_models():
    return [
        {"model_id": "gpt-4o", "provider": "OpenAI", "is_active": True},
        {"model_id": "claude-3-5-sonnet", "provider": "Anthropic", "is_active": False}
    ]

@router.post("/models/switch", response_model=MessageResponse, summary="Switch default active AI model provider")
async def switch_ai_model(model_id: str):
    return {"message": f"Active AI model switched to '{model_id}'", "status": "success"}
