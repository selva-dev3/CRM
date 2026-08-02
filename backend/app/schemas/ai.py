from pydantic import BaseModel
from typing import Optional, Dict, Any, List

class EmailGeneratorRequest(BaseModel):
    prompt: str
    context: Optional[Dict[str, Any]] = None

class EmailGeneratorResponse(BaseModel):
    subject: str
    body: str

class MeetingSummaryRequest(BaseModel):
    transcript: str

class MeetingSummaryResponse(BaseModel):
    summary: str
    action_items: List[str]

class AIChatRequest(BaseModel):
    message: str

class AIChatResponse(BaseModel):
    response: str
