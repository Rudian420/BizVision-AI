"""
BizVision AI — Smart Pricing Advisor Schemas
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from src.api.v1.schemas.common import SHAPFeature

# ── Requests ───────────────────────────────────────────────────────


class PriceOptimizationRequest(BaseModel):
    product_id: str = Field(..., description="Product/service identifier")
    current_price: float = Field(..., gt=0)
    unit_cost: float = Field(..., ge=0, description="Variable cost per unit")
    historical_demand: list[float] = Field(
        default_factory=list, description="Recent demand observations"
    )
    competitor_prices: list[float] = Field(default_factory=list)
    min_price: float | None = Field(default=None, gt=0)
    max_price: float | None = Field(default=None, gt=0)
    objective: str = Field(default="revenue", description="'revenue' | 'profit' | 'volume'")


class MonteCarloSimulationRequest(BaseModel):
    product_id: str
    candidate_price: float = Field(..., gt=0)
    unit_cost: float = Field(..., ge=0)
    demand_mean: float = Field(..., ge=0)
    demand_std: float = Field(..., ge=0)
    num_trials: int = Field(default=10_000, ge=100, le=1_000_000)


class ElasticityAnalysisRequest(BaseModel):
    product_id: str
    price_points: list[float] = Field(..., min_length=2)
    observed_demand: list[float] = Field(..., min_length=2)


class ScenarioComparisonRequest(BaseModel):
    product_id: str
    current_price: float = Field(..., gt=0)
    unit_cost: float = Field(..., ge=0)
    demand_mean: float = Field(..., ge=0)


# ── Responses ──────────────────────────────────────────────────────


class PricePoint(BaseModel):
    price: float
    expected_demand: float
    expected_revenue: float
    expected_profit: float


class PriceOptimizationResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    analysis_id: UUID
    product_id: str
    analysis_timestamp: datetime
    recommended_price: float
    current_price: float
    expected_revenue_uplift: float = Field(..., description="Fractional uplift, e.g. 0.12 = +12%")
    confidence_interval: list[float] = Field(..., description="[low, high] price band")
    revenue_curve: list[PricePoint] = Field(default_factory=list)
    top_shap_features: list[SHAPFeature] = Field(default_factory=list)
    top_lime_features: list[SHAPFeature] = Field(
        default_factory=list,
        description=(
            "Top-K LIME local linear surrogate weights for the same "
            "recommendation, in the same shape as `top_shap_features` "
            "so the UI can reuse the bar-chart component. SHAP and "
            "LIME are two independent post-hoc explainers; agreement "
            "between them is a robustness signal for the recommendation. "
            "Empty list when LIME isn't available or the model path "
            "doesn't emit it (mock fallback). TASK-044, FE-016."
        ),
    )
    ai_rationale: str = ""
    model_version: str = "pricing-lgbm-ppo-mock-0.1"


class MonteCarloSimulationResponse(BaseModel):
    analysis_id: UUID
    product_id: str
    candidate_price: float
    num_trials: int
    mean_revenue: float
    revenue_p5: float
    revenue_p50: float
    revenue_p95: float
    value_at_risk_5pct: float
    probability_of_profit: float = Field(..., ge=0.0, le=1.0)
    histogram: list[dict] = Field(default_factory=list)


class ElasticityAnalysisResponse(BaseModel):
    analysis_id: UUID
    product_id: str
    elasticity_coefficient: float
    is_elastic: bool
    optimal_price_zone: list[float] = Field(..., description="[low, high]")
    interpretation: str


class ScenarioComparisonResponse(BaseModel):
    analysis_id: UUID
    product_id: str
    scenarios: dict[str, PricePoint]
    recommended_scenario: str
    rationale: str


# ── Detail / record-view (TASK-033) ────────────────────────────────


class PricingAnalysisDetailResponse(BaseModel):
    """Persisted-row reconstruction returned by
    `GET /pricing/analyses/{analysis_id}`. Backs the audit-feed
    deep-link from TASK-033 (`reference_type='pricing_analysis'`).

    The polymorphic-table shape means the detail surfaces every
    variant uniformly: the `analysis_type` discriminator tells the UI
    which variant's response shape lives in `response_payload`. The
    front-end keys off it to choose the right renderer (price-curve
    for optimize, tornado for sensitivity, etc.).
    """

    model_config = ConfigDict(protected_namespaces=())

    analysis_id: UUID
    analysis_type: str  # discriminator: optimize / monte_carlo / elasticity / scenario_comparison
    product_id: str
    created_at: datetime

    model_version: str
    processing_time_ms: float

    # Headline columns surfaced for cheap filtering in the timeline
    # without dipping into the JSONB blobs.
    recommended_price: float | None = None
    expected_revenue_uplift: float | None = None
    num_trials_or_points: int | None = None

    # Faithful request/response payloads — the same JSONB the row
    # was written with.
    request_payload: dict
    response_payload: dict
