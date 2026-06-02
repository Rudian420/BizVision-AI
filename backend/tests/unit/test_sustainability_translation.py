"""Offline tests for the sustainability API↔ml.sustainability translation layer.

Pure-Python — no DB, no FastAPI fixtures. Verifies that the schema
translation preserves the per-pillar scores, maps the ML risk string
to the API enum, builds SHAPFeatures from the model's top_features
tuple, and wraps the carbon estimate cleanly.

Mirrors `test_forecasting_translation.py` (TASK-016) for the
sustainability equivalent (TASK-018).
"""

from __future__ import annotations

import sys
from pathlib import Path
from uuid import uuid4

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

pytest.importorskip("ml.sustainability.data.schema")

from ml.sustainability.data.schema import (  # noqa: E402
    CarbonEstimate,
    ESGScoreResult,
    PillarScore,
)
from src.api.v1.schemas.common import RiskLevel  # noqa: E402
from src.api.v1.schemas.sustainability import (  # noqa: E402
    CarbonEstimateRequest,
    ESGScoreRequest,
)
from src.services.sustainability.ml_translation import (  # noqa: E402
    api_company_profile_from_score,
    ml_carbon_to_api,
    ml_score_to_api,
)


def _score_request(
    industry: str = "technology",
    annual_revenue: float = 5_000_000.0,
) -> ESGScoreRequest:
    return ESGScoreRequest(
        company_name="Acme Corp",
        industry=industry,
        annual_revenue=annual_revenue,
        employee_count=42,
        environmental_indicators={"energy_efficiency": 0.7, "waste_diversion": 0.55},
        social_indicators={"dei_index": 0.6, "labor_compliance": 0.8},
        governance_indicators={"board_independence": 0.7, "transparency": 0.65},
    )


def _ml_result(
    *,
    industry: str = "technology",
    pillars: tuple[float, float, float] = (72.0, 65.0, 60.0),
    risk_level: str = "medium",
    top_features: tuple[tuple[str, float], ...] = (
        ("env_mean", 1.4),
        ("industry_technology", -0.8),
    ),
    model_name: str = "LinearLogisticMultiLabel",
) -> ESGScoreResult:
    return ESGScoreResult(
        company_name="Acme Corp",
        industry=industry,
        pillar_scores=PillarScore(
            environmental=pillars[0], social=pillars[1], governance=pillars[2]
        ),
        risk_level=risk_level,
        industry_percentile=70.0,
        label_probabilities={
            "env_strong": 0.85,
            "soc_strong": 0.7,
            "gov_strong": 0.55,
        },
        top_features=top_features,
        model_name=model_name,
        rationale="Linear logistic — composite 65.7.",
    )


# ── api_company_profile_from_score ─────────────────────────────────


def test_company_profile_passes_through_indicators():
    request = _score_request()
    profile = api_company_profile_from_score(request)
    assert profile.company_name == "Acme Corp"
    assert profile.industry == "technology"
    assert profile.environmental_indicators == request.environmental_indicators
    assert profile.social_indicators == request.social_indicators
    assert profile.governance_indicators == request.governance_indicators
    assert profile.annual_revenue == 5_000_000.0
    assert profile.employee_count == 42


def test_company_profile_handles_empty_indicators():
    request = ESGScoreRequest(
        company_name="X",
        industry="retail",
        annual_revenue=1.0,
        employee_count=1,
    )
    profile = api_company_profile_from_score(request)
    assert profile.environmental_indicators == {}
    assert profile.social_indicators == {}
    assert profile.governance_indicators == {}


# ── ml_score_to_api ────────────────────────────────────────────────


def test_score_response_preserves_per_pillar_scores():
    request = _score_request()
    result = _ml_result(pillars=(72.0, 65.0, 60.0))
    response = ml_score_to_api(result=result, request=request)
    assert response.sub_scores.environmental == 72.0
    assert response.sub_scores.social == 65.0
    assert response.sub_scores.governance == 60.0
    assert response.composite_score == pytest.approx((72 + 65 + 60) / 3, abs=0.1)


