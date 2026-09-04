from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIException, ForbiddenError, NotFoundError
from app.models import Company, Contact, Deal, Lead, User
from app.repositories.ai_repository import AIRepository
from app.schemas.ai import (
    AIActionProposal,
    AIChatGeneratedOutput,
    AIEvidence,
    AIOrganizationConfigUpdate,
    AISalesForecastAnalysis,
    CRMSearchPlan,
    Customer360Response,
    DataCleaningRequest,
    DealIntelligenceResponse,
    EmailGeneratorRequest,
    EmailGeneratorResponse,
    FollowUpRecommendationResponse,
    ICPMatchResponse,
    ICPProfile,
    LeadIntelligenceResponse,
    NextBestActionResponse,
    RepCoachingResponse,
    TranscriptionResponse,
)
from app.schemas.dashboard import DashboardAiInsightsResponse
from app.services.ai_domain_service import AIDomainService


def _user(**overrides: Any) -> User:
    defaults = {
        "id": "user-1",
        "email": "user@example.com",
        "organization_id": "org-1",
    }
    defaults.update(overrides)
    return User(**defaults)


def _lead(**overrides: Any) -> Lead:
    defaults = {
        "id": "lead-1",
        "organization_id": "org-1",
        "title": "VP Sales",
        "company": "Acme",
        "status": "new",
        "score": 50.0,
    }
    defaults.update(overrides)
    return Lead(**defaults)


def _deal(**overrides: Any) -> Deal:
    defaults = {
        "id": "deal-1",
        "organization_id": "org-1",
        "title": "Expansion",
        "amount": 12000.0,
        "probability": 65.0,
    }
    defaults.update(overrides)
    return Deal(**defaults)


def _company(**overrides: Any) -> Company:
    defaults = {"id": "company-1", "organization_id": "org-1", "name": "Acme"}
    defaults.update(overrides)
    return Company(**defaults)


def _repository() -> Any:
    repository: Any = AIRepository()
    repository.get_lead = AsyncMock()
    repository.list_leads = AsyncMock(return_value=[])
    repository.get_deal = AsyncMock()
    repository.get_company = AsyncMock()
    repository.get_contact = AsyncMock()
    repository.get_call = AsyncMock()
    repository.get_deal_signals = AsyncMock(return_value={"recent_activities": []})
    repository.get_lead_assignment_candidates = AsyncMock(return_value=[])
    repository.get_pricing_signals = AsyncMock(return_value={})
    repository.get_customer_context = AsyncMock()
    repository.create_transcript = AsyncMock(return_value=SimpleNamespace(id="transcript-1"))
    repository.search_transcripts = AsyncMock(return_value=[])
    repository.get_conversation = AsyncMock()
    repository.get_organization_config = AsyncMock(return_value=None)
    repository.set_organization_model = AsyncMock()
    repository.update_organization_config = AsyncMock()
    repository.search_context = AsyncMock(return_value={})
    repository.save_lead_score = AsyncMock()
    repository.create_generated_content = AsyncMock()
    repository.create_conversation = AsyncMock(return_value=SimpleNamespace(id="conversation-1"))
    repository.create_prompt = AsyncMock()
    repository.create_action = AsyncMock(return_value=SimpleNamespace(id="proposal-1"))
    repository.get_pending_action = AsyncMock()
    return repository


def _runtime(output: Any) -> AsyncMock:
    runtime = AsyncMock()
    runtime.execute.return_value = (
        output,
        SimpleNamespace(id="run-1", model_name="gpt-4o-mini", total_tokens=25),
    )
    return runtime


def _lead_result() -> LeadIntelligenceResponse:
    return LeadIntelligenceResponse(
        lead_id="lead-1",
        score=88,
        conversion_probability=72,
        quality="Hot",
        qualification="Qualified",
        confidence=0.86,
        reasons=["Senior buyer", "Target company"],
    )


