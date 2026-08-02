from fastapi import APIRouter
from app.schemas.ai import (
    EmailGeneratorRequest,
    EmailGeneratorResponse,
    MeetingSummaryRequest,
    MeetingSummaryResponse,
    AIChatRequest,
    AIChatResponse
)
from app.services.ai_service import ai_service

router = APIRouter()

@router.post("/generate-email", response_model=EmailGeneratorResponse)
async def generate_email(payload: EmailGeneratorRequest):
    result = await ai_service.generate_email(payload.prompt, payload.context)
    return result

@router.post("/summarize-meeting", response_model=MeetingSummaryResponse)
async def summarize_meeting(payload: MeetingSummaryRequest):
    result = await ai_service.summarize_meeting(payload.transcript)
    return result

@router.post("/chat", response_model=AIChatResponse)
async def ai_chat(payload: AIChatRequest):
    return {"response": f"AI Assistant received: {payload.message}. How can I assist with your sales pipeline?"}