def test_score_response_maps_risk_string_to_enum():
    request = _score_request()
    for ml_str, expected in [
        ("low", RiskLevel.LOW),
        ("medium", RiskLevel.MEDIUM),
        ("high", RiskLevel.HIGH),
        ("critical", RiskLevel.CRITICAL),
    ]:
        response = ml_score_to_api(
            result=_ml_result(risk_level=ml_str), request=request
        )
        assert response.risk_level == expected


def test_score_response_unknown_risk_falls_back_to_medium():
    """Defensive fallback — the ML package might emit a new risk label
    before the API schema is bumped."""
    request = _score_request()
    response = ml_score_to_api(
        result=_ml_result(risk_level="extreme-novel"), request=request
    )
    assert response.risk_level == RiskLevel.MEDIUM


def test_score_response_regulatory_risk_flag_tracks_risk_level():
    """flag is True iff risk in {HIGH, CRITICAL}."""
    request = _score_request()
    for ml_str, expected_flag in [
        ("low", False),
        ("medium", False),
        ("high", True),
        ("critical", True),
    ]:
        response = ml_score_to_api(
            result=_ml_result(risk_level=ml_str), request=request
        )
        assert response.regulatory_risk_flag is expected_flag


def test_score_response_top_features_become_shap_drivers():
    request = _score_request()
    result = _ml_result(
        top_features=(
            ("env_mean", 1.2),  # positive
            ("industry_tech", -0.8),  # negative
            ("log_revenue", 0.3),  # positive
        )
    )
    response = ml_score_to_api(result=result, request=request)
    names = [f.feature_name for f in response.top_shap_features]
    assert names == ["env_mean", "industry_tech", "log_revenue"]
    directions = [f.contribution_direction for f in response.top_shap_features]
    assert directions == ["positive", "negative", "positive"]
    # importance rank should follow tuple order
    ranks = [f.importance_rank for f in response.top_shap_features]
    assert ranks == [1, 2, 3]


def test_score_response_empty_top_features_falls_back_to_model_driver():
    """If the ML package returns no top_features, surface a single
    `model` driver so the response always has ≥1 entry — matches the
    forecasting NaiveLast fallback posture."""
    request = _score_request()
    result = _ml_result(top_features=())
    response = ml_score_to_api(result=result, request=request)
    assert len(response.top_shap_features) == 1
    assert response.top_shap_features[0].feature_name == "model"


def test_score_response_model_version_comes_from_ml_result():
    request = _score_request()
    result = _ml_result(model_name="LinearLogisticMultiLabel-v2")
    response = ml_score_to_api(result=result, request=request)
    assert response.model_version == "LinearLogisticMultiLabel-v2"


# ── TASK-047 / FE-016 wave 2: LIME attribution plumbing ──────────────


def test_score_response_emits_lime_features_in_insertion_order():
    """`ESGScoreResult.lime_attributions` (tuple of `(name, value)`)
    flows through `ml_score_to_api` as `top_lime_features` with
    rank derived from tuple position. The shape mirrors
    `top_shap_features` so the UI can reuse the `SHAPFeature`
    model for both panels — only the semantics differ
    (Shapley credit vs. local linear coefficient)."""
    from dataclasses import replace

    request = _score_request()
    result = replace(
        _ml_result(),
        lime_attributions=(
            ("env_mean", 0.42),
            ("renewable_energy_pct", 0.18),
            ("carbon_emissions_tco2e", -0.21),
        ),
    )
    response = ml_score_to_api(result=result, request=request)

    assert len(response.top_lime_features) == 3
    assert [f.feature_name for f in response.top_lime_features] == [
        "env_mean",
        "renewable_energy_pct",
        "carbon_emissions_tco2e",
    ]
    assert response.top_lime_features[0].importance_rank == 1
    assert response.top_lime_features[0].contribution_direction == "positive"
    assert response.top_lime_features[2].contribution_direction == "negative"
    # SHAP path is unaffected by the new field.
    assert len(response.top_shap_features) >= 1