@pytest.mark.asyncio
async def test_evaluate_lead_score_is_tenant_scoped_and_persists_history():
    repository = _repository()
    lead = _lead()
    repository.get_lead.return_value = lead
    runtime = _runtime(_lead_result())
    service = AIDomainService(repository=repository, runtime=runtime)
    service._permission_keys = AsyncMock(return_value={"ai:generate", "leads:update"})
    db = AsyncMock(spec=AsyncSession)

    result = await service.evaluate_lead_score(db, "lead-1", _user())

    assert result["score"] == 88
    assert result["run_id"] == "run-1"
    repository.get_lead.assert_awaited_once_with(db, lead_id="lead-1", organization_id="org-1")
    repository.save_lead_score.assert_awaited_once_with(
        db,
        lead=lead,
        score=88,
        confidence=0.86,
        reasons_json='["Senior buyer", "Target company"]',
    )
    assert db.commit.await_count == 2


@pytest.mark.asyncio
async def test_evaluate_lead_score_hides_cross_tenant_lead():
    repository = _repository()
    repository.get_lead.return_value = None
    runtime = _runtime(_lead_result())
    service = AIDomainService(repository=repository, runtime=runtime)

    with pytest.raises(NotFoundError):
        await service.evaluate_lead_score(AsyncMock(spec=AsyncSession), "other-org-lead", _user())

    runtime.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_lead_assignment_recommendation_uses_only_authorized_tenant_candidates():
    repository = _repository()
    repository.get_lead.return_value = _lead()
    repository.get_lead_assignment_candidates.return_value = [
        {
            "id": "rep-1",
            "name": "Alex Rep",
            "deal_count": 8,
            "won_count": 4,
            "open_deal_count": 2,
        }
    ]
    result = _lead_result()
    result.recommended_owner_id = "foreign-rep"
    result.recommended_owner_reason = "Unsupported provider suggestion"
    service = AIDomainService(repository=repository, runtime=_runtime(result))
    service._permission_keys = AsyncMock(return_value={"ai:generate", "leads:update", "users:read"})
    db = AsyncMock(spec=AsyncSession)

    response = await service.evaluate_lead_score(db, "lead-1", _user())

    repository.get_lead_assignment_candidates.assert_awaited_once_with(
        db,
        organization_id="org-1",
    )
    assert response["recommended_owner_id"] is None


@pytest.mark.asyncio
async def test_batch_lead_scoring_lists_only_current_organization():
    repository = _repository()
    service = AIDomainService(repository=repository, runtime=AsyncMock())
    db = AsyncMock(spec=AsyncSession)

    result = await service.batch_lead_scoring(db, _user())

    assert result == {"processed_count": 0, "updated_count": 0, "failures": []}
    repository.list_leads.assert_awaited_once_with(db, organization_id="org-1")


