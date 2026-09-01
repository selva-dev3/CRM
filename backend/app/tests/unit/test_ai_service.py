from typing import Any
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIException, NotFoundError
from app.models import Company, Deal, Lead
from app.repositories.ai_repository import AIRepository
from app.schemas.crm_schemas import AIGenerateEmailRequest
from app.services.ai_domain_service import AIDomainService


def _make_lead(**overrides) -> Lead:
    defaults = {"id": "lead-1", "score": 82.0}
    defaults.update(overrides)
    return Lead(**defaults)


def _make_deal(**overrides) -> Deal:
    defaults = {"id": "deal-1", "amount": 12000.0, "probability": 65.0}
    defaults.update(overrides)
    return Deal(**defaults)


def _make_company(**overrides) -> Company:
    defaults = {"id": "comp-1"}
    defaults.update(overrides)
    return Company(**defaults)


@pytest.mark.asyncio
async def test_evaluate_lead_score_uses_score():
    repo: Any = AIRepository()
    repo.get_lead = AsyncMock(return_value=_make_lead(score=88.0))
    service = AIDomainService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.evaluate_lead_score(db, "lead-1")

    assert result["score"] == 88.0
    assert len(result["reasons"]) == 3


@pytest.mark.asyncio
async def test_evaluate_lead_score_not_found():
    repo: Any = AIRepository()
    repo.get_lead = AsyncMock(return_value=None)
    service = AIDomainService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(NotFoundError):
        await service.evaluate_lead_score(db, "missing")


@pytest.mark.asyncio
async def test_batch_lead_scoring_counts():
    repo: Any = AIRepository()
    repo.list_all_leads = AsyncMock(return_value=[_make_lead(), _make_lead(id="lead-2")])
    service = AIDomainService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.batch_lead_scoring(db)

    assert result["processed_count"] == 2


@pytest.mark.asyncio
async def test_generate_email_requires_prompt():
    service = AIDomainService()
    with pytest.raises(APIException):
        await service.generate_email(AIGenerateEmailRequest(prompt=""))


@pytest.mark.asyncio
async def test_generate_email_interpolates_prompt():
    service = AIDomainService()
    result = await service.generate_email(AIGenerateEmailRequest(prompt="scaling sales"))
    assert "scaling sales" in result["body"]
    assert result["subject"]


@pytest.mark.asyncio
async def test_predict_deal_forecast_defaults():
    repo: Any = AIRepository()
    repo.get_deal = AsyncMock(return_value=_make_deal(amount=None, probability=None))
    service = AIDomainService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.predict_deal_forecast(db, "deal-1")

    assert result["predicted_revenue"] == 0.0
    assert result["confidence_percentage"] == 50.0


@pytest.mark.asyncio
async def test_suggest_next_best_action_deal_missing():
    repo: Any = AIRepository()
    repo.get_deal = AsyncMock(return_value=None)
    service = AIDomainService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(NotFoundError):
        await service.suggest_next_best_action(db, "deal", "missing")


@pytest.mark.asyncio
async def test_evaluate_icp_match():
    repo: Any = AIRepository()
    repo.get_lead = AsyncMock(return_value=_make_lead(score=90.0))
    service = AIDomainService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.evaluate_icp_match(db, "lead-1")

    assert result["icp_fit_percentage"] == 90.0
    assert result["fit_tier"] == "Tier 1"


@pytest.mark.asyncio
async def test_predict_churn_risk_not_found():
    repo: Any = AIRepository()
    repo.get_company = AsyncMock(return_value=None)
    service = AIDomainService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(NotFoundError):
        await service.predict_churn_risk(db, "missing")


@pytest.mark.asyncio
async def test_optimize_pricing():
    repo: Any = AIRepository()
    repo.get_deal = AsyncMock(return_value=_make_deal())
    service = AIDomainService(repository=repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.optimize_pricing(db, "deal-1")

    assert result["recommended_discount_pct"] == 5.0


@pytest.mark.asyncio
async def test_list_ai_models():
    result = await AIDomainService().list_ai_models()
    assert result[0]["model_id"] == "gpt-4o"


@pytest.mark.asyncio
async def test_suggest_objection_handling_requires_text():
    with pytest.raises(APIException):
        await AIDomainService().suggest_objection_handling("")