def test_score_response_empty_lime_attributions_emits_empty_list_not_placeholder():
    """Unlike the SHAP translator (which synthesises a `model`
    placeholder driver on empty input — see
    `_shap_features_from_top_features`), the LIME translator must
    emit `[]` on empty input so the frontend can render the
    empty-state copy ("No LIME attributions returned for this
    assessment.") rather than a confusing 1-feature chart with a
    zero-magnitude bar."""
    request = _score_request()
    result = _ml_result()  # `lime_attributions` defaults to ()
    response = ml_score_to_api(result=result, request=request)
    assert response.top_lime_features == []
    # SHAP still falls back to its placeholder driver.
    assert response.top_shap_features != []


def test_score_assessment_id_is_used_when_provided():
    request = _score_request()
    fixed_id = uuid4()
    response = ml_score_to_api(
        result=_ml_result(), request=request, assessment_id=fixed_id
    )
    assert response.assessment_id == fixed_id


# ── ml_carbon_to_api ───────────────────────────────────────────────


def test_carbon_response_sums_to_total():
    request = CarbonEstimateRequest(
        industry="logistics",
        annual_revenue=2_000_000.0,
        employee_count=15,
        energy_kwh=100_000.0,
        fleet_km=250_000.0,
    )
    estimate = CarbonEstimate(
        industry="logistics",
        scope_1_tco2e=42.5,
        scope_2_tco2e=40.0,
        scope_3_tco2e=600.0,
    )
    pathways = (
        "Engage top suppliers on Scope 3 reductions",
        "Procure renewable energy (largest Scope 2 lever)",
        "Electrify or optimise fleet routing",
    )
    response = ml_carbon_to_api(
        estimate=estimate, request=request, pathways=pathways
    )
    assert response.total_tco2e == pytest.approx(42.5 + 40.0 + 600.0)
    assert response.scope_1_tco2e == 42.5
    assert response.scope_2_tco2e == 40.0
    assert response.scope_3_tco2e == 600.0


def test_carbon_response_intensity_per_revenue_is_total_over_millions():
    """intensity_per_revenue = total_tco2e / (annual_revenue / 1M)."""
    request = CarbonEstimateRequest(
        industry="retail", annual_revenue=4_000_000.0, employee_count=10
    )
    estimate = CarbonEstimate(
        industry="retail",
        scope_1_tco2e=0.0,
        scope_2_tco2e=0.0,
        scope_3_tco2e=240.0,
    )
    response = ml_carbon_to_api(estimate=estimate, request=request, pathways=())
    # 240 / 4 = 60.0 tCO2e per $1M revenue
    assert response.intensity_per_revenue == pytest.approx(60.0)


def test_carbon_response_handles_zero_revenue():
    request = CarbonEstimateRequest(
        industry="retail", annual_revenue=0.0, employee_count=10
    )
    estimate = CarbonEstimate(
        industry="retail", scope_1_tco2e=0.0, scope_2_tco2e=0.0, scope_3_tco2e=0.0
    )
    response = ml_carbon_to_api(estimate=estimate, request=request, pathways=())
    assert response.intensity_per_revenue == 0.0


def test_carbon_response_pathways_pass_through_in_order():
    request = CarbonEstimateRequest(
        industry="manufacturing", annual_revenue=1_000_000.0, employee_count=5
    )
    estimate = CarbonEstimate(
        industry="manufacturing",
        scope_1_tco2e=100.0,
        scope_2_tco2e=10.0,
        scope_3_tco2e=20.0,
    )
    pathways = ("first", "second", "third")
    response = ml_carbon_to_api(
        estimate=estimate, request=request, pathways=pathways
    )
    assert response.reduction_pathways == ["first", "second", "third"]