@pytest.mark.asyncio
async def test_generate_email_rejects_blank_prompt_before_provider_call():
    runtime = AsyncMock()
    service = AIDomainService(repository=_repository(), runtime=runtime)

    with pytest.raises(APIException):
        await service.generate_email(
            AsyncMock(spec=AsyncSession), EmailGeneratorRequest(prompt=" "), _user()
        )

    runtime.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_generate_email_requires_underlying_email_permission():
    runtime = AsyncMock()
    service = AIDomainService(repository=_repository(), runtime=runtime)
    service._permission_keys = AsyncMock(return_value={"ai:generate"})

    with pytest.raises(ForbiddenError):
        await service.generate_email(
            AsyncMock(spec=AsyncSession),
            EmailGeneratorRequest(prompt="Write a follow-up"),
            _user(),
        )

    runtime.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_generate_email_uses_provider_and_persists_output():
    repository = _repository()
    output = EmailGeneratorResponse(
        subject="Next steps",
        body="Hello, shall we continue?",
        rationale="Concise follow-up",
    )
    runtime = _runtime(output)
    service = AIDomainService(repository=repository, runtime=runtime)
    service._permission_keys = AsyncMock(return_value={"ai:generate", "emails:read"})
    db = AsyncMock(spec=AsyncSession)

    result = await service.generate_email(
        db,
        EmailGeneratorRequest(prompt="Write a follow-up", mode="follow_up"),
        _user(),
    )

    assert result["subject"] == "Next steps"
    repository.create_generated_content.assert_awaited_once()
    assert repository.create_generated_content.await_args.kwargs["organization_id"] == "org-1"
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_deal_intelligence_is_tenant_scoped():
    repository = _repository()
    repository.get_deal.return_value = _deal()
    output = DealIntelligenceResponse(
        deal_id="deal-1",
        win_probability=70,
        risk_score=30,
        health="Healthy",
        stalled=False,
        risk_factors=[],
        key_drivers=["Recent activity"],
        next_action="Schedule review",
        explanation="Deal is progressing",
        confidence=0.8,
    )
    service = AIDomainService(repository=repository, runtime=_runtime(output))
    db = AsyncMock(spec=AsyncSession)

    result = await service.predict_deal_forecast(db, "deal-1", _user())

    assert result["win_probability"] == 70
    repository.get_deal.assert_awaited_once_with(db, deal_id="deal-1", organization_id="org-1")
    repository.get_deal_signals.assert_awaited_once_with(
        db, deal_id="deal-1", organization_id="org-1"
    )


@pytest.mark.asyncio
async def test_next_best_action_supports_tenant_scoped_contacts():
    repository = _repository()
    repository.get_contact.return_value = Contact(
        id="contact-1",
        organization_id="org-1",
        name="Jane Buyer",
        email="jane@example.com",
    )
    output = NextBestActionResponse(
        entity_type="contact",
        entity_id="contact-1",
        recommended_action="Schedule a call",
        reason="No recent interaction is recorded",
        priority="Medium",
        timing="This week",
        channel="Phone",
    )
    service = AIDomainService(repository=repository, runtime=_runtime(output))
    service._permission_keys = AsyncMock(return_value={"ai:generate", "contacts:read"})
    db = AsyncMock(spec=AsyncSession)

    result = await service.suggest_next_best_action(db, "contact", "contact-1", _user())

    assert result["entity_id"] == "contact-1"
    repository.get_contact.assert_awaited_once_with(
        db, contact_id="contact-1", organization_id="org-1"
    )


@pytest.mark.asyncio
async def test_icp_match_requires_tenant_configuration_before_provider_call():
    repository = _repository()
    repository.get_lead.return_value = _lead()
    runtime = AsyncMock()
    service = AIDomainService(repository=repository, runtime=runtime)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(APIException) as exc_info:
        await service.evaluate_icp_match(db, "lead-1", _user())

    assert exc_info.value.code == "AI_ICP_NOT_CONFIGURED"
    repository.get_organization_config.assert_awaited_once_with(db, "org-1")
    runtime.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_icp_match_uses_current_organization_profile():
    repository = _repository()
    repository.get_lead.return_value = _lead(industry="Software", company_size="51-200")
    repository.get_organization_config.return_value = SimpleNamespace(
        icp_profile_json='{"industries":["Software"],"company_size_ranges":["51-200"]}'
    )
    output = ICPMatchResponse(
        entity_id="lead-1",
        overall_fit=90,
        company_fit=92,
        persona_fit=80,
        qualification="Qualified",
        match_factors=["Target industry"],
        gaps=[],
    )
    runtime = _runtime(output)
    service = AIDomainService(repository=repository, runtime=runtime)
    db = AsyncMock(spec=AsyncSession)

    result = await service.evaluate_icp_match(db, "lead-1", _user())

    assert result["overall_fit"] == 90
    context = runtime.execute.await_args.kwargs["user_prompt"]
    assert '"organization_icp_profile"' in context
    assert '"Software"' in context


