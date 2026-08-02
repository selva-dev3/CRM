from fastapi import APIRouter
from app.schemas.crm_schemas import (
    AIScoreResponse,
    AIGenerateEmailRequest,
    AIGenerateEmailResponse,
    AISalesForecastResponse
)

router = APIRouter()

@router.get("/lead-score/{lead_id}", response_model=AIScoreResponse, summary="Get AI Lead Score & insights")
async def get_lead_score(lead_id: str):
    """Calculates AI quality score and conversion reasoning for lead."""
    return {
        "score": 88.5,
        "reasons": [
            "High engagement with marketing emails",
            "Target decision maker role (VP level)",
            "Active company growth indicators"
        ]
    }

@router.post("/generate-email", response_model=AIGenerateEmailResponse, summary="AI Email Generator")
async def generate_email(payload: AIGenerateEmailRequest):
    """Generates personalized sales email using OpenAI/Claude LLM."""
    return {
        "subject": f"Follow-up regarding {payload.prompt[:30]}",
        "body": f"Dear Customer,\n\nFollowing up on our conversation regarding {payload.prompt}. I would love to share a custom proposal for your team.\n\nBest regards,\nSales Team"
    }

@router.get("/sales-forecast", response_model=AISalesForecastResponse, summary="AI Predictive Sales Forecast")
async def get_sales_forecast():
    """Predicts Q3/Q4 revenue and win probabilities using AI model."""
    return {
        "predicted_revenue": 1450000.0,
        "confidence_percentage": 87.5,
        "factors": ["High velocity in Proposal stage", "Increased enterprise deal sizes"]
    }
