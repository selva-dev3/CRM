from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user, require_permission
from app.core.config import settings
from app.core.errors import APIException
from app.db.session import get_db
from app.models import User
from app.schemas.ai import (
    AIActionConfirmationRequest,
    AIActionExecutionResponse,
    AIChatRequest,
    AIChatResponse,
    AIOrganizationConfigResponse,
    AIOrganizationConfigUpdate,
    AISalesForecastResponse,
    ChurnPredictionResponse,
    CompanyEnrichmentRequest,
    CompanyIntelligenceResponse,
    CompetitorBattlecardResponse,
    CompetitorResearchRequest,
    ContractReviewRequest,
    ContractReviewResponse,
    CRMSearchRequest,
    CRMSearchResponse,
    Customer360Response,
    DataCleaningRequest,
    DataQualityResponse,
    DealIntelligenceResponse,
    EmailGeneratorRequest,
    EmailGeneratorResponse,
    EmailImproveRequest,
    EntityAIRequest,
    FollowUpRecommendationResponse,
    ICPMatchResponse,
    LeadIntelligenceResponse,
    MeetingSummaryRequest,
    MeetingSummaryResponse,
    NextBestActionResponse,
    ObjectionRequest,
    ObjectionResponse,
    PricingRecommendationResponse,
    RepCoachingRequest,
    RepCoachingResponse,
    SentimentAnalysisResponse,
    TextAnalysisRequest,
    TranscriptionResponse,
    TranscriptSearchResponse,
)
from app.schemas.crm_schemas import MessageResponse
from app.services.ai_domain_service import ai_domain_service

router = APIRouter()