@pytest.mark.asyncio
async def test_ai_configuration_update_is_tenant_scoped():
    repository = _repository()
    repository.get_organization_config.return_value = SimpleNamespace(
        enabled=False,
        provider=None,
        model_name=None,
        monthly_cost_limit_usd=25.0,
        icp_profile_json='{"industries":["Software"]}',
    )
    service = AIDomainService(repository=repository, runtime=AsyncMock())
    db = AsyncMock(spec=AsyncSession)
    payload = AIOrganizationConfigUpdate(
        enabled=False,
        monthly_cost_limit_usd=25,
        icp_profile=ICPProfile(industries=["Software"]),
    )

    result = await service.update_organization_config(db, payload, _user())

    assert result["enabled"] is False
    repository.update_organization_config.assert_awaited_once_with(
        db,
        organization_id="org-1",
        enabled=False,
        monthly_cost_limit_usd=25.0,
        icp_profile_json=payload.icp_profile.model_dump_json(),
        update_icp_profile=True,
    )
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_sales_assistant_rejects_cross_tenant_conversation():
    repository = _repository()
    repository.get_conversation.return_value = None
    service = AIDomainService(repository=repository, runtime=AsyncMock())
    service._permission_keys = AsyncMock(return_value={"ai:generate", "deals:read"})

    with pytest.raises(NotFoundError):
        await service.sales_assistant_chat(
            AsyncMock(spec=AsyncSession), "Deal status", "other-conversation", _user()
        )

    assert repository.get_conversation.await_args.kwargs["organization_id"] == "org-1"


@pytest.mark.asyncio
async def test_sales_assistant_uses_only_permitted_crm_modules():
    repository = _repository()
    output = AIChatGeneratedOutput(response="One matching deal was found")
    service = AIDomainService(repository=repository, runtime=_runtime(output))
    service._permission_keys = AsyncMock(return_value={"ai:generate", "deals:read", "tasks:read"})
    db = AsyncMock(spec=AsyncSession)

    result = await service.sales_assistant_chat(db, "Expansion", None, _user())

    assert result["conversation_id"] == "conversation-1"
    assert repository.search_context.await_args.kwargs["allowed_modules"] == {
        "deals",
        "tasks",
    }
    repository.create_prompt.assert_awaited_once()


@pytest.mark.asyncio
async def test_sales_assistant_drops_evidence_not_present_in_authorized_context():
    repository = _repository()
    repository.search_context.return_value = {
        "deals": [{"id": "deal-1", "title": "Authorized deal"}]
    }
    output = AIChatGeneratedOutput(
        response="A deal was found.",
        evidence=[
            AIEvidence(entity_type="deal", entity_id="deal-1", label="Authorized"),
            AIEvidence(entity_type="deal", entity_id="foreign-deal", label="Invalid"),
        ],
    )
    service = AIDomainService(repository=repository, runtime=_runtime(output))
    service._permission_keys = AsyncMock(return_value={"ai:generate", "deals:read"})

    result = await service.sales_assistant_chat(
        AsyncMock(spec=AsyncSession), "Find a deal", None, _user()
    )

    assert [(item["entity_type"], item["entity_id"]) for item in result["evidence"]] == [
        ("deal", "deal-1")
    ]


@pytest.mark.asyncio
async def test_sales_assistant_persists_only_supported_confirmation_actions():
    repository = _repository()
    output = AIChatGeneratedOutput(
        response="I prepared a task proposal.",
        proposed_actions=[
            AIActionProposal(
                action_type="create_task",
                title="Follow up",
                payload={"title": "Follow up", "priority": "High"},
            ),
            AIActionProposal(
                action_type="update_record",
                title="Unsafe update",
                payload={"id": "deal-1"},
            ),
        ],
    )
    service = AIDomainService(repository=repository, runtime=_runtime(output))
    service._permission_keys = AsyncMock(return_value={"ai:generate", "tasks:read"})

    result = await service.sales_assistant_chat(
        AsyncMock(spec=AsyncSession), "Create a follow-up", None, _user()
    )

    assert len(result["proposed_actions"]) == 1
    assert result["proposed_actions"][0]["proposal_id"] == "proposal-1"
    assert repository.create_action.await_args.kwargs["organization_id"] == "org-1"
    assert repository.create_action.await_args.kwargs["user_id"] == "user-1"


