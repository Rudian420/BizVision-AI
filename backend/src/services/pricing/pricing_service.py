"""
BizVision AI — Smart Pricing Advisor Service

Persistence-aware service. Every `/optimize`, `/simulate`, `/elasticity`,
and `/scenarios` call writes a row to `pricing_analyses` (one table,
discriminator-keyed — see `src.models.pricing.PricingAnalysis`).
`list_history` and `get_explanation` read back from that table.

ML state (2026-05-29):
  • **Persistence is real.** Every analysis call persists its request +
    response payload + headline values; `list_history` is a real paged
    DB query.
  • **ML scoring is still the deterministic mock.** The real LightGBM
    demand model + PPO pricing agent live in `ml/pricing/` and will be
    wired through a `PricingInferenceClient` mirroring ADR-024 once the
    `ml.pricing.{data,models,inference}` modules are built out
    (planned: Sessions 9–10). The persistence layer is unchanged when
    that wiring lands — same DB schema, same response shapes.
"""

from __future__ import annotations

import math
import statistics
import time
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.schemas.common import SHAPFeature
from src.api.v1.schemas.pricing import (
    ElasticityAnalysisRequest,
    ElasticityAnalysisResponse,
    MonteCarloSimulationRequest,
    MonteCarloSimulationResponse,
    PriceOptimizationRequest,
    PriceOptimizationResponse,
    PricePoint,
    PricingAnalysisDetailResponse,
    ScenarioComparisonRequest,
    ScenarioComparisonResponse,
)
from src.core.config import settings
from src.models.audit import AuditModule
from src.models.pricing import PricingAnalysis, PricingAnalysisType
from src.services.audit.audit_service import AuditService

_MOCK_MODEL_VERSION = "pricing-mock-0.1"
_REAL_MODEL_VERSION = "pricing-real-0.1"


def _current_model_version() -> str:
    """Resolve the persisted model_version string from the feature flag.

    Read at *write time* (not import time) so flipping
    `PRICING_USE_REAL_ML` between requests is reflected in the persisted
    row without restarting the worker."""
    return _REAL_MODEL_VERSION if settings.PRICING_USE_REAL_ML else _MOCK_MODEL_VERSION


def _demand_at(price: float, base_price: float, base_demand: float) -> float:
    """Simple constant-elasticity demand curve (elasticity ~ -1.5)."""
    if price <= 0:
        return 0.0
    return max(0.0, base_demand * (base_price / price) ** 1.5)


