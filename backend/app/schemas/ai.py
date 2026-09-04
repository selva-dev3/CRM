from typing import Any, Literal

from pydantic import BaseModel, Field


class AIEvidence(BaseModel):
    entity_type: str
    entity_id: str
    label: str
    detail: str | None = None


class AIActionProposal(BaseModel):
    action_type: Literal["create_task", "draft_email", "update_record"]
    title: str
    payload: dict[str, Any]
    requires_confirmation: bool = True
    proposal_id: str | None = None


class AIActionConfirmationRequest(BaseModel):
    proposal_id: str = Field(min_length=1, max_length=100)


class AIActionExecutionResponse(BaseModel):
    proposal_id: str
    action_type: str
    status: Literal["executed"]
    result: dict[str, Any]


class AIResponseMetadata(BaseModel):
    run_id: str | None = None
    provider: str | None = None
    model: str | None = None
    generated_at: str


class EmailGeneratorRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=10000)
    context: dict[str, Any] | None = None
    mode: Literal["cold_outreach", "follow_up", "reply", "rewrite"] = "cold_outreach"
    tone: str = "Professional"
    entity_type: Literal["lead", "contact", "company", "deal"] | None = None
    entity_id: str | None = None


class EmailImproveRequest(BaseModel):
    email_text: str = Field(min_length=1, max_length=50000)
    tone: str = Field(default="Professional", min_length=1, max_length=100)


class TextAnalysisRequest(BaseModel):
    text: str = Field(min_length=1, max_length=100000)


class CompanyEnrichmentRequest(BaseModel):
    company_name: str = Field(min_length=1, max_length=255)
    domain: str | None = Field(default=None, max_length=255)


class ObjectionRequest(BaseModel):
    objection_text: str = Field(min_length=1, max_length=20000)


class ContractReviewRequest(BaseModel):
    contract_text: str = Field(min_length=1, max_length=200000)


class CompetitorResearchRequest(BaseModel):
    competitor_name: str = Field(min_length=1, max_length=255)


class ICPProfile(BaseModel):
    industries: list[str] = Field(default_factory=list, max_length=50)
    company_size_ranges: list[str] = Field(default_factory=list, max_length=20)
    countries: list[str] = Field(default_factory=list, max_length=100)
    buyer_titles: list[str] = Field(default_factory=list, max_length=100)
    qualification_notes: str | None = Field(default=None, max_length=5000)


class AIOrganizationConfigUpdate(BaseModel):
    enabled: bool | None = None
    model_id: str | None = Field(default=None, max_length=100)
    monthly_cost_limit_usd: float | None = Field(default=None, ge=0, le=1000000)
    icp_profile: ICPProfile | None = None


class AIOrganizationConfigResponse(BaseModel):
    enabled: bool
    provider: str
    model_id: str
    monthly_cost_limit_usd: float
    icp_profile: ICPProfile | None = None


class EmailGeneratorResponse(BaseModel):
    subject: str
    body: str
    suggested_send_time: str | None = None
    rationale: str
    evidence: list[AIEvidence] = Field(default_factory=list)
    run_id: str | None = None
    metadata: AIResponseMetadata | None = None


class MeetingSummaryRequest(BaseModel):
    transcript: str = Field(min_length=1, max_length=200000)


class MeetingSummaryResponse(BaseModel):
    summary: str
    action_items: list[str]
    decisions: list[str] = Field(default_factory=list)
    requirements: list[str] = Field(default_factory=list)
    objections: list[str] = Field(default_factory=list)
    competitors: list[str] = Field(default_factory=list)
    sentiment: str | None = None
    run_id: str | None = None


class AIChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    conversation_id: str | None = None


class AIChatGeneratedOutput(BaseModel):
    response: str
    evidence: list[AIEvidence] = Field(default_factory=list)
    proposed_actions: list[AIActionProposal] = Field(default_factory=list)


class AIChatResponse(BaseModel):
    conversation_id: str
    response: str
    evidence: list[AIEvidence] = Field(default_factory=list)
    proposed_actions: list[AIActionProposal] = Field(default_factory=list)
    run_id: str | None = None
    metadata: AIResponseMetadata | None = None