@pytest.mark.asyncio
async def test_confirm_action_requires_underlying_task_permission():
    repository = _repository()
    repository.get_pending_action.return_value = SimpleNamespace(
        id="proposal-1",
        action_type="create_task",
        payload_json='{"title":"Follow up"}',
        expires_at=datetime.now(UTC) + timedelta(minutes=10),
    )
    tasks = AsyncMock()
    service = AIDomainService(
        repository=repository,
        runtime=AsyncMock(),
        task_service_instance=tasks,
    )
    service._permission_keys = AsyncMock(return_value={"ai:generate"})

    with pytest.raises(ForbiddenError):
        await service.confirm_action(AsyncMock(spec=AsyncSession), "proposal-1", _user())

    tasks.create_task.assert_not_awaited()


@pytest.mark.asyncio
async def test_confirm_action_is_scoped_and_creates_task_for_current_user():
    repository = _repository()
    action = SimpleNamespace(
        id="proposal-1",
        action_type="create_task",
        payload_json=(
            '{"title":"Follow up","priority":"High",'
            '"assigned_to":"foreign-user","status":"Completed"}'
        ),
        expires_at=datetime.now(UTC) + timedelta(minutes=10),
        status="pending",
        result_json=None,
        executed_at=None,
    )
    repository.get_pending_action.return_value = action
    tasks = AsyncMock()
    tasks.create_task.return_value = {"id": "task-1", "title": "Follow up"}
    service = AIDomainService(
        repository=repository,
        runtime=AsyncMock(),
        task_service_instance=tasks,
    )
    service._permission_keys = AsyncMock(return_value={"ai:generate", "tasks:create"})
    db = AsyncMock(spec=AsyncSession)
    actor = _user()

    result = await service.confirm_action(db, "proposal-1", actor)

    repository.get_pending_action.assert_awaited_once_with(
        db,
        action_id="proposal-1",
        organization_id="org-1",
        user_id="user-1",
    )
    task_payload = tasks.create_task.await_args.args[1]
    assert task_payload.assigned_to == "user-1"
    assert task_payload.status == "Pending"
    assert result["status"] == "executed"
    assert action.status == "executed"


@pytest.mark.asyncio
async def test_crm_search_checks_scope_permission_before_ai_planning():
    runtime = AsyncMock()
    service = AIDomainService(repository=_repository(), runtime=runtime)
    service._permission_keys = AsyncMock(return_value={"ai:generate", "contacts:read"})

    with pytest.raises(ForbiddenError):
        await service.search_crm(
            AsyncMock(spec=AsyncSession), "open deals over 500000", "deal", _user()
        )

    runtime.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_crm_search_executes_only_validated_tenant_scoped_plan():
    repository = _repository()
    repository.execute_search_plan = AsyncMock(
        return_value=[{"id": "company-1", "name": "Acme", "open_deal_value": 600000}]
    )
    plan = CRMSearchPlan(
        entity_type="company",
        inactive_days=30,
        minimum_open_deal_amount=500000,
    )
    service = AIDomainService(repository=repository, runtime=_runtime(plan))
    service._permission_keys = AsyncMock(
        return_value={"ai:generate", "companies:read", "deals:read"}
    )
    db = AsyncMock(spec=AsyncSession)

    result = await service.search_crm(
        db,
        "Customers not contacted in 30 days with open deals above 5 lakh",
        "company",
        _user(),
    )

    assert result["result_count"] == 1
    assert repository.execute_search_plan.await_args.kwargs["organization_id"] == "org-1"
    assert repository.execute_search_plan.await_args.kwargs["minimum_open_deal_amount"] == 500000


