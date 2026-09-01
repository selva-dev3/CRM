from typing import Any

from pydantic import BaseModel


class EmailGeneratorRequest(BaseModel):
    prompt: str
    context: dict[str, Any] | None = None


class EmailGeneratorResponse(BaseModel):
    subject: str
    body: str


class MeetingSummaryRequest(BaseModel):
    transcript: str


class MeetingSummaryResponse(BaseModel):
    summary: str
    action_items: list[str]


class AIChatRequest(BaseModel):
    message: str


class AIChatResponse(BaseModel):
    response: str