class PricingService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── 1. optimize ────────────────────────────────────────────────
    async def optimize(
        self, request: PriceOptimizationRequest, user_id: UUID
    ) -> PriceOptimizationResponse:
        t0 = time.perf_counter()

        # Real-ML branch — delegates to the shared `PricingInferenceClient`
        # (mirrors ADR-024). Persistence is identical either way.
        if settings.PRICING_USE_REAL_ML:
            from src.services.pricing.inference import get_inference_client

            response = get_inference_client().recommend_price(request)
            elapsed_ms = (time.perf_counter() - t0) * 1000
            await self._persist(
                analysis_id=response.analysis_id,
                user_id=user_id,
                analysis_type=PricingAnalysisType.OPTIMIZE,
                product_id=request.product_id,
                request=request,
                response=response,
                processing_time_ms=elapsed_ms,
                recommended_price=response.recommended_price,
                expected_revenue_uplift=response.expected_revenue_uplift,
                num_trials_or_points=len(response.revenue_curve),
            )
            return response

        # ── Mock path (unchanged) ──────────────────────────────────
        base_demand = (
            statistics.fmean(request.historical_demand) if request.historical_demand else 100.0
        )
        lo = request.min_price or request.current_price * 0.6
        hi = request.max_price or request.current_price * 1.6

        curve: list[PricePoint] = []
        steps = 25
        best: PricePoint | None = None
        for i in range(steps + 1):
            price = lo + (hi - lo) * i / steps
            demand = _demand_at(price, request.current_price, base_demand)
            revenue = price * demand
            profit = (price - request.unit_cost) * demand
            point = PricePoint(
                price=round(price, 2),
                expected_demand=round(demand, 2),
                expected_revenue=round(revenue, 2),
                expected_profit=round(profit, 2),
            )
            curve.append(point)
            key = profit if request.objective == "profit" else revenue
            best_key = (
                (best.expected_profit if request.objective == "profit" else best.expected_revenue)
                if best
                else -1.0
            )
            if best is None or key > best_key:
                best = point

        assert best is not None
        current_rev = request.current_price * _demand_at(
            request.current_price, request.current_price, base_demand
        )
        uplift = (best.expected_revenue - current_rev) / current_rev if current_rev else 0.0

        response = PriceOptimizationResponse(
            analysis_id=uuid4(),
            product_id=request.product_id,
            analysis_timestamp=datetime.now(timezone.utc),
            recommended_price=best.price,
            current_price=request.current_price,
            expected_revenue_uplift=round(uplift, 4),
            confidence_interval=[round(best.price * 0.95, 2), round(best.price * 1.05, 2)],
            revenue_curve=curve,
            top_shap_features=[
                SHAPFeature(
                    feature_name="price_elasticity",
                    shap_value=-0.22,
                    feature_value=-1.5,
                    contribution_direction="negative",
                    importance_rank=1,
                ),
                SHAPFeature(
                    feature_name="competitor_price_gap",
                    shap_value=0.11,
                    feature_value=0.0,
                    contribution_direction="positive",
                    importance_rank=2,
                ),
            ],
            ai_rationale=(
                f"At {best.price:.2f} the {request.objective} objective is maximised "
                "given the estimated demand curve and unit cost."
            ),
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000

        # Persist with the response's analysis_id as the row PK so a later
        # `get_explanation(analysis_id)` reads back the same row.
        await self._persist(
            analysis_id=response.analysis_id,
            user_id=user_id,
            analysis_type=PricingAnalysisType.OPTIMIZE,
            product_id=request.product_id,
            request=request,
            response=response,
            processing_time_ms=elapsed_ms,
            recommended_price=response.recommended_price,
            expected_revenue_uplift=response.expected_revenue_uplift,
            num_trials_or_points=len(response.revenue_curve),
        )
        return response

    # ── 2. monte carlo ─────────────────────────────────────────────
    async def run_monte_carlo(
        self, request: MonteCarloSimulationRequest, user_id: UUID
    ) -> MonteCarloSimulationResponse:
        t0 = time.perf_counter()

        if settings.PRICING_USE_REAL_ML:
            from src.services.pricing.inference import get_inference_client

            response = get_inference_client().simulate(request)
            elapsed_ms = (time.perf_counter() - t0) * 1000
            await self._persist(
                analysis_id=response.analysis_id,
                user_id=user_id,
                analysis_type=PricingAnalysisType.MONTE_CARLO,
                product_id=request.product_id,
                request=request,
                response=response,
                processing_time_ms=elapsed_ms,
                num_trials_or_points=request.num_trials,
            )
            return response

        # ── Mock path (unchanged) ──────────────────────────────────
        mean_rev = request.candidate_price * request.demand_mean
        std_rev = request.candidate_price * request.demand_std
        response = MonteCarloSimulationResponse(
            analysis_id=uuid4(),
            product_id=request.product_id,
            candidate_price=request.candidate_price,
            num_trials=request.num_trials,
            mean_revenue=round(mean_rev, 2),
            revenue_p5=round(mean_rev - 1.645 * std_rev, 2),
            revenue_p50=round(mean_rev, 2),
            revenue_p95=round(mean_rev + 1.645 * std_rev, 2),
            value_at_risk_5pct=round(1.645 * std_rev, 2),
            probability_of_profit=0.87,
            histogram=[{"bin": round(mean_rev, 0), "count": request.num_trials}],
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000
        await self._persist(
            analysis_id=response.analysis_id,
            user_id=user_id,
            analysis_type=PricingAnalysisType.MONTE_CARLO,
            product_id=request.product_id,
            request=request,
            response=response,
            processing_time_ms=elapsed_ms,
            num_trials_or_points=request.num_trials,
        )
        return response

    # ── 3. elasticity ──────────────────────────────────────────────
    async def calculate_elasticity(
        self, request: ElasticityAnalysisRequest, user_id: UUID
    ) -> ElasticityAnalysisResponse:
        t0 = time.perf_counter()

        if settings.PRICING_USE_REAL_ML:
            from src.services.pricing.inference import get_inference_client

            response = get_inference_client().estimate_elasticity(request)
            elapsed_ms = (time.perf_counter() - t0) * 1000
            await self._persist(
                analysis_id=response.analysis_id,
                user_id=user_id,
                analysis_type=PricingAnalysisType.ELASTICITY,
                product_id=request.product_id,
                request=request,
                response=response,
                processing_time_ms=elapsed_ms,
                num_trials_or_points=len(request.price_points),
            )
            return response

        # ── Mock path (unchanged) ──────────────────────────────────
        prices = request.price_points
        demand = request.observed_demand
        try:
            elasticity = (math.log(demand[-1]) - math.log(demand[0])) / (
                math.log(prices[-1]) - math.log(prices[0])
            )
        except (ValueError, ZeroDivisionError):
            elasticity = -1.0
        lo, hi = min(prices), max(prices)
        response = ElasticityAnalysisResponse(
            analysis_id=uuid4(),
            product_id=request.product_id,
            elasticity_coefficient=round(elasticity, 4),
            is_elastic=abs(elasticity) > 1,
            optimal_price_zone=[round(lo * 1.05, 2), round(hi * 0.95, 2)],
            interpretation=(
                "Demand is elastic — small price increases reduce revenue."
                if abs(elasticity) > 1
                else "Demand is inelastic — there is room to raise price."
            ),
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000
        await self._persist(
            analysis_id=response.analysis_id,
            user_id=user_id,
            analysis_type=PricingAnalysisType.ELASTICITY,
            product_id=request.product_id,
            request=request,
            response=response,
            processing_time_ms=elapsed_ms,
            num_trials_or_points=len(prices),
        )
        return response

    # ── 4. scenario comparison ─────────────────────────────────────
    async def compare_scenarios(
        self, request: ScenarioComparisonRequest, user_id: UUID
    ) -> ScenarioComparisonResponse:
        t0 = time.perf_counter()

        if settings.PRICING_USE_REAL_ML:
            from src.services.pricing.inference import get_inference_client

            response = get_inference_client().compare_scenarios(request)
            elapsed_ms = (time.perf_counter() - t0) * 1000
            await self._persist(
                analysis_id=response.analysis_id,
                user_id=user_id,
                analysis_type=PricingAnalysisType.SCENARIO_COMPARISON,
                product_id=request.product_id,
                request=request,
                response=response,
                processing_time_ms=elapsed_ms,
                recommended_price=response.scenarios[response.recommended_scenario].price,
                num_trials_or_points=len(response.scenarios),
            )
            return response

        # ── Mock path (unchanged) ──────────────────────────────────
        def point(multiplier: float) -> PricePoint:
            price = request.current_price * multiplier
            demand = _demand_at(price, request.current_price, request.demand_mean)
            return PricePoint(
                price=round(price, 2),
                expected_demand=round(demand, 2),
                expected_revenue=round(price * demand, 2),
                expected_profit=round((price - request.unit_cost) * demand, 2),
            )

        scenarios = {
            "conservative": point(0.95),
            "optimal": point(1.08),
            "aggressive": point(1.20),
        }
        best = max(scenarios.items(), key=lambda kv: kv[1].expected_revenue)
        response = ScenarioComparisonResponse(
            analysis_id=uuid4(),
            product_id=request.product_id,
            scenarios=scenarios,
            recommended_scenario=best[0],
            rationale=f"'{best[0]}' maximises expected revenue under the demand model.",
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000
        await self._persist(
            analysis_id=response.analysis_id,
            user_id=user_id,
            analysis_type=PricingAnalysisType.SCENARIO_COMPARISON,
            product_id=request.product_id,
            request=request,
            response=response,
            processing_time_ms=elapsed_ms,
            recommended_price=scenarios[best[0]].price,
            num_trials_or_points=len(scenarios),
        )
        return response

    # ── 5. explanation (reads from DB) ─────────────────────────────
    async def get_explanation(self, analysis_id: UUID, user_id: UUID) -> dict:
        row = await self._find(analysis_id, user_id)
        # SHAP features were persisted in the response payload for
        # `optimize`; other types don't have model-attributed explanations.
        response = row.response_payload or {}
        shap_features = response.get("top_shap_features") or []
        return {
            "analysis_id": str(analysis_id),
            "analysis_type": row.analysis_type.value,
            "product_id": row.product_id,
            "shap_features": [
                {
                    "feature": f.get("feature_name") or f.get("feature"),
                    "value": f.get("shap_value"),
                    "direction": f.get("contribution_direction"),
                }
                for f in shap_features
            ],
            "narrative": response.get("ai_rationale")
            or response.get("interpretation")
            or response.get("rationale")
            or "",
        }

    # ── 5a. detail (reads from DB) ─────────────────────────────────
    async def get_analysis_detail(
        self, analysis_id: UUID, user_id: UUID
    ) -> PricingAnalysisDetailResponse:
        """Reconstruct one persisted analysis row. Backs the audit-feed
        deep-link (TASK-033). 404 via `_find` when not yours."""
        row = await self._find(analysis_id, user_id)
        return PricingAnalysisDetailResponse(
            analysis_id=row.id,
            analysis_type=row.analysis_type.value,
            product_id=row.product_id,
            created_at=row.created_at,
            model_version=row.model_version,
            processing_time_ms=row.processing_time_ms,
            recommended_price=row.recommended_price,
            expected_revenue_uplift=row.expected_revenue_uplift,
            num_trials_or_points=row.num_trials_or_points,
            request_payload=row.request_payload or {},
            response_payload=row.response_payload or {},
        )

    # ── 6. history (reads from DB, paged) ──────────────────────────
    async def list_history(
        self,
        user_id: UUID,
        product_id: str | None,
        page: int,
        page_size: int,
        analysis_type: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> dict:
        page = max(1, page)
        page_size = max(1, min(page_size, 100))
        offset = (page - 1) * page_size

        # Build the filter once; both the count and the page reuse it.
        filters = [PricingAnalysis.user_id == user_id]
        if product_id is not None:
            filters.append(PricingAnalysis.product_id == product_id)
        if analysis_type is not None:
            try:
                typed = PricingAnalysisType(analysis_type)
            except ValueError as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Unknown analysis_type {analysis_type!r}",
                ) from e
            filters.append(PricingAnalysis.analysis_type == typed)
        # Date-range filter (TASK-037). `since` is inclusive lower bound,
        # `until` is inclusive upper bound — both are full timestamps so
        # the frontend can pass either ISO date strings (00:00 UTC) or
        # full datetimes without surprise.
        if since is not None:
            filters.append(PricingAnalysis.created_at >= since)
        if until is not None:
            filters.append(PricingAnalysis.created_at <= until)

        total = await self.db.scalar(
            select(func.count()).select_from(PricingAnalysis).where(*filters)
        )
        rows = await self.db.execute(
            select(PricingAnalysis)
            .where(*filters)
            .order_by(PricingAnalysis.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        items = [
            {
                "analysis_id": str(r.id),
                "analysis_type": r.analysis_type.value,
                "product_id": r.product_id,
                "recommended_price": r.recommended_price,
                "expected_revenue_uplift": r.expected_revenue_uplift,
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

    # ── internals ──────────────────────────────────────────────────
    async def _persist(
        self,
        *,
        analysis_id: UUID,
        user_id: UUID,
        analysis_type: PricingAnalysisType,
        product_id: str,
        request: Any,
        response: Any,
        processing_time_ms: float,
        recommended_price: float | None = None,
        expected_revenue_uplift: float | None = None,
        num_trials_or_points: int | None = None,
    ) -> None:
        model_version = _current_model_version()
        row = PricingAnalysis(
            id=analysis_id,
            user_id=user_id,
            analysis_type=analysis_type,
            product_id=product_id,
            request_payload=request.model_dump(mode="json"),
            response_payload=response.model_dump(mode="json"),
            recommended_price=recommended_price,
            expected_revenue_uplift=expected_revenue_uplift,
            model_version=model_version,
            processing_time_ms=round(processing_time_ms, 3),
            num_trials_or_points=num_trials_or_points,
        )
        self.db.add(row)
        await self.db.flush()

        # Cross-module audit log (ADR-031). Fire-and-forget. SHAP
        # attributions appear only for `optimize` today — surface them
        # when present so the Phase-4 dashboards have a uniform feed.
        response_dump = response.model_dump(mode="json")
        shap_features = response_dump.get("top_shap_features") or []
        await AuditService(self.db).record(
            user_id=user_id,
            module=AuditModule.PRICING,
            action=analysis_type.value,
            reference_id=analysis_id,
            reference_type="pricing_analysis",
            request_summary={
                "product_id": product_id,
                "objective": getattr(request, "objective", None),
                "current_price": getattr(request, "current_price", None),
                "candidate_price": getattr(request, "candidate_price", None),
                "num_trials_or_points": num_trials_or_points,
            },
            response_summary={
                "recommended_price": recommended_price,
                "expected_revenue_uplift": expected_revenue_uplift,
                "is_elastic": response_dump.get("is_elastic"),
                "recommended_scenario": response_dump.get("recommended_scenario"),
            },
            explanation_summary=(
                {"top_shap_features": shap_features[:3]} if shap_features else None
            ),
            risk_tier=None,  # pricing has no fairness risk tier today
            model_version=model_version,
            latency_ms=round(processing_time_ms, 3),
        )

    async def _find(self, analysis_id: UUID, user_id: UUID) -> PricingAnalysis:
        result = await self.db.execute(
            select(PricingAnalysis).where(
                PricingAnalysis.id == analysis_id,
                PricingAnalysis.user_id == user_id,
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Pricing analysis {analysis_id} not found",
            )
        return row
