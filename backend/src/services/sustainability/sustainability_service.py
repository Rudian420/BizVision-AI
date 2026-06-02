"""
BizVision AI — Green Business Sustainability Scorer Service

Persistence-aware service. Every `/score`, `/simulate`, `/recommendations`,
and `/carbon-estimate` call writes a row to `sustainability_assessments`
(one polymorphic table, discriminator-keyed — see
`src.models.sustainability.SustainabilityAssessment`).
`get_explanation` reads back from that table; `get_benchmarks` stays
stateless (reference data, no row produced).

ML state (2026-05-30):
  • **Persistence is real.** Every analysis call persists its request +
    response payload + headline values; cross-user authorisation is
    enforced by 404 on `_find`.
  • **Real-ML branch is real.** With `SUSTAINABILITY_USE_REAL_ML=True`,
    `/score` and `/carbon-estimate` delegate to the
    `SustainabilityInferenceClient` (mirror of ADR-024) which dispatches
    to `ml.sustainability` (LinearLogisticMultiLabel + CarbonEstimatorModel).
    `/simulate`, `/recommendations`, and `/benchmarks/{industry}` stay
    closed-form in both branches — same posture as pricing's
    `/elasticity` and forecasting's `/sensitivity`.
  • **Mock branch is preserved.** Same code paths, same persisted shape
    — the flag flip changes only the upstream scorer + carbon model,
    not the DB schema or response contract.
"""

from __future__ import annotations

import statistics
import time
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.schemas.common import RiskLevel, SHAPFeature
from src.api.v1.schemas.sustainability import (
    CarbonEstimateRequest,
    CarbonEstimateResponse,
    ESGScoreRequest,
    ESGScoreResponse,
    ESGSimulationRequest,
    ESGSimulationResponse,
    ESGSubScores,
    Recommendation,
    RecommendationsRequest,
    RecommendationsResponse,
    SustainabilityAssessmentDetailResponse,
)
from src.core.config import settings
from src.models.audit import AuditModule
from src.models.sustainability import (
    SustainabilityAssessment,
    SustainabilityAssessmentType,
)
from src.services.audit.audit_service import AuditService

_MOCK_MODEL_VERSION = "esg-mock-0.1"
_REAL_MODEL_VERSION = "esg-real-0.1"


def _current_model_version() -> str:
    """Resolve the active sustainability model version at write-time.

    Reading the flag here (rather than at module import) means flipping
    `SUSTAINABILITY_USE_REAL_ML` between requests is reflected in the
    persisted `model_version` column without a process restart — same
    pattern as pricing's + forecasting's `_current_model_version()`.
    """
    return _REAL_MODEL_VERSION if settings.SUSTAINABILITY_USE_REAL_ML else _MOCK_MODEL_VERSION

# Rough industry carbon intensity (tCO2e per $1M revenue) for the mock.
_INDUSTRY_INTENSITY = {
    "manufacturing": 220.0,
    "retail": 60.0,
    "technology": 25.0,
    "logistics": 300.0,
    "agriculture": 180.0,
}
_DEFAULT_INTENSITY = 100.0


def _pillar_score(indicators: dict[str, float]) -> float:
    if not indicators:
        return 55.0
    return round(min(100.0, max(0.0, 100.0 * statistics.fmean(indicators.values()))), 1)


def _risk_for(score: float) -> RiskLevel:
    if score >= 75:
        return RiskLevel.LOW
    if score >= 55:
        return RiskLevel.MEDIUM
    if score >= 35:
        return RiskLevel.HIGH
    return RiskLevel.CRITICAL


