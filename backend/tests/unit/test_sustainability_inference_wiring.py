"""Offline tests for the sustainability inference orchestrator.

Verifies the wiring (request translation → scorer call → response
translation) for both model-backed endpoints without booting any
heavy ML backbone. We inject hand-rolled scorer + carbon model stubs;
`/simulate`, `/recommendations`, and `/benchmarks/{industry}` are
closed-form and live in the service layer.

Mirrors `test_forecasting_inference_wiring.py` (TASK-016) for the
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

pytest.importorskip("ml.sustainability.models.base")

from ml.sustainability.data.schema import (  # noqa: E402
    CarbonEstimate,
    ESGScoreResult,
    PillarScore,
)
from ml.sustainability.models.base import ESGScorer  # noqa: E402
from src.api.v1.schemas.common import RiskLevel  # noqa: E402
from src.api.v1.schemas.sustainability import (  # noqa: E402
    CarbonEstimateRequest,
    ESGScoreRequest,
)
from src.services.sustainability.inference import (  # noqa: E402
    SustainabilityInferenceClient,
    get_inference_client,
    reset_inference_client,
)

# ── Stub scorer — deterministic, no real fit ────────────────────────


class StubScorer(ESGScorer):
    """Predicts fixed per-pillar scores; sentinel for tests."""

    requires_training = False

    def __init__(
        self,
        *,
        env: float = 70.0,
        soc: float = 60.0,
        gov: float = 50.0,
        risk: str = "medium",
        top_features: tuple[tuple[str, float], ...] = (
            ("env_mean", 1.0),
            ("industry_technology", 0.5),
        ),
    ) -> None:
        self.env = env
        self.soc = soc
        self.gov = gov
        self.risk = risk
        self.top_features = top_features
        self.last_profile = None

    @property
    def name(self) -> str:
        return "StubScorer"

    def fit(self, observations):
        return self

    def score(self, profile):
        self.last_profile = profile
        return ESGScoreResult(
            company_name=profile.company_name,
            industry=profile.industry,
            pillar_scores=PillarScore(self.env, self.soc, self.gov),
            risk_level=self.risk,
            industry_percentile=65.0,
            label_probabilities={"env_strong": 0.8, "soc_strong": 0.6, "gov_strong": 0.4},
            top_features=self.top_features,
            model_name=self.name,
        )


class StubCarbonModel:
    """Returns a sentinel CarbonEstimate so the wiring is testable
    without instantiating the real model."""

    def __init__(
        self,
        *,
        scope_1: float = 50.0,
        scope_2: float = 80.0,
        scope_3: float = 300.0,
        pathways: tuple[str, ...] = ("first", "second", "third"),
    ) -> None:
        self.scope_1 = scope_1
        self.scope_2 = scope_2
        self.scope_3 = scope_3
        self.pathways = pathways
        self.last_kwargs: dict | None = None

    def predict(
        self,
        *,
        industry: str,
        annual_revenue: float,
        energy_kwh: float | None = None,
        fleet_km: float | None = None,
    ) -> CarbonEstimate:
        self.last_kwargs = {
            "industry": industry,
            "annual_revenue": annual_revenue,
            "energy_kwh": energy_kwh,
            "fleet_km": fleet_km,
        }
        return CarbonEstimate(
            industry=industry,
            scope_1_tco2e=self.scope_1,
            scope_2_tco2e=self.scope_2,
            scope_3_tco2e=self.scope_3,
        )

    def reduction_pathways(self, estimate) -> tuple[str, ...]:
        return self.pathways


def _score_request() -> ESGScoreRequest:
    return ESGScoreRequest(
        company_name="Acme",
        industry="technology",
        annual_revenue=5_000_000.0,
        employee_count=42,
        environmental_indicators={"a": 0.7},
        social_indicators={"a": 0.6},
        governance_indicators={"a": 0.55},
    )


def _carbon_request() -> CarbonEstimateRequest:
    return CarbonEstimateRequest(
        industry="logistics",
        annual_revenue=2_000_000.0,
        employee_count=15,
        energy_kwh=100_000.0,
        fleet_km=250_000.0,
    )


@pytest.fixture(autouse=True)
def reset_singleton():
    reset_inference_client(None)
    yield
    reset_inference_client(None)


# ── calculate_score ─────────────────────────────────────────────────


def test_score_uses_injected_scorer_and_translates_pillars():
    scorer = StubScorer(env=72.0, soc=64.0, gov=56.0, risk="medium")
    client = SustainabilityInferenceClient(scorer=scorer)
    response = client.calculate_score(_score_request())

    assert response.sub_scores.environmental == 72.0
    assert response.sub_scores.social == 64.0
    assert response.sub_scores.governance == 56.0
    assert response.composite_score == pytest.approx((72 + 64 + 56) / 3, abs=0.1)
    assert response.risk_level == RiskLevel.MEDIUM
    assert response.model_version == "StubScorer"
    # SHAP features pass through with correct order + direction
    names = [f.feature_name for f in response.top_shap_features]
    assert names == ["env_mean", "industry_technology"]


def test_score_passes_profile_with_indicators_to_scorer():
    """The translation layer must convert the API request's indicator
    dicts into the ML CompanyProfile — the stub records the call to
    let us verify."""
    scorer = StubScorer()
    client = SustainabilityInferenceClient(scorer=scorer)
    client.calculate_score(_score_request())

    assert scorer.last_profile is not None
    assert scorer.last_profile.industry == "technology"
    assert scorer.last_profile.environmental_indicators == {"a": 0.7}
    assert scorer.last_profile.employee_count == 42


def test_score_high_risk_triggers_regulatory_flag():
    scorer = StubScorer(env=30.0, soc=25.0, gov=20.0, risk="high")
    client = SustainabilityInferenceClient(scorer=scorer)
    response = client.calculate_score(_score_request())
    assert response.regulatory_risk_flag is True


def test_score_assessment_id_round_trip():
    scorer = StubScorer()
    client = SustainabilityInferenceClient(scorer=scorer)
    fixed_id = uuid4()
    response = client.calculate_score(_score_request(), assessment_id=fixed_id)
    assert response.assessment_id == fixed_id


# ── estimate_carbon ─────────────────────────────────────────────────


def test_carbon_uses_injected_model_and_translates_response():
    carbon = StubCarbonModel(scope_1=40.0, scope_2=60.0, scope_3=200.0)
    client = SustainabilityInferenceClient(carbon_model=carbon)
    response = client.estimate_carbon(_carbon_request())

    assert response.scope_1_tco2e == 40.0
    assert response.scope_2_tco2e == 60.0
    assert response.scope_3_tco2e == 200.0
    assert response.total_tco2e == 300.0
    # 300 / 2 = 150 tCO2e per $1M revenue
    assert response.intensity_per_revenue == pytest.approx(150.0)
    assert response.reduction_pathways == ["first", "second", "third"]


def test_carbon_forwards_request_payload_to_model():
    """The inference client must pass through `industry`, revenue,
    `energy_kwh`, `fleet_km` to the carbon model unchanged."""
    carbon = StubCarbonModel()
    client = SustainabilityInferenceClient(carbon_model=carbon)
    client.estimate_carbon(_carbon_request())

    assert carbon.last_kwargs == {
        "industry": "logistics",
        "annual_revenue": 2_000_000.0,
        "energy_kwh": 100_000.0,
        "fleet_km": 250_000.0,
    }


def test_carbon_handles_omitted_energy_and_fleet():
    """`energy_kwh` and `fleet_km` are Optional; client must pass None
    through (model is expected to default them)."""
    carbon = StubCarbonModel()
    client = SustainabilityInferenceClient(carbon_model=carbon)
    request = CarbonEstimateRequest(
        industry="retail", annual_revenue=1_000_000.0, employee_count=5
    )
    client.estimate_carbon(request)
    assert carbon.last_kwargs["energy_kwh"] is None
    assert carbon.last_kwargs["fleet_km"] is None


# ── source tracking + singleton ─────────────────────────────────────


def test_source_is_uninitialised_when_factory_injected():
    """Injection-path clients never run the registry/bootstrap loader."""
    client = SustainabilityInferenceClient(scorer=StubScorer())
    _ = client.calculate_score(_score_request())
    assert client.source == "uninitialised"


def test_get_inference_client_returns_same_singleton_per_process():
    a = get_inference_client()
    b = get_inference_client()
    assert a is b


def test_reset_inference_client_replaces_singleton():
    a = get_inference_client()
    reset_inference_client(None)
    b = get_inference_client()
    assert a is not b


def test_get_inference_client_returns_uninitialised_until_used():
    """Singleton construction is cheap; source stays 'uninitialised'
    until calculate_score / estimate_carbon trigger lazy load."""
    client = get_inference_client()
    assert client.source == "uninitialised"
