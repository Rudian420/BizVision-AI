"""Offline tests for the backend ↔ `ml.pricing` translation layer.

Verifies the API ↔ ML shape contract without instantiating any heavy
ML model (no LightGBM, no PPO, no SHAP). The lazy imports inside the
translation functions need the repo root on `sys.path` — added at the
top of the file. Pure-numpy via `ml.pricing.data.schema` dataclasses.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

pytest.importorskip("ml.pricing.data.schema")

from src.api.v1.schemas.pricing import (  # noqa: E402
    ElasticityAnalysisRequest,
    MonteCarloSimulationRequest,
    PriceOptimizationRequest,
    ScenarioComparisonRequest,
)
from src.services.pricing.ml_translation import (  # noqa: E402
    _current_revenue_from_curve,
    api_monte_carlo_config,
    api_observations_from_elasticity,
    api_product_from_optimize,
    api_product_from_scenarios,
    ml_elasticity_to_api,
    ml_monte_carlo_to_api,
    ml_recommendation_to_api,
    ml_scenarios_to_api,
)

# ── factories ──────────────────────────────────────────────────────


def _optimize_req(product_id: str = "sku-001") -> PriceOptimizationRequest:
    return PriceOptimizationRequest(
        product_id=product_id,
        current_price=20.0,
        unit_cost=7.5,
        historical_demand=[100.0, 110.0, 95.0],
        competitor_prices=[21.0, 22.0],
        objective="revenue",
    )


def _mc_req(product_id: str = "sku-001") -> MonteCarloSimulationRequest:
    return MonteCarloSimulationRequest(
        product_id=product_id,
        candidate_price=22.0,
        unit_cost=7.5,
        demand_mean=120.0,
        demand_std=12.0,
        num_trials=2_000,
    )


def _elasticity_req(product_id: str = "sku-001") -> ElasticityAnalysisRequest:
    return ElasticityAnalysisRequest(
        product_id=product_id,
        price_points=[10.0, 12.0, 14.0, 16.0],
        observed_demand=[200.0, 165.0, 140.0, 110.0],
    )


def _scenarios_req(product_id: str = "sku-001") -> ScenarioComparisonRequest:
    return ScenarioComparisonRequest(
        product_id=product_id,
        current_price=20.0,
        unit_cost=7.5,
        demand_mean=120.0,
    )


# ── API → ml.pricing ─────────────────────────────────────────────────


def test_api_product_from_optimize_captures_metadata():
    product = api_product_from_optimize(_optimize_req())
    assert product.product_id == "sku-001"
    assert product.current_price == 20.0
    assert product.unit_cost == 7.5
    assert product.competitor_prices == (21.0, 22.0)


def test_api_product_from_scenarios_has_no_competitors():
    """The /scenarios request has no competitor field by design."""
    product = api_product_from_scenarios(_scenarios_req())
    assert product.competitor_prices == ()
    assert product.unit_cost == 7.5
    assert product.current_price == 20.0


def test_api_observations_from_elasticity_pairs_arrays():
    obs = api_observations_from_elasticity(_elasticity_req())
    assert len(obs) == 4
    assert [o.price for o in obs] == [10.0, 12.0, 14.0, 16.0]
    assert [o.demand for o in obs] == [200.0, 165.0, 140.0, 110.0]


def test_api_observations_from_elasticity_rejects_mismatched_lengths():
    req = ElasticityAnalysisRequest(
        product_id="x",
        price_points=[10.0, 12.0, 14.0],
        observed_demand=[100.0, 80.0],
    )
    with pytest.raises(ValueError, match="length mismatch"):
        api_observations_from_elasticity(req)


def test_api_monte_carlo_config_preserves_seed_as_none():
    cfg = api_monte_carlo_config(_mc_req())
    assert cfg.product_id == "sku-001"
    assert cfg.candidate_price == 22.0
    assert cfg.num_trials == 2000
    # Seed is intentionally None — the API doesn't expose seed; the
    # simulator uses fresh randomness per request.
    assert cfg.seed is None


# ── ml.pricing → API ─────────────────────────────────────────────────


def test_ml_recommendation_to_api_computes_uplift_from_curve():
    """Uplift = (recommended_revenue - revenue_at_current_price) / revenue_at_current_price."""
    from ml.pricing.data.schema import PricePoint as MLPricePoint
    from ml.pricing.data.schema import PriceRecommendation

    curve = (
        MLPricePoint(
            price=18.0, expected_demand=110.0, expected_revenue=1980.0, expected_profit=1155.0
        ),
        MLPricePoint(
            price=20.0, expected_demand=100.0, expected_revenue=2000.0, expected_profit=1250.0
        ),
        MLPricePoint(
            price=22.0, expected_demand=90.0, expected_revenue=1980.0, expected_profit=1305.0
        ),
    )
    rec = PriceRecommendation(
        product_id="sku-001",
        recommended_price=22.0,
        expected_revenue=2200.0,
        expected_demand=100.0,
        confidence_interval=(20.9, 23.1),
        revenue_curve=curve,
        sub_scores={"elasticity": -1.4},
        rationale="elasticity=-1.4; revenue argmax in grid.",
    )
    fixed_id = UUID("11111111-1111-1111-1111-111111111111")
    response = ml_recommendation_to_api(
        recommendation=rec, request=_optimize_req(), analysis_id=fixed_id
    )
    assert response.analysis_id == fixed_id
    assert response.recommended_price == 22.0
    # Current price 20.0 → revenue 2000 (from curve nearest)
    # Recommended revenue 2200 → uplift = 0.10
    assert response.expected_revenue_uplift == pytest.approx(0.10, abs=1e-6)
    assert len(response.top_shap_features) == 1
    assert response.top_shap_features[0].feature_name == "elasticity"


def test_ml_recommendation_to_api_empty_curve_zero_uplift():
    """PPO arm sometimes returns no curve; uplift must degrade to 0."""
    from ml.pricing.data.schema import PriceRecommendation

    rec = PriceRecommendation(
        product_id="sku-001",
        recommended_price=22.0,
        expected_revenue=0.0,
        expected_demand=0.0,
        confidence_interval=(20.9, 23.1),
        revenue_curve=(),
        sub_scores={},
        rationale="PPO point recommendation.",
    )
    response = ml_recommendation_to_api(recommendation=rec, request=_optimize_req())
    assert response.expected_revenue_uplift == 0.0
    assert response.revenue_curve == []


def test_ml_monte_carlo_to_api_preserves_quantiles():
    from ml.pricing.models.monte_carlo import MonteCarloResult

    result = MonteCarloResult(
        product_id="sku-001",
        candidate_price=22.0,
        num_trials=2_000,
        mean_revenue=2640.0,
        revenue_p5=2200.0,
        revenue_p50=2640.0,
        revenue_p95=3080.0,
        value_at_risk_5pct=440.0,
        probability_of_profit=0.92,
        histogram=({"bin_low": 2000.0, "bin_high": 2200.0, "count": 100},),
        mean_profit=1740.0,
    )
    response = ml_monte_carlo_to_api(result=result, request=_mc_req())
    assert response.mean_revenue == 2640.0
    assert response.revenue_p5 == 2200.0
    assert response.probability_of_profit == 0.92


def test_ml_elasticity_to_api_threshold():
    response = ml_elasticity_to_api(elasticity=-1.4, request=_elasticity_req())
    assert response.elasticity_coefficient == -1.4
    assert response.is_elastic is True
    assert "elastic" in response.interpretation.lower()


def test_ml_elasticity_to_api_inelastic_when_abs_lt_one():
    response = ml_elasticity_to_api(elasticity=-0.7, request=_elasticity_req())
    assert response.is_elastic is False
    assert "raise" in response.interpretation.lower()


def test_ml_scenarios_to_api_picks_revenue_winner():
    """Recommended scenario = argmax expected revenue."""
    from ml.pricing.data.schema import PriceRecommendation

    scenarios = {
        "conservative": PriceRecommendation(
            product_id="x",
            recommended_price=19.0,
            expected_revenue=0.0,
            expected_demand=110.0,
            confidence_interval=(18.0, 20.0),
        ),
        "optimal": PriceRecommendation(
            product_id="x",
            recommended_price=21.6,
            expected_revenue=0.0,
            expected_demand=100.0,
            confidence_interval=(20.5, 22.7),
        ),
        "aggressive": PriceRecommendation(
            product_id="x",
            recommended_price=24.0,
            expected_revenue=0.0,
            expected_demand=80.0,
            confidence_interval=(22.8, 25.2),
        ),
    }
    response = ml_scenarios_to_api(scenarios=scenarios, request=_scenarios_req())
    # Revenue = price * demand:
    #   conservative 19.0 * 110 = 2090
    #   optimal      21.6 * 100 = 2160 ← winner
    #   aggressive   24.0 * 80  = 1920
    assert response.recommended_scenario == "optimal"
    assert "optimal" in response.rationale


def test_ml_scenarios_to_api_rejects_empty():
    with pytest.raises(ValueError, match="empty"):
        ml_scenarios_to_api(scenarios={}, request=_scenarios_req())


# ── _current_revenue_from_curve helper ──────────────────────────────


def test_current_revenue_from_curve_picks_nearest_price():
    from src.api.v1.schemas.pricing import PricePoint

    curve = [
        PricePoint(price=18.0, expected_demand=110.0, expected_revenue=1980.0, expected_profit=0.0),
        PricePoint(price=21.0, expected_demand=95.0, expected_revenue=1995.0, expected_profit=0.0),
    ]
    # Current price 20.0 is closer to 21.0 (Δ=1) than 18.0 (Δ=2) → revenue=1995
    assert _current_revenue_from_curve(curve, current_price=20.0) == 1995.0


def test_current_revenue_from_curve_empty_returns_zero():
    assert _current_revenue_from_curve([], current_price=20.0) == 0.0


def test_current_revenue_from_curve_zero_price_returns_zero():
    from src.api.v1.schemas.pricing import PricePoint

    curve = [
        PricePoint(price=10.0, expected_demand=100.0, expected_revenue=1000.0, expected_profit=0.0)
    ]
    assert _current_revenue_from_curve(curve, current_price=0.0) == 0.0


# ── Timestamp default behaviour ──────────────────────────────────────


def test_ml_recommendation_to_api_default_timestamp_is_utc_now():
    from ml.pricing.data.schema import PriceRecommendation

    rec = PriceRecommendation(
        product_id="x",
        recommended_price=20.0,
        expected_revenue=2000.0,
        expected_demand=100.0,
        confidence_interval=(19.0, 21.0),
    )
    before = datetime.now(timezone.utc)
    response = ml_recommendation_to_api(recommendation=rec, request=_optimize_req())
    after = datetime.now(timezone.utc)
    assert before <= response.analysis_timestamp <= after
    # analysis_id is generated when not supplied
    assert isinstance(response.analysis_id, UUID)


def test_caller_supplied_analysis_id_is_preserved():
    from ml.pricing.data.schema import PriceRecommendation

    rec = PriceRecommendation(
        product_id="x",
        recommended_price=20.0,
        expected_revenue=2000.0,
        expected_demand=100.0,
        confidence_interval=(19.0, 21.0),
    )
    fixed = uuid4()
    response = ml_recommendation_to_api(
        recommendation=rec, request=_optimize_req(), analysis_id=fixed
    )
    assert response.analysis_id == fixed


# ── TASK-044 / FE-016: LIME attribution plumbing ──────────────────────


def test_ml_recommendation_to_api_emits_lime_features_in_order():
    """`PriceRecommendation.lime_attributions` flows through the
    translator as `top_lime_features` with rank derived from insertion
    order. The shape mirrors `top_shap_features` so the UI can reuse
    the `SHAPFeature` model for both panels."""
    from ml.pricing.data.schema import PriceRecommendation

    rec = PriceRecommendation(
        product_id="sku-lime",
        recommended_price=20.0,
        expected_revenue=2000.0,
        expected_demand=100.0,
        confidence_interval=(19.0, 21.0),
        sub_scores={"elasticity": -1.4},
        lime_attributions={
            "competitor_price_gap": 1.85,
            "price": 0.42,
            "season_cos": -0.21,
        },
    )
    response = ml_recommendation_to_api(recommendation=rec, request=_optimize_req())

    # Both lists present, both have the right cardinality.
    assert len(response.top_shap_features) == 1
    assert len(response.top_lime_features) == 3

    # Order preserved (insertion order — `_lime_sub_scores_for_best`
    # already pre-sorts by |weight| descending, so this is what the UI
    # receives).
    names = [f.feature_name for f in response.top_lime_features]
    assert names == ["competitor_price_gap", "price", "season_cos"]

    # Ranks are 1-indexed and contribution direction follows sign.
    assert response.top_lime_features[0].importance_rank == 1
    assert response.top_lime_features[0].contribution_direction == "positive"
    assert response.top_lime_features[2].contribution_direction == "negative"


def test_ml_recommendation_to_api_lime_features_default_to_empty_list():
    """Backwards compatibility: a `PriceRecommendation` from a code
    path that doesn't populate `lime_attributions` (e.g. mock stubs,
    older test fixtures) must still translate cleanly with an empty
    `top_lime_features`."""
    from ml.pricing.data.schema import PriceRecommendation

    rec = PriceRecommendation(
        product_id="sku-no-lime",
        recommended_price=20.0,
        expected_revenue=2000.0,
        expected_demand=100.0,
        confidence_interval=(19.0, 21.0),
    )
    response = ml_recommendation_to_api(recommendation=rec, request=_optimize_req())
    assert response.top_lime_features == []
