"""
API ↔ `ml.sustainability` schema translation.

Pure Python, zero heavy ML imports — same architectural seam as
`backend/src/services/forecasting/ml_translation.py` (TASK-016) and
`backend/src/services/pricing/ml_translation.py` (TASK-011). The
backend speaks **Pydantic schemas** (`src.api.v1.schemas.sustainability`);
the ML package speaks **frozen dataclasses**
(`ml.sustainability.data.schema`); this module is the *only* place that
knows about both.

Two of the five ESG endpoints are model-backed when
`SUSTAINABILITY_USE_REAL_ML=True`:
  • `/score`           → `LinearLogisticMultiLabel.score`
  • `/carbon-estimate` → `CarbonEstimatorModel.predict`

The other three stay model-free in wave 1:
  • `/simulate`        — closed-form baseline + uplift projection
  • `/recommendations` — static catalog (copilot upgrade in wave 2)
  • `/benchmarks/{industry}` — stateless reference data
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from src.api.v1.schemas.common import RiskLevel, SHAPFeature
from src.api.v1.schemas.sustainability import (
    CarbonEstimateRequest,
    CarbonEstimateResponse,
    ESGScoreRequest,
    ESGScoreResponse,
    ESGSubScores,
)

if TYPE_CHECKING:
    # Imports for type-checker only — keeps this module importable in the
    # backend's lean runtime image where ml/ may not be on sys.path.
    from ml.sustainability.data.schema import (
        CarbonEstimate as MLCarbonEstimate,
    )
    from ml.sustainability.data.schema import (
        CompanyProfile as MLCompanyProfile,
    )
    from ml.sustainability.data.schema import (
        ESGScoreResult as MLESGScoreResult,
    )


# ── API → ml.sustainability ────────────────────────────────────────


def api_company_profile_from_score(request: ESGScoreRequest) -> MLCompanyProfile:
    """Build an `ml.sustainability.CompanyProfile` from a `/score` request."""
    from ml.sustainability.data.schema import (
        CompanyProfile as MLCompanyProfileImpl,
    )

    return MLCompanyProfileImpl(
        company_name=request.company_name,
        industry=request.industry,
        annual_revenue=float(request.annual_revenue),
        employee_count=int(request.employee_count),
        environmental_indicators=dict(request.environmental_indicators),
        social_indicators=dict(request.social_indicators),
        governance_indicators=dict(request.governance_indicators),
    )


# ── ml.sustainability → API ────────────────────────────────────────


def _ml_risk_to_api(risk_str: str) -> RiskLevel:
    """Map the ML package's lowercase risk string to the API enum.

    The `RiskLevel` enum's values are the lowercase strings, so this
    is `RiskLevel(risk_str)` with a defensive fallback to `MEDIUM` for
    any unknown value the ML package emits.
    """
    try:
        return RiskLevel(risk_str)
    except ValueError:
        return RiskLevel.MEDIUM


def _shap_features_from_top_features(
    top_features: tuple[tuple[str, float], ...],
) -> list[SHAPFeature]:
    """Translate the ML package's `top_features` tuple into the API's
    `SHAPFeature` list. Sign of the SHAP value drives the direction;
    rank follows tuple order.

    Wave-1 arms (LinearLogistic) return up to 3 features in standardised
    space. If the upstream sub-scores are empty we surface a single
    `model` driver so the response always has ≥1 driver — mirrors the
    forecasting translation layer's NaiveLast fallback posture
    (TASK-016).
    """
    if not top_features:
        return [
            SHAPFeature(
                feature_name="model",
                shap_value=0.0,
                feature_value="ml.sustainability",
                contribution_direction="positive",
                importance_rank=1,
            )
        ]
    result: list[SHAPFeature] = []
    for rank, (name, value) in enumerate(top_features, start=1):
        direction = "positive" if value >= 0 else "negative"
        result.append(
            SHAPFeature(
                feature_name=name,
                shap_value=float(value),
                feature_value=name,
                contribution_direction=direction,
                importance_rank=rank,
            )
        )
    return result


def _lime_features_from_attributions(
    lime_attributions: tuple[tuple[str, float], ...],
) -> list[SHAPFeature]:
    """Translate the ML package's `lime_attributions` tuple into the
    API's `SHAPFeature` list (TASK-047 / FE-016 wave 2). Reuses the
    `SHAPFeature` shape because the wire-level fields are
    structurally identical to SHAP — only the semantics differ
    (Shapley credit vs. local linear coefficient). Unlike the SHAP
    translator we *don't* synthesise a placeholder "model" entry on
    empty input: an empty LIME list is the standard signal to the
    frontend that LIME wasn't computed (mock scorer / explainer
    backend rejected the input), and the `<LimePanel>` empty state
    handles that gracefully.
    """
    result: list[SHAPFeature] = []
    for rank, (name, value) in enumerate(lime_attributions, start=1):
        direction = "positive" if value >= 0 else "negative"
        result.append(
            SHAPFeature(
                feature_name=name,
                shap_value=float(value),
                feature_value=name,
                contribution_direction=direction,
                importance_rank=rank,
            )
        )
    return result


def ml_score_to_api(
    *,
    result: MLESGScoreResult,
    request: ESGScoreRequest,
    assessment_id: UUID | None = None,
) -> ESGScoreResponse:
    """Wrap a single `ml.sustainability.ESGScoreResult` into the
    `/score` API response.

    The ML result's `pillar_scores` is already in the 0–100 scale the
    API expects; we round to the 0.1 precision the API contract uses
    so downstream consumers see numbers identical to the mock branch.
    """
    pillars = result.pillar_scores
    sub = ESGSubScores(
        environmental=round(pillars.environmental, 1),
        social=round(pillars.social, 1),
        governance=round(pillars.governance, 1),
    )
    composite = round(pillars.composite, 1)
    risk = _ml_risk_to_api(result.risk_level)

    return ESGScoreResponse(
        assessment_id=assessment_id or uuid4(),
        company_name=result.company_name,
        industry=result.industry,
        assessed_at=datetime.now(timezone.utc),
        composite_score=composite,
        sub_scores=sub,
        risk_level=risk,
        industry_percentile=round(result.industry_percentile, 1),
        regulatory_risk_flag=risk in (RiskLevel.HIGH, RiskLevel.CRITICAL),
        top_shap_features=_shap_features_from_top_features(result.top_features),
        top_lime_features=_lime_features_from_attributions(
            # Legacy `MLESGScoreResult` fixtures from earlier tests may
            # not carry the new field — fall back to () so the
            # response shape stays stable.
            getattr(result, "lime_attributions", ())
        ),
        model_version=result.model_name or "ml.sustainability",
    )


def ml_carbon_to_api(
    *,
    estimate: MLCarbonEstimate,
    request: CarbonEstimateRequest,
    pathways: tuple[str, ...],
) -> CarbonEstimateResponse:
    """Wrap a single `ml.sustainability.CarbonEstimate` into the
    `/carbon-estimate` API response, including reduction pathways.

    `pathways` is the model-derived ordering (largest scope share first)
    — we pass it through rather than recomputing it here so the
    translation layer stays pure.
    """
    total = float(estimate.total_tco2e)
    revenue_m = request.annual_revenue / 1_000_000.0
    intensity_per_revenue = round(total / revenue_m, 2) if revenue_m else 0.0
    return CarbonEstimateResponse(
        scope_1_tco2e=round(float(estimate.scope_1_tco2e), 2),
        scope_2_tco2e=round(float(estimate.scope_2_tco2e), 2),
        scope_3_tco2e=round(float(estimate.scope_3_tco2e), 2),
        total_tco2e=round(total, 2),
        intensity_per_revenue=intensity_per_revenue,
        reduction_pathways=list(pathways),
    )