@pytest.mark.asyncio
async def test_crm_search_rejects_provider_scope_escalation():
    plan = CRMSearchPlan(entity_type="deal")
    runtime = _runtime(plan)
    service = AIDomainService(repository=_repository(), runtime=runtime)
    service._permission_keys = AsyncMock(return_value={"ai:generate", "companies:read"})

    with pytest.raises(APIException) as exc_info:
        await service.search_crm(AsyncMock(spec=AsyncSession), "Show Acme", "company", _user())

    assert exc_info.value.code == "AI_INVALID_SEARCH_PLAN"


@pytest.mark.asyncio
async def test_sales_forecast_preserves_canonical_revenue_values():
    reports = AsyncMock()
    reports.get_revenue_forecasting_report.return_value = {
        "metrics": {
            "committed_revenue": 100000,
            "open_pipeline_amount": 500000,
            "weighted_pipeline_amount": 250000,
            "table_rows": [],
        }
    }
    analysis = AISalesForecastAnalysis(
        at_risk_percentage=20,
        confidence=0.75,
        explanation="Half the pipeline is probability weighted.",
        factors=["Weighted pipeline coverage"],
    )
    service = AIDomainService(
        repository=_repository(),
        runtime=_runtime(analysis),
        report_service_instance=reports,
    )
    service._permission_keys = AsyncMock(return_value={"ai:generate", "reports:read", "deals:read"})
    db = AsyncMock(spec=AsyncSession)
    actor = _user()

    result = await service.get_sales_forecast(db, actor)

    assert result["commit_revenue"] == 100000
    assert result["best_case_revenue"] == 600000
    assert result["at_risk_revenue"] == 100000
    reports.get_revenue_forecasting_report.assert_awaited_once_with(db, current_user=actor)


@pytest.mark.asyncio
async def test_dashboard_insights_drop_hallucinated_deal_identifiers():
    output = DashboardAiInsightsResponse(
        summary="Pipeline summary",
        insights=[
            {
                "title": "Valid",
                "description": "Uses an authorized deal",
                "type": "info",
                "deal_id": "deal-1",
            },
            {
                "title": "Invalid",
                "description": "Invented deal",
                "type": "warning",
                "deal_id": "foreign-deal",
            },
        ],
        risk_deals=[],
    )
    service = AIDomainService(repository=_repository(), runtime=_runtime(output))

    result = await service.generate_dashboard_insights(
        AsyncMock(spec=AsyncSession),
        {"deals": [{"id": "deal-1", "title": "Authorized"}]},
        _user(),
    )

    assert [item["deal_id"] for item in result["insights"]] == ["deal-1"]


@pytest.mark.asyncio
async def test_sales_coach_hides_cross_tenant_user_before_ai_call():
    repository = _repository()
    repository.get_user = AsyncMock(return_value=None)
    runtime = AsyncMock()
    service = AIDomainService(repository=repository, runtime=runtime)
    service._permission_keys = AsyncMock(return_value={"ai:generate", "users:read", "reports:read"})

    with pytest.raises(NotFoundError):
        await service.coach_sales_rep(AsyncMock(spec=AsyncSession), "foreign-user", _user())

    runtime.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_sales_coach_uses_tenant_scoped_recorded_metrics():
    repository = _repository()
    repository.get_user = AsyncMock(return_value=_user(name="Sales Rep"))
    repository.get_rep_metrics = AsyncMock(
        return_value={"deal_count": 10, "won_count": 4, "lost_count": 2}
    )
    output = RepCoachingResponse(
        user_id="user-1",
        strengths=["Consistent wins"],
        improvement_areas=["Follow-up evidence unavailable"],
        coaching_actions=["Record follow-up activity"],
    )
    service = AIDomainService(repository=repository, runtime=_runtime(output))
    service._permission_keys = AsyncMock(return_value={"ai:generate", "users:read", "reports:read"})
    db = AsyncMock(spec=AsyncSession)

    result = await service.coach_sales_rep(db, "user-1", _user())

    assert result["strengths"] == ["Consistent wins"]
    repository.get_rep_metrics.assert_awaited_once_with(
        db, user_id="user-1", organization_id="org-1"
    )