@router.get(
    "/configuration",
    response_model=AIOrganizationConfigResponse,
    dependencies=[
        Depends(require_permission("ai:read")),
        Depends(require_permission("settings:read")),
    ],
)
async def get_ai_configuration(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await ai_domain_service.get_organization_config(db, current_user)


@router.put(
    "/configuration",
    response_model=AIOrganizationConfigResponse,
    dependencies=[
        Depends(require_permission("settings:update")),
        Depends(require_permission("settings:security")),
    ],
)
async def update_ai_configuration(
    payload: AIOrganizationConfigUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await ai_domain_service.update_organization_config(db, payload, current_user)


@router.post(
    "/lead-scoring/evaluate",
    response_model=LeadIntelligenceResponse,
    summary="Calculate AI lead score & key contributing factors",
    dependencies=[
        Depends(require_permission("ai:generate")),
        Depends(require_permission("leads:update")),
    ],
)
async def evaluate_lead_score(
    lead_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await ai_domain_service.evaluate_lead_score(db, lead_id, current_user)


@router.post(
    "/lead-scoring/batch",
    summary="Batch recalculate AI lead scores across organization",
    dependencies=[
        Depends(require_permission("ai:generate")),
        Depends(require_permission("leads:update")),
    ],
)
async def batch_lead_scoring(
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    return await ai_domain_service.batch_lead_scoring(db, current_user)


@router.post(
    "/email-writer/generate",
    response_model=EmailGeneratorResponse,
    summary="Generate personalized cold outreach email using LLM",
    dependencies=[
        Depends(require_permission("ai:generate")),
        Depends(require_permission("emails:read")),
    ],
)
async def generate_email(
    payload: EmailGeneratorRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await ai_domain_service.generate_email(db, payload, current_user)


@router.post(
    "/email-writer/improve",
    response_model=EmailGeneratorResponse,
    summary="Rewrite and polish email draft to adjust tone and brevity",
    dependencies=[
        Depends(require_permission("ai:generate")),
        Depends(require_permission("emails:read")),
    ],
)
async def improve_email(
    payload: EmailImproveRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await ai_domain_service.improve_email(db, payload.email_text, payload.tone, current_user)


@router.post(
    "/deal-forecaster/predict",
    response_model=DealIntelligenceResponse,
    summary="Predict deal win probability and key risk factors",
    dependencies=[
        Depends(require_permission("ai:generate")),
        Depends(require_permission("deals:read")),
    ],
)
async def predict_deal_forecast(
    deal_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await ai_domain_service.predict_deal_forecast(db, deal_id, current_user)


@router.post(
    "/sales-assistant/chat",
    response_model=AIChatResponse,
    summary="Query interactive AI Sales Assistant for advice & answers",
    dependencies=[Depends(require_permission("ai:generate"))],
)
async def sales_assistant_chat(
    payload: AIChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await ai_domain_service.sales_assistant_chat(
        db, payload.message, payload.conversation_id, current_user
    )


@router.post(
    "/sales-assistant/actions/confirm",
    response_model=AIActionExecutionResponse,
    summary="Confirm and execute a persisted AI action proposal",
    dependencies=[Depends(require_permission("ai:generate"))],
)
async def confirm_sales_assistant_action(
    payload: AIActionConfirmationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await ai_domain_service.confirm_action(db, payload.proposal_id, current_user)


@router.post(
    "/crm-search/query",
    response_model=CRMSearchResponse,
    summary="Search authorized CRM data using a safe natural-language query plan",
    dependencies=[Depends(require_permission("ai:generate"))],
)
async def search_crm(
    payload: CRMSearchRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await ai_domain_service.search_crm(db, payload.query, payload.scope, current_user)


@router.post(
    "/sales-forecast/predict",
    response_model=AISalesForecastResponse,
    summary="Explain the canonical organization revenue forecast with AI risk analysis",
    dependencies=[
        Depends(require_permission("ai:generate")),
        Depends(require_permission("reports:read")),
        Depends(require_permission("deals:read")),
    ],
)
async def get_sales_forecast(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await ai_domain_service.get_sales_forecast(db, current_user)


@router.post(
    "/sales-coach/analyze",
    response_model=RepCoachingResponse,
    summary="Generate tenant-scoped sales coaching from recorded performance metrics",
    dependencies=[
        Depends(require_permission("ai:generate")),
        Depends(require_permission("users:read")),
        Depends(require_permission("reports:read")),
    ],
)
async def coach_sales_rep(
    payload: RepCoachingRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await ai_domain_service.coach_sales_rep(db, payload.user_id, current_user)


@router.post(
    "/follow-up/recommend",
    response_model=FollowUpRecommendationResponse,
    summary="Recommend an approval-required follow-up for an authorized CRM entity",
    dependencies=[Depends(require_permission("ai:generate"))],
)
async def recommend_follow_up(
    payload: EntityAIRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await ai_domain_service.recommend_follow_up(
        db, payload.entity_type, payload.entity_id, current_user
    )


@router.post(
    "/data-cleaning/analyze",
    response_model=DataQualityResponse,
    summary="Find tenant-scoped duplicate, incomplete, and stale CRM records",
    dependencies=[Depends(require_permission("ai:generate"))],
)
async def analyze_data_quality(
    payload: DataCleaningRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await ai_domain_service.analyze_data_quality(db, payload, current_user)


@router.post(
    "/customer-360/summarize",
    response_model=Customer360Response,
    summary="Generate a tenant- and permission-scoped customer 360 summary",
    dependencies=[Depends(require_permission("ai:generate"))],
)
async def get_customer_360(
    payload: EntityAIRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if payload.entity_type not in {"company", "contact"}:
        raise APIException(
            status_code=400,
            code="AI_ENTITY_UNSUPPORTED",
            message="Customer 360 supports company and contact entities.",
        )
    return await ai_domain_service.get_customer_360(
        db, payload.entity_type, payload.entity_id, current_user
    )


@router.post(
    "/call-summarizer/summarize",
    response_model=MeetingSummaryResponse,
    summary="Generate AI summary & key takeaways from call transcript",
    dependencies=[
        Depends(require_permission("ai:generate")),
        Depends(require_permission("calls:read")),
    ],
)
async def summarize_call(
    payload: MeetingSummaryRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await ai_domain_service.summarize_call(db, payload.transcript, current_user)


@router.post(
    "/sentiment-analyzer/analyze",
    response_model=SentimentAnalysisResponse,
    summary="Analyze customer text or message sentiment",
    dependencies=[Depends(require_permission("ai:generate"))],
)
async def analyze_sentiment(
    payload: TextAnalysisRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await ai_domain_service.analyze_sentiment(db, payload.text, current_user)


@router.post(
    "/next-best-action/suggest",
    response_model=NextBestActionResponse,
    summary="Recommend Next Best Action for sales rep on lead or deal",
    dependencies=[Depends(require_permission("ai:generate"))],
)
async def suggest_next_best_action(
    entity_type: str,
    entity_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await ai_domain_service.suggest_next_best_action(
        db, entity_type, entity_id, current_user
    )


@router.post(
    "/company-enricher/enrich",
    response_model=CompanyIntelligenceResponse,
    summary="AI research and auto-enrich company firmographics",
    dependencies=[
        Depends(require_permission("ai:generate")),
        Depends(require_permission("companies:read")),
    ],
)
async def enrich_company(
    payload: CompanyEnrichmentRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await ai_domain_service.enrich_company(
        db, payload.company_name, payload.domain, current_user
    )


@router.post(
    "/objection-handler/suggest",
    response_model=ObjectionResponse,
    summary="Generate AI response strategies for customer objections",
    dependencies=[Depends(require_permission("ai:generate"))],
)
async def suggest_objection_handling(
    payload: ObjectionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await ai_domain_service.suggest_objection_handling(
        db, payload.objection_text, current_user
    )


@router.post(
    "/contract-analyzer/review",
    response_model=ContractReviewResponse,
    summary="AI contract review for risk clauses and compliance",
    dependencies=[
        Depends(require_permission("ai:generate")),
        Depends(require_permission("documents:read")),
    ],
)
async def review_contract(
    payload: ContractReviewRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await ai_domain_service.review_contract(db, payload.contract_text, current_user)


@router.post(
    "/competitor-intelligence/battlecard",
    response_model=CompetitorBattlecardResponse,
    summary="Generate AI competitor battlecard & positioning points",
    dependencies=[
        Depends(require_permission("ai:generate")),
        Depends(require_permission("companies:read")),
    ],
)
async def get_competitor_battlecard(
    payload: CompetitorResearchRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await ai_domain_service.get_competitor_battlecard(
        db, payload.competitor_name, current_user
    )


@router.post(
    "/icp-matcher/evaluate",
    response_model=ICPMatchResponse,
    summary="Evaluate lead match score against Ideal Customer Profile",
    dependencies=[
        Depends(require_permission("ai:generate")),
        Depends(require_permission("leads:read")),
    ],
)
async def evaluate_icp_match(
    lead_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await ai_domain_service.evaluate_icp_match(db, lead_id, current_user)


@router.post(
    "/churn-predictor/evaluate",
    response_model=ChurnPredictionResponse,
    summary="Predict customer churn risk score for account",
    dependencies=[
        Depends(require_permission("ai:generate")),
        Depends(require_permission("companies:read")),
    ],
)
async def predict_churn_risk(
    company_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await ai_domain_service.predict_churn_risk(db, company_id, current_user)


@router.post(
    "/pricing-optimizer/suggest",
    response_model=PricingRecommendationResponse,
    summary="AI discount & price optimization recommendation",
    dependencies=[
        Depends(require_permission("ai:generate")),
        Depends(require_permission("deals:read")),
    ],
)
async def optimize_pricing(
    deal_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await ai_domain_service.optimize_pricing(db, deal_id, current_user)


@router.post(
    "/transcription/speech-to-text",
    response_model=TranscriptionResponse,
    summary="Transcribe speech audio file to text using Whisper AI model",
    dependencies=[Depends(require_permission("ai:generate"))],
)
async def speech_to_text(
    audio: UploadFile = File(...),
    source_type: str | None = Form(default=None),
    source_id: str | None = Form(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    allowed_types = {
        "audio/flac",
        "audio/m4a",
        "audio/mp3",
        "audio/mp4",
        "audio/mpeg",
        "audio/ogg",
        "audio/wav",
        "audio/webm",
    }
    content_type = (audio.content_type or "").lower()
    if content_type not in allowed_types:
        raise APIException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            code="AI_AUDIO_TYPE_UNSUPPORTED",
            message="The uploaded audio type is not supported.",
        )
    content = await audio.read(settings.AI_MAX_AUDIO_BYTES + 1)
    await audio.close()
    if not content:
        raise APIException(code="AI_AUDIO_EMPTY", message="The uploaded audio file is empty.")
    if len(content) > settings.AI_MAX_AUDIO_BYTES:
        raise APIException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            code="AI_AUDIO_TOO_LARGE",
            message="The uploaded audio file exceeds the configured size limit.",
        )
    return await ai_domain_service.speech_to_text(
        db,
        file_name=audio.filename or "audio",
        content=content,
        content_type=content_type,
        current_user=current_user,
        source_type=source_type,
        source_id=source_id,
    )


@router.get(
    "/transcription/search",
    response_model=list[TranscriptSearchResponse],
    summary="Search tenant-scoped transcripts the caller is authorized to read",
    dependencies=[Depends(require_permission("ai:read"))],
)
async def search_transcripts(
    query: str = Query(min_length=2, max_length=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await ai_domain_service.search_transcripts(db, query, current_user)


@router.get(
    "/usage-stats",
    summary="Get AI API token usage & budget consumption statistics",
    dependencies=[Depends(require_permission("ai:read"))],
)
async def get_ai_usage_stats(
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    return await ai_domain_service.get_ai_usage_stats(db, current_user)


@router.get(
    "/models",
    summary="List available AI model options",
    dependencies=[Depends(require_permission("ai:read"))],
)
async def list_ai_models(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await ai_domain_service.list_ai_models(db, current_user)


@router.post(
    "/models/switch",
    response_model=MessageResponse,
    summary="Switch default active AI model provider",
    dependencies=[
        Depends(require_permission("ai:read")),
        Depends(require_permission("settings:update")),
    ],
)
async def switch_ai_model(
    model_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await ai_domain_service.switch_ai_model(db, model_id, current_user)