class LeadIntelligenceResponse(BaseModel):
    lead_id: str
    score: float = Field(ge=0, le=100)
    conversion_probability: float = Field(ge=0, le=100)
    quality: Literal["Hot", "Warm", "Cold"]
    qualification: Literal["Qualified", "Needs Review", "Unqualified"]
    confidence: float = Field(ge=0, le=1)
    reasons: list[str]
    recommended_owner_id: str | None = None
    recommended_owner_reason: str | None = None
    run_id: str | None = None


class DealIntelligenceResponse(BaseModel):
    deal_id: str
    win_probability: float = Field(ge=0, le=100)
    risk_score: float = Field(ge=0, le=100)
    health: Literal["Healthy", "At Risk", "Critical"]
    stalled: bool
    expected_close_date: str | None = None
    risk_factors: list[str]
    key_drivers: list[str]
    next_action: str
    explanation: str
    confidence: float = Field(ge=0, le=1)
    run_id: str | None = None


class SentimentAnalysisResponse(BaseModel):
    sentiment: Literal["Positive", "Neutral", "Negative"]
    confidence: float = Field(ge=0, le=1)
    reasons: list[str]
    escalation_required: bool
    urgency: Literal["Low", "Medium", "High", "Critical"]
    run_id: str | None = None


class NextBestActionResponse(BaseModel):
    entity_type: Literal["lead", "deal", "company", "contact"]
    entity_id: str
    recommended_action: str
    reason: str
    priority: Literal["Low", "Medium", "High", "Critical"]
    timing: str
    channel: Literal["Email", "Phone", "Meeting", "Task", "None"]
    evidence: list[AIEvidence] = Field(default_factory=list)
    run_id: str | None = None


class CompanyIntelligenceResponse(BaseModel):
    company_name: str
    industry: str | None = None
    employee_count_range: str | None = None
    estimated_revenue_range: str | None = None
    technologies: list[str] = Field(default_factory=list)
    description: str
    decision_maker_roles: list[str] = Field(default_factory=list)
    fit_score: float = Field(ge=0, le=100)
    health: Literal["Healthy", "Needs Attention", "Unknown"]
    sources: list[str] = Field(default_factory=list)
    run_id: str | None = None


class CompetitorBattlecardResponse(BaseModel):
    competitor: str
    comparison: str
    our_strengths: list[str]
    competitor_strengths: list[str]
    competitor_weaknesses: list[str]
    positioning: list[str]
    strategy: str
    sources: list[str] = Field(default_factory=list)
    run_id: str | None = None


class ObjectionResponse(BaseModel):
    category: str
    objection: str
    suggested_response: str
    talking_points: list[str]
    proof_points: list[str]
    follow_up_questions: list[str]
    strategy: str
    run_id: str | None = None


class ContractReviewResponse(BaseModel):
    summary: str
    risk_level: Literal["Low", "Medium", "High", "Critical"]
    clauses: list[dict[str, Any]]
    risks: list[dict[str, Any]]
    renewal_date: str | None = None
    payment_terms: str | None = None
    liability: str | None = None
    compliance_findings: list[str] = Field(default_factory=list)
    source_references: list[str] = Field(default_factory=list)
    run_id: str | None = None


class ICPMatchResponse(BaseModel):
    entity_id: str
    overall_fit: float = Field(ge=0, le=100)
    company_fit: float = Field(ge=0, le=100)
    persona_fit: float = Field(ge=0, le=100)
    qualification: Literal["Qualified", "Needs Review", "Unqualified"]
    match_factors: list[str]
    gaps: list[str]
    run_id: str | None = None


class ChurnPredictionResponse(BaseModel):
    company_id: str
    churn_probability: float = Field(ge=0, le=100)
    risk_tier: Literal["Low", "Medium", "High", "Critical"]
    engagement_factors: list[str]
    sentiment_factors: list[str]
    competitor_signals: list[str]
    renewal_risk: str
    retention_action: str
    run_id: str | None = None