@pytest.mark.asyncio
async def test_follow_up_remains_approval_only():
    repository = _repository()
    repository.get_lead.return_value = _lead(updated_at=datetime.now(UTC) - timedelta(days=31))
    output = FollowUpRecommendationResponse(
        entity_type="lead",
        entity_id="lead-1",
        inactive_days=1,
        recommendation="Send a concise check-in",
    )
    service = AIDomainService(repository=repository, runtime=_runtime(output))
    service._permission_keys = AsyncMock(return_value={"ai:generate", "leads:read"})

    result = await service.recommend_follow_up(
        AsyncMock(spec=AsyncSession), "lead", "lead-1", _user()
    )

    assert result["inactive_days"] == 31
    assert result["requires_approval"] is True


@pytest.mark.asyncio
async def test_data_cleaning_detects_duplicates_without_mutation():
    repository = _repository()
    repository.list_cleaning_records = AsyncMock(
        return_value=[
            _lead(id="lead-1", email="buyer@example.com", contact_name="Jane Buyer"),
            _lead(id="lead-2", email="BUYER@example.com", contact_name="Jane Buyer"),
        ]
    )
    runtime = AsyncMock()
    runtime.start_local_run.return_value = SimpleNamespace(id="local-run-1")
    service = AIDomainService(repository=repository, runtime=runtime)
    service._permission_keys = AsyncMock(return_value={"ai:generate", "leads:read"})
    db = AsyncMock(spec=AsyncSession)

    result = await service.analyze_data_quality(
        db, DataCleaningRequest(entity_type="lead"), _user()
    )

    assert result["destructive_changes_applied"] is False
    assert result["findings"][0]["duplicate_ids"] == ["lead-2"]
    runtime.start_local_run.assert_awaited_once()
    runtime.complete_local_run.assert_awaited_once()


@pytest.mark.asyncio
async def test_customer_360_only_loads_modules_the_caller_can_read():
    repository = _repository()
    repository.get_customer_context = AsyncMock(
        return_value={"entity": {"id": "company-1", "name": "Acme"}}
    )
    output = Customer360Response(
        entity_type="company",
        entity_id="company-1",
        summary="No interaction evidence is available.",
        relationship_health="Needs Attention",
        open_deal_value=999,
        next_action="Review available CRM data",
        freshness="Current entity record",
    )
    service = AIDomainService(repository=repository, runtime=_runtime(output))
    service._permission_keys = AsyncMock(return_value={"ai:generate", "companies:read"})
    db = AsyncMock(spec=AsyncSession)

    result = await service.get_customer_360(db, "company", "company-1", _user())

    assert result["open_deal_value"] == 0
    assert repository.get_customer_context.await_args.kwargs["include_deals"] is False
    assert repository.get_customer_context.await_args.kwargs["include_calls"] is False


@pytest.mark.asyncio
async def test_churn_prediction_hides_cross_tenant_company():
    repository = _repository()
    repository.get_company.return_value = None
    service = AIDomainService(repository=repository, runtime=AsyncMock())

    with pytest.raises(NotFoundError):
        await service.predict_churn_risk(AsyncMock(spec=AsyncSession), "other-company", _user())


@pytest.mark.asyncio
async def test_pricing_intelligence_hides_cross_tenant_deal():
    repository = _repository()
    repository.get_deal.return_value = None
    service = AIDomainService(repository=repository, runtime=AsyncMock())

    with pytest.raises(NotFoundError):
        await service.optimize_pricing(AsyncMock(spec=AsyncSession), "other-deal", _user())


