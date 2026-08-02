from fastapi import APIRouter, HTTPException, status, Query
from typing import List, Optional
from app.schemas.crm_schemas import CallLogResponse, CallLogBase, MessageResponse, BulkDeleteRequest, BulkActionResponse

router = APIRouter()

@router.get("", response_model=List[CallLogResponse], summary="List all call logs")
async def list_calls(page: int = 1, limit: int = 20):
    return [
        {"id": "cl-1", "contact_id": "cnt-1", "call_type": "Outbound", "duration_seconds": 320, "notes": "Discussed feature roadmap", "timestamp": "2026-08-02T11:30:00Z"},
        {"id": "cl-2", "contact_id": "cnt-2", "call_type": "Inbound", "duration_seconds": 140, "notes": "Inquired about enterprise SLA", "timestamp": "2026-08-02T09:15:00Z"}
    ]

@router.post("", response_model=CallLogResponse, status_code=status.HTTP_201_CREATED, summary="Log a new call manually")
async def log_call(payload: CallLogBase):
    return {"id": "cl-3", "contact_id": payload.contact_id, "call_type": payload.call_type, "duration_seconds": payload.duration_seconds, "notes": payload.notes, "timestamp": "2026-08-02T15:00:00Z"}

@router.post("/trigger-outbound", summary="Trigger click-to-dial call via Twilio/telephony")
async def trigger_outbound_call(phone_number: str, contact_id: str):
    return {"call_sid": "CA1234567890", "status": "initiating", "to": phone_number}

@router.get("/dispositions", summary="Get call disposition outcome tags")
async def get_call_dispositions():
    return ["Connected", "Left Voicemail", "No Answer", "Busy", "Wrong Number", "Scheduled Meeting"]

@router.post("/dispositions", response_model=MessageResponse, summary="Create call disposition outcome tag")
async def create_call_disposition(name: str):
    return {"message": f"Disposition '{name}' created", "status": "success"}

@router.get("/stats/rep-performance", summary="Get telephony statistics per sales rep")
async def get_call_stats():
    return [{"user_id": "usr-1", "total_calls": 45, "total_duration_mins": 185.0, "avg_duration_secs": 246}]

@router.post("/voicemail", response_model=MessageResponse, summary="Log voicemail drop execution")
async def log_voicemail_drop(contact_id: str, voicemail_template_id: str):
    return {"message": f"Voicemail template {voicemail_template_id} sent to {contact_id}", "status": "success"}

@router.post("/bulk-delete", response_model=BulkActionResponse, summary="Bulk delete call logs")
async def bulk_delete_calls(payload: BulkDeleteRequest):
    return {"affected_count": len(payload.ids), "message": "Call logs deleted successfully"}

@router.get("/{call_id}", response_model=CallLogResponse, summary="Get call log details by ID")
async def get_call(call_id: str):
    return {"id": call_id, "contact_id": "cnt-1", "call_type": "Outbound", "duration_seconds": 320, "notes": "Discussed feature roadmap", "timestamp": "2026-08-02T11:30:00Z"}

@router.delete("/{call_id}", response_model=MessageResponse, summary="Delete call log by ID")
async def delete_call(call_id: str):
    return {"message": f"Call log {call_id} deleted", "status": "success"}

@router.get("/{call_id}/recording", summary="Get audio recording URL for call")
async def get_call_recording(call_id: str):
    return {"call_id": call_id, "recording_url": f"https://api.crm.com/recordings/{call_id}.mp3", "duration_seconds": 320}

@router.get("/{call_id}/sentiment", summary="Get AI voice sentiment analysis & emotion score")
async def get_call_sentiment(call_id: str):
    return {"call_id": call_id, "overall_sentiment": "Positive", "confidence_score": 0.89, "customer_interest": "High"}
