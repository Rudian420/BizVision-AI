"""
API ↔ `ml.pricing` schema translation.

Pure Python, zero heavy ML imports — same architectural seam as
`backend/src/services/recruitment/ml_translation.py`. The backend speaks
**Pydantic schemas** (`src.api.v1.schemas.pricing`); the ML package speaks
**frozen dataclasses** (`ml.pricing.data.schema`); this module is the
*only* place that knows about both.

Pricing has four endpoints (`/optimize` · `/simulate` · `/elasticity` ·
`/scenarios`) so the translation surface is wider than recruitment's. We
provide one function per direction per endpoint and keep them pure
(no I/O, no module-level imports of `ml.pricing.models.*`).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from src.api.v1.schemas.common import SHAPFeature
from src.api.v1.schemas.pricing import (
    ElasticityAnalysisRequest,
    ElasticityAnalysisResponse,
    MonteCarloSimulationRequest,
    MonteCarloSimulationResponse,
    PriceOptimizationRequest,
    PriceOptimizationResponse,
    PricePoint,
    ScenarioComparisonRequest,
    ScenarioComparisonResponse,
)

if TYPE_CHECKING:
    # Imports for type-checker only — keeps this module importable in the
    # backend's lean runtime image where ml/ may not be on sys.path.
    from ml.pricing.data.schema import (
        MonteCarloConfig as MLMonteCarloConfig,
    )
    from ml.pricing.data.schema import (
        PriceObservation as MLPriceObservation,
    )
    from ml.pricing.data.schema import (
        PriceRecommendation as MLPriceRecommendation,
    )
    from ml.pricing.data.schema import (
        Product as MLProduct,
    )
    from ml.pricing.models.monte_carlo import MonteCarloResult


# ── API → ml.pricing ────────────────────────────────────────────────


def api_product_from_optimize(request: PriceOptimizationRequest) -> MLProduct:
    """Build an `ml.pricing.Product` from a `/optimize` request."""
    from ml.pricing.data.schema import Product as MLProductImpl

    return MLProductImpl(
        product_id=request.product_id,
        category=None,
        unit_cost=float(request.unit_cost),
        current_price=float(request.current_price),
        competitor_prices=tuple(float(p) for p in request.competitor_prices),
        seasonal_factor=1.0,
    )


def api_product_from_scenarios(request: ScenarioComparisonRequest) -> MLProduct:
    """Build an `ml.pricing.Product` from a `/scenarios` request.

    The scenarios endpoint doesn't carry an explicit competitor list, so
    we leave the tuple empty; the policy falls back to its training-time
    competitor signal."""
    from ml.pricing.data.schema import Product as MLProductImpl

    return MLProductImpl(
        product_id=request.product_id,
        unit_cost=float(request.unit_cost),
        current_price=float(request.current_price),
    )


def api_observations_from_elasticity(
    request: ElasticityAnalysisRequest,
) -> list[MLPriceObservation]:
    """Pair `(price_points, observed_demand)` into `PriceObservation` rows.

    Validates the array lengths match — if they don't we raise a
    ValueError that the service turns into a 422."""
    from ml.pricing.data.schema import PriceObservation as MLObsImpl

    prices = list(request.price_points)
    demand = list(request.observed_demand)
    if len(prices) != len(demand):
        raise ValueError(
            f"price_points ({len(prices)}) and observed_demand " f"({len(demand)}) length mismatch"
        )
    return [
        MLObsImpl(
            product_id=request.product_id,
            price=float(p),
            demand=float(d),
        )
        for p, d in zip(prices, demand, strict=False)
    ]


def api_monte_carlo_config(request: MonteCarloSimulationRequest) -> MLMonteCarloConfig:
    """Build the simulator config from the API request."""
    from ml.pricing.data.schema import MonteCarloConfig as MLMCConfig

    return MLMCConfig(
        product_id=request.product_id,
        candidate_price=float(request.candidate_price),
        unit_cost=float(request.unit_cost),
        demand_mean=float(request.demand_mean),
        demand_std=float(request.demand_std),
        num_trials=int(request.num_trials),
        seed=None,
    )


# ── ml.pricing → API ────────────────────────────────────────────────


def ml_recommendation_to_api(
    *,
    recommendation: MLPriceRecommendation,
    request: PriceOptimizationRequest,
    analysis_id: UUID | None = None,
    timestamp: datetime | None = None,
) -> PriceOptimizationResponse:
    """Translate `PriceRecommendation` → `PriceOptimizationResponse`."""
    revenue_curve = [
        PricePoint(
            price=float(pp.price),
            expected_demand=float(pp.expected_demand),
            expected_revenue=float(pp.expected_revenue),
            expected_profit=float(pp.expected_profit),
        )
        for pp in recommendation.revenue_curve
    ]

    # Uplift vs the current price's expected revenue, computed from the
    # ranked curve when present. Falls back to 0.0 when the curve is empty
    # (e.g. PPO arm).
    current_revenue = _current_revenue_from_curve(
        revenue_curve, current_price=float(request.current_price)
    )
    if current_revenue and recommendation.expected_revenue:
        uplift = (recommendation.expected_revenue - current_revenue) / current_revenue
    else:
        uplift = 0.0

    return PriceOptimizationResponse(
        analysis_id=analysis_id or uuid4(),
        product_id=request.product_id,
        analysis_timestamp=timestamp or datetime.now(timezone.utc),
        recommended_price=round(float(recommendation.recommended_price), 4),
        current_price=float(request.current_price),
        expected_revenue_uplift=round(float(uplift), 4),
        confidence_interval=[
            round(float(recommendation.confidence_interval[0]), 4),
            round(float(recommendation.confidence_interval[1]), 4),
        ],
        revenue_curve=revenue_curve,
        top_shap_features=[
            SHAPFeature(
                feature_name=name,
                shap_value=round(float(value), 4),
                feature_value=round(float(value), 4),
                contribution_direction="positive" if value >= 0 else "negative",
                importance_rank=rank,
            )
            for rank, (name, value) in enumerate(recommendation.sub_scores.items(), start=1)
        ],
        top_lime_features=[
            SHAPFeature(
                feature_name=name,
                shap_value=round(float(value), 4),
                feature_value=round(float(value), 4),
                contribution_direction="positive" if value >= 0 else "negative",
                importance_rank=rank,
            )
            for rank, (name, value) in enumerate(
                # `lime_attributions` may be absent on stub mock records
                # built outside the LightGBMGridPolicy path; default to
                # empty so the response shape stays stable.
                getattr(recommendation, "lime_attributions", {}).items(),
                start=1,
            )
        ],
        ai_rationale=recommendation.rationale or "",
    )


def ml_monte_carlo_to_api(
    *,
    result: MonteCarloResult,
    request: MonteCarloSimulationRequest,
    analysis_id: UUID | None = None,
) -> MonteCarloSimulationResponse:
    """Translate `MonteCarloResult` → `MonteCarloSimulationResponse`."""
    return MonteCarloSimulationResponse(
        analysis_id=analysis_id or uuid4(),
        product_id=request.product_id,
        candidate_price=float(result.candidate_price),
        num_trials=int(result.num_trials),
        mean_revenue=round(float(result.mean_revenue), 4),
        revenue_p5=round(float(result.revenue_p5), 4),
        revenue_p50=round(float(result.revenue_p50), 4),
        revenue_p95=round(float(result.revenue_p95), 4),
        value_at_risk_5pct=round(float(result.value_at_risk_5pct), 4),
        probability_of_profit=round(float(result.probability_of_profit), 4),
        histogram=[dict(b) for b in result.histogram],
    )


def ml_elasticity_to_api(
    *,
    elasticity: float,
    request: ElasticityAnalysisRequest,
    analysis_id: UUID | None = None,
) -> ElasticityAnalysisResponse:
    """Translate an estimated elasticity scalar → API response."""
    lo = float(min(request.price_points))
    hi = float(max(request.price_points))
    is_elastic = abs(elasticity) > 1
    interpretation = (
        "Demand is elastic — small price increases reduce revenue."
        if is_elastic
        else "Demand is inelastic — there is room to raise price."
    )
    return ElasticityAnalysisResponse(
        analysis_id=analysis_id or uuid4(),
        product_id=request.product_id,
        elasticity_coefficient=round(float(elasticity), 4),
        is_elastic=is_elastic,
        optimal_price_zone=[round(lo * 1.05, 4), round(hi * 0.95, 4)],
        interpretation=interpretation,
    )


def ml_scenarios_to_api(
    *,
    scenarios: dict[str, MLPriceRecommendation],
    request: ScenarioComparisonRequest,
    analysis_id: UUID | None = None,
) -> ScenarioComparisonResponse:
    """Translate a dict of `{scenario_label: PriceRecommendation}` → API response."""
    points: dict[str, PricePoint] = {}
    for label, rec in scenarios.items():
        demand = float(rec.expected_demand or 0.0)
        price = float(rec.recommended_price)
        points[label] = PricePoint(
            price=round(price, 4),
            expected_demand=round(demand, 4),
            expected_revenue=round(price * demand, 4),
            expected_profit=round((price - float(request.unit_cost)) * demand, 4),
        )

    if not points:
        raise ValueError("scenarios cannot be empty")

    best_label = max(points, key=lambda k: points[k].expected_revenue)
    rationale = f"'{best_label}' maximises expected revenue under the demand model."
    return ScenarioComparisonResponse(
        analysis_id=analysis_id or uuid4(),
        product_id=request.product_id,
        scenarios=points,
        recommended_scenario=best_label,
        rationale=rationale,
    )


# ── helpers ─────────────────────────────────────────────────────────


def _current_revenue_from_curve(curve: list[PricePoint], *, current_price: float) -> float:
    """Find the curve point nearest the current price; return its revenue.

    Returns 0.0 when the curve is empty (e.g. policies that don't emit a
    grid — the PPO arm in some configurations)."""
    if not curve or current_price <= 0:
        return 0.0
    nearest = min(curve, key=lambda p: abs(p.price - current_price))
    return float(nearest.expected_revenue)