@pytest.mark.asyncio
async def test_transcription_uses_audited_provider_runtime():
    runtime = AsyncMock()
    runtime.execute_transcription.return_value = (
        TranscriptionResponse(text="Customer approved next steps", language="en"),
        SimpleNamespace(id="run-audio-1"),
    )
    service = AIDomainService(repository=_repository(), runtime=runtime)
    service._permission_keys = AsyncMock(return_value={"ai:generate", "calls:recording"})
    db = AsyncMock(spec=AsyncSession)
    audio = b"audio bytes"
    actor = _user()

    result = await service.speech_to_text(
        db,
        file_name="call.mp3",
        content=audio,
        content_type="audio/mpeg",
        current_user=actor,
    )

    assert result["text"] == "Customer approved next steps"
    assert result["run_id"] == "run-audio-1"
    assert result["transcript_id"] == "transcript-1"
    runtime.execute_transcription.assert_awaited_once_with(
        db,
        current_user=actor,
        file_name="call.mp3",
        content=audio,
        content_type="audio/mpeg",
    )
    repository = service.repository
    repository.create_transcript.assert_awaited_once()
    assert repository.create_transcript.await_args.kwargs["organization_id"] == "org-1"


@pytest.mark.asyncio
async def test_transcription_rejects_cross_tenant_link_before_provider_call():
    repository = _repository()
    repository.get_call.return_value = None
    runtime = AsyncMock()
    service = AIDomainService(repository=repository, runtime=runtime)
    service._permission_keys = AsyncMock(
        return_value={"ai:generate", "calls:read", "calls:recording"}
    )

    with pytest.raises(NotFoundError):
        await service.speech_to_text(
            AsyncMock(spec=AsyncSession),
            file_name="call.mp3",
            content=b"audio",
            content_type="audio/mpeg",
            current_user=_user(),
            source_type="call",
            source_id="foreign-call",
        )

    runtime.execute_transcription.assert_not_awaited()


@pytest.mark.asyncio
async def test_transcript_search_limits_linked_sources_by_permissions():
    repository = _repository()
    service = AIDomainService(repository=repository, runtime=AsyncMock())
    service._permission_keys = AsyncMock(return_value={"ai:read", "meetings:read"})

    await service.search_transcripts(AsyncMock(spec=AsyncSession), "pricing", _user())

    assert repository.search_transcripts.await_args.kwargs["organization_id"] == "org-1"
    assert repository.search_transcripts.await_args.kwargs["allowed_source_types"] == {"meeting"}
    assert repository.search_transcripts.await_args.kwargs["allow_unlinked"] is False


@pytest.mark.asyncio
async def test_meeting_transcription_does_not_require_call_recording_permission():
    repository = _repository()
    repository.get_meeting = AsyncMock(return_value=SimpleNamespace(id="meeting-1"))
    runtime = AsyncMock()
    runtime.execute_transcription.return_value = (
        TranscriptionResponse(text="Meeting transcript"),
        SimpleNamespace(id="run-meeting-1"),
    )
    service = AIDomainService(repository=repository, runtime=runtime)
    service._permission_keys = AsyncMock(return_value={"ai:generate", "meetings:read"})

    await service.speech_to_text(
        AsyncMock(spec=AsyncSession),
        file_name="meeting.mp3",
        content=b"audio",
        content_type="audio/mpeg",
        current_user=_user(),
        source_type="meeting",
        source_id="meeting-1",
    )

    repository.get_meeting.assert_awaited_once()
    runtime.execute_transcription.assert_awaited_once()


@pytest.mark.asyncio
async def test_unlinked_transcription_requires_recording_permission():
    runtime = AsyncMock()
    service = AIDomainService(repository=_repository(), runtime=runtime)
    service._permission_keys = AsyncMock(return_value={"ai:generate"})

    with pytest.raises(ForbiddenError):
        await service.speech_to_text(
            AsyncMock(spec=AsyncSession),
            file_name="audio.mp3",
            content=b"audio",
            content_type="audio/mpeg",
            current_user=_user(),
        )

    runtime.execute_transcription.assert_not_awaited()
