"""
BizVision AI — Green Business Sustainability Scorer Schemas
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from src.api.v1.schemas.common import RiskLevel, SHAPFeature

# ── Requests ───────────────────────────────────────────────────────


class ESGScoreRequest(BaseModel):
    company_name: str
    industry: str = Field(..., description="Industry sector for benchmarking")
    annual_revenue: float = Field(..., ge=0)
    employee_count: int = Field(..., ge=1)
    # Free-form practice indicators (0-1 self-reported or extracted).
    environmental_indicators: dict[str, float] = Field(default_factory=dict)
    social_indicators: dict[str, float] = Field(default_factory=dict)
    governance_indicators: dict[str, float] = Field(default_factory=dict)


class ESGSimulationRequest(BaseModel):
    assessment_id: UUID
    investments: dict[str, float] = Field(..., description="Initiative name -> investment amount")
    horizon_months: int = Field(default=24, ge=1, le=120)


class RecommendationsRequest(BaseModel):
    assessment_id: UUID
    max_recommendations: int = Field(default=5, ge=1, le=20)


class CarbonEstimateRequest(BaseModel):
    industry: str
    annual_revenue: float = Field(..., ge=0)
    employee_count: int = Field(..., ge=1)
    energy_kwh: float | None = Field(default=None, ge=0)
    fleet_km: float | None = Field(default=None, ge=0)


# ── Responses ──────────────────────────────────────────────────────


class ESGSubScores(BaseModel):
    environmental: float = Field(..., ge=0, le=100)
    social: float = Field(..., ge=0, le=100)
    governance: float = Field(..., ge=0, le=100)


class ESGScoreResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    assessment_id: UUID
    company_name: str
    industry: str
    assessed_at: datetime
    composite_score: float = Field(..., ge=0, le=100)
    sub_scores: ESGSubScores
    risk_level: RiskLevel
    industry_percentile: float = Field(..., ge=0, le=100)
    regulatory_risk_flag: bool
    top_shap_features: list[SHAPFeature] = Field(default_factory=list)
    top_lime_features: list[SHAPFeature] = Field(
        default_factory=list,
        description=(
            "Top-K LIME local linear surrogate weights for the same "
            "ESG score, in the same shape as `top_shap_features` so "
            "the UI can reuse the bar-chart component. SHAP and LIME "
            "are two independent post-hoc explainers; agreement "
            "between them on the strongest drivers is a robustness "
            "signal for the headline score. Empty list when LIME isn't "
            "available or the model path doesn't emit it (mock "
            "fallback). TASK-047, FE-016 wave 2."
        ),
    )
    model_version: str = "esg-multilabel-mock-0.1"


class ESGSimulationResponse(BaseModel):
    assessment_id: UUID
    baseline_score: float
    projected_score: float
    score_uplift: float
    payback_months: int
    projected_carbon_reduction_tco2e: float


class Recommendation(BaseModel):
    title: str
    pillar: str = Field(..., description="'E' | 'S' | 'G'")
    estimated_score_impact: float
    implementation_effort: str = Field(..., description="'low' | 'medium' | 'high'")
    rationale: str


class RecommendationsResponse(BaseModel):
    assessment_id: UUID
    recommendations: list[Recommendation]


class CarbonEstimateResponse(BaseModel):
    scope_1_tco2e: float
    scope_2_tco2e: float
    scope_3_tco2e: float
    total_tco2e: float
    intensity_per_revenue: float
    reduction_pathways: list[str] = Field(default_factory=list)


# ── Detail / record-view (TASK-033) ────────────────────────────────


class SustainabilityAssessmentDetailResponse(BaseModel):
    """Persisted-row reconstruction returned by
    `GET /sustainability/assessments/{assessment_id}`. Backs the
    audit-feed deep-link from TASK-033
    (`reference_type='sustainability_assessment'`).

    Same posture as PricingAnalysisDetailResponse — discriminator-
    keyed polymorphic table → one schema serves every variant
    (score / simulation / recommendations / carbon_estimate).
    """

    model_config = ConfigDict(protected_namespaces=())

    assessment_id: UUID
    assessment_type: str  # score / simulation / recommendations / carbon_estimate
    company_name: str | None = None
    industry: str | None = None
    created_at: datetime

    model_version: str
    processing_time_ms: float

    # Headline columns surfaced for cheap filtering.
    composite_score: float | None = None
    risk_level: str | None = None
    total_tco2e: float | None = None
    interpretation: str | None = None

    request_payload: dict
    response_payload: dict