class SustainabilityService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── 1. score ───────────────────────────────────────────────────
    async def calculate_score(
        self, request: ESGScoreRequest, user_id: UUID
    ) -> ESGScoreResponse:
        t0 = time.perf_counter()

        # Real-ML branch — delegates to the shared
        # `SustainabilityInferenceClient` (mirrors ADR-024).
        # Persistence is identical either way.
        if settings.SUSTAINABILITY_USE_REAL_ML:
            from src.services.sustainability.inference import get_inference_client

            response = get_inference_client().calculate_score(request)
            elapsed_ms = (time.perf_counter() - t0) * 1000
            await self._persist(
                assessment_id=response.assessment_id,
                user_id=user_id,
                assessment_type=SustainabilityAssessmentType.SCORE,
                company_name=request.company_name,
                industry=request.industry,
                request=request,
                response=response,
                processing_time_ms=elapsed_ms,
                composite_score=response.composite_score,
                risk_level=response.risk_level.value,
                interpretation=(
                    f"Composite {response.composite_score:.1f}/100 → "
                    f"{response.risk_level.value} risk ({response.model_version}). "
                    f"Environmental={response.sub_scores.environmental:.0f}, "
                    f"Social={response.sub_scores.social:.0f}, "
                    f"Governance={response.sub_scores.governance:.0f}."
                ),
            )
            return response

        # ── Mock path (unchanged) ──────────────────────────────────
        sub = ESGSubScores(
            environmental=_pillar_score(request.environmental_indicators),
            social=_pillar_score(request.social_indicators),
            governance=_pillar_score(request.governance_indicators),
        )
        composite = round((sub.environmental + sub.social + sub.governance) / 3, 1)
        risk = _risk_for(composite)
        response = ESGScoreResponse(
            assessment_id=uuid4(),
            company_name=request.company_name,
            industry=request.industry,
            assessed_at=datetime.now(timezone.utc),
            composite_score=composite,
            sub_scores=sub,
            risk_level=risk,
            industry_percentile=round(min(99.0, composite + 5), 1),
            regulatory_risk_flag=risk in (RiskLevel.HIGH, RiskLevel.CRITICAL),
            top_shap_features=[
                SHAPFeature(
                    feature_name="energy_efficiency",
                    shap_value=0.21,
                    feature_value=sub.environmental,
                    contribution_direction="positive",
                    importance_rank=1,
                ),
                SHAPFeature(
                    feature_name="board_independence",
                    shap_value=0.14,
                    feature_value=sub.governance,
                    contribution_direction="positive",
                    importance_rank=2,
                ),
            ],
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000
        await self._persist(
            assessment_id=response.assessment_id,
            user_id=user_id,
            assessment_type=SustainabilityAssessmentType.SCORE,
            company_name=request.company_name,
            industry=request.industry,
            request=request,
            response=response,
            processing_time_ms=elapsed_ms,
            composite_score=composite,
            risk_level=risk.value,
            interpretation=(
                f"Composite {composite:.1f}/100 → {risk.value} risk. "
                f"Environmental={sub.environmental:.0f}, Social={sub.social:.0f}, "
                f"Governance={sub.governance:.0f}."
            ),
        )
        return response

    # ── 2. simulate (references an existing score row) ─────────────
    async def simulate_improvements(
        self, request: ESGSimulationRequest, user_id: UUID
    ) -> ESGSimulationResponse:
        t0 = time.perf_counter()
        # Validate the referenced score exists and belongs to this user.
        parent = await self._find(request.assessment_id, user_id)
        baseline = float(parent.composite_score or 58.0)

        total_investment = sum(request.investments.values())
        uplift = min(30.0, total_investment / 10_000.0)
        projected = round(baseline + uplift, 1)
        projected_risk = _risk_for(projected)
        response = ESGSimulationResponse(
            assessment_id=request.assessment_id,
            baseline_score=baseline,
            projected_score=projected,
            score_uplift=round(uplift, 1),
            payback_months=min(request.horizon_months, 18),
            projected_carbon_reduction_tco2e=round(total_investment / 500.0, 1),
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000
        # Persist as a NEW row referencing the parent in `request_payload`.
        await self._persist(
            assessment_id=uuid4(),
            user_id=user_id,
            assessment_type=SustainabilityAssessmentType.SIMULATION,
            company_name=parent.company_name,
            industry=parent.industry,
            request=request,
            response=response,
            processing_time_ms=elapsed_ms,
            composite_score=projected,
            risk_level=projected_risk.value,
            interpretation=(
                f"Projected score {projected:.1f} (+{uplift:.1f}) under "
                f"${total_investment:,.0f} in investments."
            ),
        )
        return response

    # ── 3. recommendations (references an existing score row) ──────
    async def get_recommendations(
        self, request: RecommendationsRequest, user_id: UUID
    ) -> RecommendationsResponse:
        t0 = time.perf_counter()
        parent = await self._find(request.assessment_id, user_id)
        catalog = [
            Recommendation(
                title="Switch to renewable energy contract",
                pillar="E",
                estimated_score_impact=6.5,
                implementation_effort="medium",
                rationale="Cuts Scope 2 emissions and improves energy-efficiency score.",
            ),
            Recommendation(
                title="Publish a DEI transparency report",
                pillar="S",
                estimated_score_impact=4.0,
                implementation_effort="low",
                rationale="Improves social-pillar disclosure metrics.",
            ),
            Recommendation(
                title="Add independent board members",
                pillar="G",
                estimated_score_impact=5.0,
                implementation_effort="high",
                rationale="Strengthens governance independence indicators.",
            ),
            Recommendation(
                title="Implement supplier ESG screening",
                pillar="E",
                estimated_score_impact=3.5,
                implementation_effort="medium",
                rationale="Reduces Scope 3 supply-chain emissions.",
            ),
            Recommendation(
                title="Formal anti-corruption policy + training",
                pillar="G",
                estimated_score_impact=3.0,
                implementation_effort="low",
                rationale="Closes a common governance gap for SMEs.",
            ),
        ]
        response = RecommendationsResponse(
            assessment_id=request.assessment_id,
            recommendations=catalog[: request.max_recommendations],
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000
        await self._persist(
            assessment_id=uuid4(),
            user_id=user_id,
            assessment_type=SustainabilityAssessmentType.RECOMMENDATIONS,
            company_name=parent.company_name,
            industry=parent.industry,
            request=request,
            response=response,
            processing_time_ms=elapsed_ms,
            interpretation=(
                f"Top {len(response.recommendations)} recommendations "
                f"prioritised by estimated score impact."
            ),
        )
        return response

    # ── 4. benchmarks (stateless reference data) ───────────────────
    async def get_benchmarks(self, industry: str) -> dict:
        """No row written — benchmarks are public reference data."""
        intensity = _INDUSTRY_INTENSITY.get(industry.lower(), _DEFAULT_INTENSITY)
        return {
            "industry": industry,
            "median_esg_score": 56.0,
            "top_quartile_threshold": 72.0,
            "carbon_intensity_tco2e_per_million": intensity,
        }

    # ── 5. carbon estimate ─────────────────────────────────────────
    async def estimate_carbon(
        self, request: CarbonEstimateRequest, user_id: UUID
    ) -> CarbonEstimateResponse:
        t0 = time.perf_counter()

        if settings.SUSTAINABILITY_USE_REAL_ML:
            from src.services.sustainability.inference import get_inference_client

            response = get_inference_client().estimate_carbon(request)
            elapsed_ms = (time.perf_counter() - t0) * 1000
            # Internal UUID — the response schema doesn't surface one.
            await self._persist(
                assessment_id=uuid4(),
                user_id=user_id,
                assessment_type=SustainabilityAssessmentType.CARBON_ESTIMATE,
                company_name=None,
                industry=request.industry,
                request=request,
                response=response,
                processing_time_ms=elapsed_ms,
                total_tco2e=response.total_tco2e,
                interpretation=(
                    f"Total {response.total_tco2e:.1f} tCO2e "
                    f"(Scope 1={response.scope_1_tco2e:.1f}, "
                    f"Scope 2={response.scope_2_tco2e:.1f}, "
                    f"Scope 3={response.scope_3_tco2e:.1f})."
                ),
            )
            return response

        # ── Mock path (unchanged) ──────────────────────────────────
        intensity = _INDUSTRY_INTENSITY.get(request.industry.lower(), _DEFAULT_INTENSITY)
        revenue_m = request.annual_revenue / 1_000_000.0
        scope_2 = (request.energy_kwh or 0.0) * 0.0004
        scope_1 = (request.fleet_km or 0.0) * 0.00017
        scope_3 = intensity * revenue_m
        total = scope_1 + scope_2 + scope_3
        response = CarbonEstimateResponse(
            scope_1_tco2e=round(scope_1, 2),
            scope_2_tco2e=round(scope_2, 2),
            scope_3_tco2e=round(scope_3, 2),
            total_tco2e=round(total, 2),
            intensity_per_revenue=round(total / revenue_m, 2) if revenue_m else 0.0,
            reduction_pathways=[
                "Procure renewable energy (largest Scope 2 lever)",
                "Electrify or optimise fleet routing",
                "Engage top suppliers on Scope 3 reductions",
            ],
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000
        # The CarbonEstimateResponse schema doesn't expose an
        # `assessment_id`, so we mint one internally for the audit trail
        # but don't surface it. A future schema bump can echo it.
        await self._persist(
            assessment_id=uuid4(),
            user_id=user_id,
            assessment_type=SustainabilityAssessmentType.CARBON_ESTIMATE,
            company_name=None,
            industry=request.industry,
            request=request,
            response=response,
            processing_time_ms=elapsed_ms,
            total_tco2e=round(total, 2),
            interpretation=(
                f"Total {total:.1f} tCO2e (Scope 1={scope_1:.1f}, "
                f"Scope 2={scope_2:.1f}, Scope 3={scope_3:.1f})."
            ),
        )
        return response

    # ── 5b. list assessments (reads from DB, paged) ───────────────
    async def list_assessments(
        self,
        user_id: UUID,
        assessment_type: str | None,
        industry: str | None,
        page: int,
        page_size: int,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> dict[str, Any]:
        """Paged list of the caller's persisted assessments. Backs the
        frontend's `/modules/sustainability/assessments` history page
        (TASK-035). Mirrors pricing's + forecasting's `list_history`
        posture — paged + filterable by discriminator + key column +
        date range (TASK-037).
        """
        from sqlalchemy import func

        page = max(1, page)
        page_size = max(1, min(page_size, 100))
        offset = (page - 1) * page_size

        filters = [SustainabilityAssessment.user_id == user_id]
        if assessment_type is not None:
            try:
                typed = SustainabilityAssessmentType(assessment_type)
            except ValueError as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Unknown assessment_type {assessment_type!r}",
                ) from e
            filters.append(SustainabilityAssessment.assessment_type == typed)
        if industry is not None:
            filters.append(SustainabilityAssessment.industry == industry)
        # Date-range filter (TASK-037).
        if since is not None:
            filters.append(SustainabilityAssessment.created_at >= since)
        if until is not None:
            filters.append(SustainabilityAssessment.created_at <= until)

        total = await self.db.scalar(
            select(func.count())
            .select_from(SustainabilityAssessment)
            .where(*filters)
        )
        rows = await self.db.execute(
            select(SustainabilityAssessment)
            .where(*filters)
            .order_by(SustainabilityAssessment.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        items = [
            {
                "assessment_id": str(r.id),
                "assessment_type": r.assessment_type.value,
                "company_name": r.company_name,
                "industry": r.industry,
                "composite_score": r.composite_score,
                "risk_level": r.risk_level,
                "total_tco2e": r.total_tco2e,
                "model_version": r.model_version,
                "created_at": r.created_at.isoformat(),
            }
            for r in rows.scalars()
        ]
        return {
            "items": items,
            "total": int(total or 0),
            "page": page,
            "page_size": page_size,
        }

    # ── 5a. detail (reads from DB) ─────────────────────────────────
    async def get_assessment_detail(
        self, assessment_id: UUID, user_id: UUID
    ) -> SustainabilityAssessmentDetailResponse:
        """Reconstruct one persisted assessment row. Backs the audit-
        feed deep-link (TASK-033). 404 via `_find` when not yours."""
        row = await self._find(assessment_id, user_id)
        return SustainabilityAssessmentDetailResponse(
            assessment_id=row.id,
            assessment_type=row.assessment_type.value,
            company_name=row.company_name,
            industry=row.industry,
            created_at=row.created_at,
            model_version=row.model_version,
            processing_time_ms=row.processing_time_ms,
            composite_score=row.composite_score,
            risk_level=row.risk_level,
            total_tco2e=row.total_tco2e,
            interpretation=row.interpretation,
            request_payload=row.request_payload or {},
            response_payload=row.response_payload or {},
        )

    # ── 6. explanation (reads from DB) ─────────────────────────────
    async def get_explanation(self, assessment_id: UUID, user_id: UUID) -> dict:
        row = await self._find(assessment_id, user_id)
        response = row.response_payload or {}
        shap_features = response.get("top_shap_features") or []
        drivers = [
            {
                "feature": f.get("feature_name") or f.get("feature"),
                "shap_value": f.get("shap_value"),
                "direction": f.get("contribution_direction"),
            }
            for f in shap_features
        ] or [
            # For non-score types (simulate, recommendations, carbon) we
            # haven't tracked SHAP; surface a stable empty list rather
            # than the score's drivers (which would be misleading).
        ]
        return {
            "assessment_id": str(assessment_id),
            "assessment_type": row.assessment_type.value,
            "company_name": row.company_name,
            "industry": row.industry,
            "drivers": drivers,
            "narrative": row.interpretation
            or response.get("interpretation")
            or response.get("rationale")
            or "",
        }

    # ── internals ──────────────────────────────────────────────────
    async def _persist(
        self,
        *,
        assessment_id: UUID,
        user_id: UUID,
        assessment_type: SustainabilityAssessmentType,
        company_name: str | None,
        industry: str | None,
        request: Any,
        response: Any,
        processing_time_ms: float,
        composite_score: float | None = None,
        risk_level: str | None = None,
        total_tco2e: float | None = None,
        interpretation: str | None = None,
    ) -> None:
        model_version = _current_model_version()
        row = SustainabilityAssessment(
            id=assessment_id,
            user_id=user_id,
            assessment_type=assessment_type,
            company_name=company_name,
            industry=industry,
            request_payload=request.model_dump(mode="json"),
            response_payload=response.model_dump(mode="json"),
            composite_score=composite_score,
            risk_level=risk_level,
            total_tco2e=total_tco2e,
            model_version=model_version,
            processing_time_ms=round(processing_time_ms, 3),
            interpretation=interpretation,
        )
        self.db.add(row)
        await self.db.flush()

        # Cross-module audit log (ADR-031). Fire-and-forget.
        # `risk_tier` populated from the per-assessment risk_level
        # (LOW/MEDIUM/HIGH/CRITICAL) when the assessment type produces
        # one — score / simulation. carbon_estimate +
        # recommendations don't have a risk tier of their own.
        response_dump = response.model_dump(mode="json")
        shap_features = response_dump.get("top_shap_features") or []
        await AuditService(self.db).record(
            user_id=user_id,
            module=AuditModule.SUSTAINABILITY,
            action=assessment_type.value,
            reference_id=assessment_id,
            reference_type="sustainability_assessment",
            request_summary={
                "company_name": company_name,
                "industry": industry,
                "parent_assessment_id": str(
                    getattr(request, "assessment_id", None)
                )
                if getattr(request, "assessment_id", None)
                else None,
            },
            response_summary={
                "composite_score": composite_score,
                "risk_level": risk_level,
                "total_tco2e": total_tco2e,
                "industry_percentile": response_dump.get("industry_percentile"),
                "regulatory_risk_flag": response_dump.get("regulatory_risk_flag"),
            },
            explanation_summary=(
                {"top_shap_features": shap_features[:3]} if shap_features else None
            ),
            risk_tier=risk_level,
            model_version=model_version,
            latency_ms=round(processing_time_ms, 3),
        )

    async def _find(
        self, assessment_id: UUID, user_id: UUID
    ) -> SustainabilityAssessment:
        result = await self.db.execute(
            select(SustainabilityAssessment).where(
                SustainabilityAssessment.id == assessment_id,
                SustainabilityAssessment.user_id == user_id,
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Sustainability assessment {assessment_id} not found",
            )
        return row
