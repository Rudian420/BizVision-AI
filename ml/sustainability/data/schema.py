"""
ESG sustainability data schemas.

Pure dataclasses — no heavy imports. Mirrors `ml.forecasting.data.schema`
and `ml.pricing.data.schema` so the cross-module pattern stays
recognisable: every package's `data` sub-module holds frozen
dataclasses; loaders produce a `*Dataset` container; downstream code
consumes these without dragging in pandas / numpy at import time.

The shape mirrors the API contract (`src.api.v1.schemas.sustainability`)
one-to-one so the backend translation layer is a thin field rename —
same posture as forecasting (TASK-016) and pricing (TASK-011).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class CompanyProfile:
    """One company under ESG assessment.

    Indicator dicts use the 0..1 self-reported scale the API exposes;
    the feature builder normalises into model-ready vectors.
    """

    company_name: str
    industry: str
    annual_revenue: float
    employee_count: int
    environmental_indicators: dict[str, float] = field(default_factory=dict)
    social_indicators: dict[str, float] = field(default_factory=dict)
    governance_indicators: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class ESGLabel:
    """Per-pillar binary labels — one row per (company, pillar).

    The multi-label classifier outputs the joint probability of (E, S, G)
    each being "strong" (≥ 60th-percentile industry-relative score). The
    composite score is a downstream aggregate, NOT the prediction target.
    """

    company_id: str
    env_strong: bool
    soc_strong: bool
    gov_strong: bool


@dataclass(frozen=True)
class ESGObservation:
    """One (profile, label) training pair."""

    profile: CompanyProfile
    label: ESGLabel


@dataclass(frozen=True)
class ESGDataset:
    """Training pool — observations + the industry catalog used for
    group-fairness audits (`fairness/auditor.py`)."""

    observations: tuple[ESGObservation, ...]
    industries: tuple[str, ...]

    def __len__(self) -> int:
        return len(self.observations)


@dataclass(frozen=True)
class PillarScore:
    """Per-pillar continuous score in [0, 100] — mirrors the API."""

    environmental: float
    social: float
    governance: float

    @property
    def composite(self) -> float:
        return (self.environmental + self.social + self.governance) / 3.0


@dataclass(frozen=True)
class ESGScoreResult:
    """Structured output of an `ESGScorer.score` call.

    Mirrors what the backend translation layer will wrap into the
    `/sustainability/score` Pydantic response — same posture as
    `ForecastResult` / `PriceRecommendation`.

    `top_features` carries the SHAP closed-form attributions for the
    environmental pillar (today's only path), per
    `explainability.shap_adapter`. `lime_attributions` carries a
    second, independent explainer view (TASK-047 / FE-016 wave 2)
    when the scorer is wired with a LIME adapter — empty otherwise.
    Both are kept as plain tuples / dicts so downstream translators
    stay decoupled from the explainer implementations.
    """

    company_name: str
    industry: str
    pillar_scores: PillarScore
    risk_level: str
    industry_percentile: float
    label_probabilities: dict[str, float]
    top_features: tuple[tuple[str, float], ...] = ()
    lime_attributions: tuple[tuple[str, float], ...] = ()
    model_name: str = ""
    rationale: str = ""


@dataclass(frozen=True)
class CarbonEstimate:
    """Scope 1/2/3 emissions decomposition for a single company."""

    industry: str
    scope_1_tco2e: float
    scope_2_tco2e: float
    scope_3_tco2e: float

    @property
    def total_tco2e(self) -> float:
        return self.scope_1_tco2e + self.scope_2_tco2e + self.scope_3_tco2e
