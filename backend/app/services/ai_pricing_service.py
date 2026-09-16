from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from app.core.config import settings


class PricingStatus(StrEnum):
    KNOWN = "known"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class PricingCalculation:
    status: PricingStatus
    estimated_cost: float
    version: str | None
    currency: str | None


class AIModelPricingRegistry:
    """Deployment-owned pricing registry; unknown prices remain explicitly unknown."""

    def calculate(
        self, *, provider: str, model: str, input_tokens: int, output_tokens: int
    ) -> PricingCalculation:
        try:
            catalog = json.loads(settings.AI_MODEL_PRICING_JSON or "{}")
        except (TypeError, ValueError):
            catalog = {}
        entry = catalog.get(provider, {}).get(model) if isinstance(catalog, dict) else None
        if not isinstance(entry, dict):
            return PricingCalculation(PricingStatus.UNKNOWN, 0.0, None, None)
        try:
            input_price = float(entry["input_per_million"])
            output_price = float(entry["output_per_million"])
            currency = str(entry.get("currency", "USD")).upper()
            effective_date = date.fromisoformat(str(entry["effective_date"]))
        except (KeyError, TypeError, ValueError):
            return PricingCalculation(PricingStatus.UNKNOWN, 0.0, None, None)
        if (
            not math.isfinite(input_price)
            or not math.isfinite(output_price)
            or input_price < 0
            or output_price < 0
            or currency != "USD"
        ):
            return PricingCalculation(PricingStatus.UNKNOWN, 0.0, None, None)
        cost = (input_tokens * input_price + output_tokens * output_price) / 1_000_000
        return PricingCalculation(
            PricingStatus.KNOWN,
            round(cost, 8),
            effective_date.isoformat(),
            currency,
        )


ai_model_pricing_registry = AIModelPricingRegistry()
