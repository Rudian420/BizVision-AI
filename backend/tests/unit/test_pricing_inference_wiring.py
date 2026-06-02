"""Offline tests for the pricing inference orchestrator.

Verifies the wiring (request translation → policy call → response
translation) for all four endpoints without booting any heavy ML
backbone. We inject a hand-rolled `PricingPolicy` stub and use the
real `MonteCarloSimulator` + `ConstantElasticityEstimator` (both pure
numpy).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

pytest.importorskip("ml.pricing.models.base")

from ml.pricing.data.schema import (  # noqa: E402
    PriceRecommendation as MLPriceRecommendation,
)
from ml.pricing.models.base import PricingPolicy  # noqa: E402
from src.api.v1.schemas.pricing import (  # noqa: E402
    ElasticityAnalysisRequest,
    MonteCarloSimulationRequest,
    PriceOptimizationRequest,
    ScenarioComparisonRequest,
)
from src.services.pricing.inference import (  # noqa: E402
    PricingInferenceClient,
    get_inference_client,
    reset_inference_client,
)

# ── Stub policy — returns a deterministic recommendation ────────────


class StubPricingPolicy(PricingPolicy):
    """Deterministic policy: recommends current_price × 1.05; demand = 100."""

    requires_training = False

    @property
    def name(self) -> str:
        return "stub-pricing-policy"

    def fit(self, observations):
        return self

    def recommend_price(self, product, context=None):
        recommended = float(product.current_price) * 1.05
        return MLPriceRecommendation(
            product_id=product.product_id,
            recommended_price=recommended,
            expected_revenue=recommended * 100.0,
            expected_demand=100.0,
            confidence_interval=(recommended * 0.95, recommended * 1.05),
            revenue_curve=(),
            sub_scores={"stub_signal": 0.5},
            rationale=f"stub@{recommended:.2f}",
        )


# ── Request factories ──────────────────────────────────────────────


def _optimize_request() -> PriceOptimizationRequest:
    return PriceOptimizationRequest(
        product_id="sku-001",
        current_price=20.0,
        unit_cost=7.5,
        historical_demand=[100.0, 110.0],
        competitor_prices=[21.0],
        objective="revenue",
    )


def _mc_request() -> MonteCarloSimulationRequest:
    return MonteCarloSimulationRequest(
        product_id="sku-001",
        candidate_price=22.0,
        unit_cost=7.5,
        demand_mean=120.0,
        demand_std=12.0,
        num_trials=1_000,
    )


def _elasticity_request() -> ElasticityAnalysisRequest:
    """Synthetic `demand = 1000 / price^1.5` — true elasticity ≈ -1.5."""
    prices = [10.0, 15.0, 20.0, 25.0, 30.0]
    demands = [1000.0 / (p**1.5) for p in prices]
    return ElasticityAnalysisRequest(
        product_id="sku-001",
        price_points=prices,
        observed_demand=demands,
    )


def _scenarios_request() -> ScenarioComparisonRequest:
    return ScenarioComparisonRequest(
        product_id="sku-001",
        current_price=20.0,
        unit_cost=7.5,
        demand_mean=120.0,
    )


# ── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _clear_client():
    reset_inference_client(None)
    yield
    reset_inference_client(None)


# ── recommend_price ────────────────────────────────────────────────


def test_recommend_price_returns_full_api_response():
    client = PricingInferenceClient(policy=StubPricingPolicy())
    response = client.recommend_price(_optimize_request())
    assert response.product_id == "sku-001"
    assert response.recommended_price == pytest.approx(21.0)
    assert response.current_price == 20.0
    # Stub returns `sub_scores={"stub_signal": 0.5}` → one SHAP feature
    assert len(response.top_shap_features) == 1
    assert response.top_shap_features[0].feature_name == "stub_signal"


def test_recommend_price_uplift_is_zero_when_curve_empty():
    """Stub returns no curve → uplift defaults to 0."""
    client = PricingInferenceClient(policy=StubPricingPolicy())
    response = client.recommend_price(_optimize_request())
    assert response.expected_revenue_uplift == 0.0
    assert response.revenue_curve == []


# ── simulate (uses the real Monte Carlo simulator) ────────────────


def test_simulate_quantile_ordering():
    """Stateless — uses the real `MonteCarloSimulator`. Quantiles must be ordered."""
    client = PricingInferenceClient(policy=StubPricingPolicy())
    response = client.simulate(_mc_request())
    assert response.revenue_p5 <= response.revenue_p50 <= response.revenue_p95
    assert response.num_trials == 1_000
    assert 0.0 <= response.probability_of_profit <= 1.0


# ── estimate_elasticity (uses the real estimator) ─────────────────


def test_estimate_elasticity_recovers_synthetic_slope_within_1pct():
    """Demand = price^-1.5 → estimator must recover ε ≈ -1.5."""
    client = PricingInferenceClient(policy=StubPricingPolicy())
    response = client.estimate_elasticity(_elasticity_request())
    assert response.elasticity_coefficient == pytest.approx(-1.5, rel=1e-2)
    assert response.is_elastic is True


# ── compare_scenarios (dispatches through the policy) ─────────────


def test_compare_scenarios_picks_revenue_winner():
    """Stub policy recommends current × 1.05; demand always 100. With the
    three multipliers (0.95, 1.08, 1.20), expected_revenue ∝ multiplier
    so 'aggressive' wins."""
    client = PricingInferenceClient(policy=StubPricingPolicy())
    response = client.compare_scenarios(_scenarios_request())
    assert response.recommended_scenario == "aggressive"
    assert set(response.scenarios.keys()) == {"conservative", "optimal", "aggressive"}


# ── Singleton behaviour ────────────────────────────────────────────


def test_get_inference_client_is_singleton():
    a = get_inference_client()
    b = get_inference_client()
    assert a is b


def test_reset_inference_client_replaces_singleton():
    sentinel = PricingInferenceClient(policy=StubPricingPolicy())
    reset_inference_client(sentinel)
    assert get_inference_client() is sentinel


def test_injected_policy_does_not_change_source():
    """Source stays `uninitialised` when a policy is injected — the
    MLflow / bootstrap loader is never invoked."""
    client = PricingInferenceClient(policy=StubPricingPolicy())
    client.recommend_price(_optimize_request())
    assert client.source == "uninitialised"