class PricingRecommendationResponse(BaseModel):
    deal_id: str
    recommended_price: float = Field(ge=0)
    recommended_discount_pct: float = Field(ge=0, le=100)
    margin_impact: str
    historical_outcome_summary: str
    guardrail_status: Literal["Within Guardrails", "Approval Required", "Rejected"]
    explanation: str
    run_id: str | None = None


class TranscriptionSegment(BaseModel):
    speaker: str | None = None
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(ge=0)
    text: str


class TranscriptionResponse(BaseModel):
    text: str
    language: str | None = None
    duration_seconds: float | None = None
    segments: list[TranscriptionSegment] = Field(default_factory=list)
    run_id: str | None = None
    transcript_id: str | None = None


class TranscriptSearchResponse(BaseModel):
    id: str
    source_type: str | None = None
    source_id: str | None = None
    file_name: str
    language: str | None = None
    duration_seconds: float | None = None
    text: str
    created_at: str


class AISalesForecastResponse(BaseModel):
    commit_revenue: float = Field(ge=0)
    best_case_revenue: float = Field(ge=0)
    at_risk_revenue: float = Field(ge=0)
    confidence: float = Field(ge=0, le=1)
    explanation: str
    factors: list[str]
    run_id: str | None = None


class AISalesForecastAnalysis(BaseModel):
    at_risk_percentage: float = Field(ge=0, le=100)
    confidence: float = Field(ge=0, le=1)
    explanation: str
    factors: list[str]


class RepCoachingResponse(BaseModel):
    user_id: str
    strengths: list[str]
    improvement_areas: list[str]
    coaching_actions: list[str]
    evidence: list[AIEvidence] = Field(default_factory=list)
    run_id: str | None = None


class FollowUpRecommendationResponse(BaseModel):
    entity_type: str
    entity_id: str
    inactive_days: int = Field(ge=0)
    recommendation: str
    email_draft: EmailGeneratorResponse | None = None
    task: AIActionProposal | None = None
    requires_approval: bool = True
    run_id: str | None = None


class DataQualityFinding(BaseModel):
    entity_type: str
    entity_id: str
    score: float = Field(ge=0, le=100)
    duplicate_ids: list[str] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    stale: bool
    reasons: list[str]


class Customer360Response(BaseModel):
    entity_type: Literal["company", "contact"]
    entity_id: str
    summary: str
    relationship_health: Literal["Healthy", "Needs Attention", "At Risk"]
    open_deal_value: float = Field(ge=0)
    last_interaction_at: str | None = None
    sentiment: str | None = None
    churn_risk: str | None = None
    recent_issues: list[str] = Field(default_factory=list)
    next_action: str
    freshness: str
    evidence: list[AIEvidence] = Field(default_factory=list)
    run_id: str | None = None


class EntityAIRequest(BaseModel):
    entity_type: Literal["lead", "deal", "company", "contact"]
    entity_id: str = Field(min_length=1, max_length=100)


class RepCoachingRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=100)


class DataCleaningRequest(BaseModel):
    entity_type: Literal["lead", "contact", "company"]


class DataQualityResponse(BaseModel):
    entity_type: Literal["lead", "contact", "company"]
    findings: list[DataQualityFinding]
    reviewed_count: int
    destructive_changes_applied: bool = False


class CRMSearchRequest(BaseModel):
    query: str = Field(min_length=3, max_length=1000)
    scope: Literal["lead", "contact", "company", "deal", "task"]


class CRMSearchPlan(BaseModel):
    entity_type: Literal["lead", "contact", "company", "deal", "task"]
    text_query: str | None = None
    status: str | None = None
    inactive_days: int | None = Field(default=None, ge=1, le=3650)
    minimum_open_deal_amount: float | None = Field(default=None, ge=0)
    limit: int = Field(default=20, ge=1, le=50)


class CRMSearchResponse(BaseModel):
    query: str
    plan: CRMSearchPlan
    results: list[dict[str, Any]]
    result_count: int
    run_id: str
