"""
BizVision AI — Profit Forecasting Service

Persistence-aware service. Every `/forecast`, `/sensitivity`, `/what-if`,
and `/cross-module` call writes a row to `forecast_analyses` (one
polymorphic table, discriminator-keyed — see
`src.models.forecasting.ForecastAnalysis`). `get_explanation` and
`list_history` read back from that table; per-user authorisation is
enforced by 404 on `_find`.

ML state (2026-05-30):
  • **Persistence is real.** Every analysis call persists its request +
    response payload + headline values; cross-user authorisation is
    enforced by 404 on `_find`.
  • **Real-ML branch is real.** With `FORECASTING_USE_REAL_ML=True`,
    `/forecast`, `/what-if`, and `/cross-module` delegate to the
    `ForecastingInferenceClient` (mirror of ADR-024) which dispatches to
    `ml.forecasting` (Theta / HoltWinters / baselines). `/sensitivity`
    stays closed-form in both branches — same posture as pricing's
    `/elasticity`.
  • **Mock branch is preserved.** Same code paths, same persisted shape
    — the flag flip changes only the upstream forecaster, not the
    DB schema or response contract.
"""

from __future__ import annotations

import statistics
import time
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.schemas.common import SHAPFeature
from src.api.v1.schemas.forecasting import (
    CrossModuleForecastRequest,
    ForecastAnalysisDetailResponse,
    ForecastPoint,
    ForecastRequest,
    ForecastResponse,
    ScenarioForecast,
    SensitivityAnalysisRequest,
    SensitivityAnalysisResponse,
    TornadoBar,
    WhatIfRequest,
    WhatIfResponse,
)
from src.core.config import settings
from src.models.audit import AuditModule
from src.models.forecasting import ForecastAnalysis, ForecastAnalysisType
from src.services.audit.audit_service import AuditService

_MOCK_MODEL_VERSION = "forecast-ensemble-mock-0.1"
_REAL_MODEL_VERSION = "forecast-ensemble-real-0.1"


def _current_model_version() -> str:
    """Resolve the active forecasting model version at write-time.

    Reading the flag here (rather than at module import) means flipping
    `FORECASTING_USE_REAL_ML` between requests is reflected in the
    persisted `model_version` column without a process restart — same
    pattern as pricing's `_current_model_version()`.
    """
    return _REAL_MODEL_VERSION if settings.FORECASTING_USE_REAL_ML else _MOCK_MODEL_VERSION

_SCENARIO_MULTIPLIERS = {"base": 1.0, "bull": 1.15, "bear": 0.85}


def _linear_trend(history) -> tuple[float, float, float]:
    """Return (last_value, daily_slope, last_ordinal)."""
    ys = [p.y for p in history]
    n = len(ys)
    xs = list(range(n))
    mean_x = statistics.fmean(xs)
    mean_y = statistics.fmean(ys)
    denom = sum((x - mean_x) ** 2 for x in xs) or 1.0
    slope = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys, strict=False)) / denom
    return ys[-1], slope, history[-1].ds.toordinal()


def _build_scenario(history, horizon: int, multiplier: float, label: str) -> ScenarioForecast:
    last_value, slope, last_ord = _linear_trend(history)
    points: list[ForecastPoint] = []
    cumulative = 0.0
    for d in range(1, horizon + 1):
        yhat = (last_value + slope * d) * multiplier
        band = abs(yhat) * 0.08
        ds = datetime.fromordinal(last_ord + d).date()
        points.append(
            ForecastPoint(
                ds=ds,
                yhat=round(yhat, 2),
                yhat_lower=round(yhat - band, 2),
                yhat_upper=round(yhat + band, 2),
            )
        )
        cumulative += yhat
    return ScenarioForecast(
        scenario=label,
        points=points,
        end_value=round(points[-1].yhat, 2),
        cumulative_value=round(cumulative, 2),
    )


class ForecastingService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── 1. forecast ────────────────────────────────────────────────
    async def generate_forecast(
        self, request: ForecastRequest, user_id: UUID
    ) -> ForecastResponse:
        t0 = time.perf_counter()
        horizon = request.forecast_horizon_days

        # Real-ML branch — delegates to the shared `ForecastingInferenceClient`
        # (mirrors ADR-024). Persistence is identical either way.
        if settings.FORECASTING_USE_REAL_ML:
            from src.services.forecasting.inference import get_inference_client

            response = get_inference_client().forecast(request)
            elapsed_ms = (time.perf_counter() - t0) * 1000
            await self._persist(
                forecast_id=response.forecast_id,
                user_id=user_id,
                analysis_type=ForecastAnalysisType.FORECAST,
                series_name=request.series_name,
                request=request,
                response=response,
                processing_time_ms=elapsed_ms,
                horizon_days=horizon,
                base_end_value=response.scenarios["base"].end_value,
                bull_end_value=response.scenarios["bull"].end_value,
                bear_end_value=response.scenarios["bear"].end_value,
                mape=response.mape,
                interpretation=(
                    f"{horizon}-day {response.model_version} forecast for "
                    f"'{request.series_name}': base "
                    f"{response.scenarios['base'].end_value:.2f}, bull "
                    f"{response.scenarios['bull'].end_value:.2f}, bear "
                    f"{response.scenarios['bear'].end_value:.2f}."
                ),
            )
            return response

        # ── Mock path (unchanged) ──────────────────────────────────
        scenarios = {
            label: _build_scenario(request.history, horizon, mult, label)
            for label, mult in _SCENARIO_MULTIPLIERS.items()
        }
        response = ForecastResponse(
            forecast_id=uuid4(),
            series_name=request.series_name,
            generated_at=datetime.now(timezone.utc),
            horizon_days=horizon,
            scenarios=scenarios,
            primary_drivers=[
                SHAPFeature(
                    feature_name="trend",
                    shap_value=0.34,
                    feature_value="upward",
                    contribution_direction="positive",
                    importance_rank=1,
                ),
                SHAPFeature(
                    feature_name="seasonality",
                    shap_value=0.12,
                    feature_value="weekly",
                    contribution_direction="positive",
                    importance_rank=2,
                ),
            ],
            mape=6.4,
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000
        await self._persist(
            forecast_id=response.forecast_id,
            user_id=user_id,
            analysis_type=ForecastAnalysisType.FORECAST,
            series_name=request.series_name,
            request=request,
            response=response,
            processing_time_ms=elapsed_ms,
            horizon_days=horizon,
            base_end_value=scenarios["base"].end_value,
            bull_end_value=scenarios["bull"].end_value,
            bear_end_value=scenarios["bear"].end_value,
            mape=response.mape,
            interpretation=(
                f"{horizon}-day forecast for '{request.series_name}': "
                f"base {scenarios['base'].end_value:.2f}, "
                f"bull {scenarios['bull'].end_value:.2f}, "
                f"bear {scenarios['bear'].end_value:.2f}."
            ),
        )
        return response

    # ── 2. sensitivity ─────────────────────────────────────────────
    async def sensitivity_analysis(
        self, request: SensitivityAnalysisRequest, user_id: UUID
    ) -> SensitivityAnalysisResponse:
        t0 = time.perf_counter()
        bars: list[TornadoBar] = []
        for driver, baseline in request.drivers.items():
            swing = abs(baseline) * request.perturbation_pct
            bars.append(
                TornadoBar(
                    driver=driver,
                    low_impact=round(-swing, 2),
                    high_impact=round(swing, 2),
                    swing=round(2 * swing, 2),
                )
            )
        bars.sort(key=lambda b: b.swing, reverse=True)
        response = SensitivityAnalysisResponse(
            forecast_id=uuid4(),
            tornado=bars,
            most_sensitive_driver=bars[0].driver if bars else "n/a",
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000
        await self._persist(
            forecast_id=response.forecast_id,
            user_id=user_id,
            analysis_type=ForecastAnalysisType.SENSITIVITY,
            series_name=None,
            request=request,
            response=response,
            processing_time_ms=elapsed_ms,
            interpretation=(
                f"Tornado over {len(bars)} drivers — most sensitive: "
                f"{response.most_sensitive_driver}."
            ),
        )
        return response

    # ── 3. what-if ─────────────────────────────────────────────────
    async def what_if(self, request: WhatIfRequest, user_id: UUID) -> WhatIfResponse:
        t0 = time.perf_counter()

        if settings.FORECASTING_USE_REAL_ML:
            from src.services.forecasting.inference import get_inference_client

            response = get_inference_client().what_if(request)
            elapsed_ms = (time.perf_counter() - t0) * 1000
            await self._persist(
                forecast_id=response.forecast_id,
                user_id=user_id,
                analysis_type=ForecastAnalysisType.WHAT_IF,
                series_name=None,
                request=request,
                response=response,
                processing_time_ms=elapsed_ms,
                horizon_days=request.forecast_horizon_days,
                base_end_value=response.baseline_end_value,
                bull_end_value=None,
                bear_end_value=None,
                interpretation=(
                    f"What-if delta {response.delta_pct:+.2%}: baseline "
                    f"{response.baseline_end_value:.2f} → adjusted "
                    f"{response.adjusted_end_value:.2f}."
                ),
            )
            return response

        # ── Mock path (unchanged) ──────────────────────────────────
        base = _build_scenario(request.history, request.forecast_horizon_days, 1.0, "base")
        # Aggregate adjustment factor from the supplied overrides.
        factor = 1.0 + sum(request.adjustments.values()) / max(len(request.adjustments), 1) / 100.0
        adjusted = _build_scenario(
            request.history, request.forecast_horizon_days, factor, "adjusted"
        )
        delta = (adjusted.end_value - base.end_value) / base.end_value if base.end_value else 0.0
        response = WhatIfResponse(
            forecast_id=uuid4(),
            baseline_end_value=base.end_value,
            adjusted_end_value=adjusted.end_value,
            delta_pct=round(delta, 4),
            points=adjusted.points,
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000
        await self._persist(
            forecast_id=response.forecast_id,
            user_id=user_id,
            analysis_type=ForecastAnalysisType.WHAT_IF,
            series_name=None,
            request=request,
            response=response,
            processing_time_ms=elapsed_ms,
            horizon_days=request.forecast_horizon_days,
            base_end_value=base.end_value,
            bull_end_value=None,
            bear_end_value=None,
            interpretation=(
                f"What-if delta {delta:+.2%}: baseline {base.end_value:.2f} → "
                f"adjusted {adjusted.end_value:.2f}."
            ),
        )
        return response

    # ── 4. cross-module ────────────────────────────────────────────
    async def cross_module_forecast(
        self, request: CrossModuleForecastRequest, user_id: UUID
    ) -> ForecastResponse:
        t0 = time.perf_counter()
        horizon = request.forecast_horizon_days

        if settings.FORECASTING_USE_REAL_ML:
            from src.services.forecasting.inference import get_inference_client

            response = get_inference_client().cross_module(request)
            elapsed_ms = (time.perf_counter() - t0) * 1000
            await self._persist(
                forecast_id=response.forecast_id,
                user_id=user_id,
                analysis_type=ForecastAnalysisType.CROSS_MODULE,
                series_name=response.series_name,
                request=request,
                response=response,
                processing_time_ms=elapsed_ms,
                horizon_days=horizon,
                base_end_value=response.scenarios["base"].end_value,
                bull_end_value=response.scenarios["bull"].end_value,
                bear_end_value=response.scenarios["bear"].end_value,
                mape=response.mape,
                interpretation=(
                    f"Cross-module {horizon}-day {response.model_version} forecast — "
                    f"pricing {'on' if request.include_pricing_signals else 'off'}, "
                    f"recruitment {'on' if request.include_recruitment_signals else 'off'}, "
                    f"ESG {'on' if request.include_esg_signals else 'off'}."
                ),
            )
            return response

        # ── Mock path (unchanged) ──────────────────────────────────
        scenarios = {
            label: _build_scenario(request.history, horizon, mult, label)
            for label, mult in _SCENARIO_MULTIPLIERS.items()
        }
        drivers = [
            SHAPFeature(
                feature_name="pricing_signal",
                shap_value=0.18,
                feature_value="active" if request.include_pricing_signals else "off",
                contribution_direction="positive",
                importance_rank=1,
            ),
            SHAPFeature(
                feature_name="recruitment_cost_signal",
                shap_value=-0.09,
                feature_value="active" if request.include_recruitment_signals else "off",
                contribution_direction="negative",
                importance_rank=2,
            ),
            SHAPFeature(
                feature_name="esg_risk_signal",
                shap_value=-0.05,
                feature_value="active" if request.include_esg_signals else "off",
                contribution_direction="negative",
                importance_rank=3,
            ),
        ]
        response = ForecastResponse(
            forecast_id=uuid4(),
            series_name="profit_cross_module",
            generated_at=datetime.now(timezone.utc),
            horizon_days=horizon,
            scenarios=scenarios,
            primary_drivers=drivers,
            mape=5.9,
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000
        await self._persist(
            forecast_id=response.forecast_id,
            user_id=user_id,
            analysis_type=ForecastAnalysisType.CROSS_MODULE,
            series_name=response.series_name,
            request=request,
            response=response,
            processing_time_ms=elapsed_ms,
            horizon_days=horizon,
            base_end_value=scenarios["base"].end_value,
            bull_end_value=scenarios["bull"].end_value,
            bear_end_value=scenarios["bear"].end_value,
            mape=response.mape,
            interpretation=(
                f"Cross-module {horizon}-day forecast — pricing "
                f"{'on' if request.include_pricing_signals else 'off'}, "
                f"recruitment {'on' if request.include_recruitment_signals else 'off'}, "
                f"ESG {'on' if request.include_esg_signals else 'off'}."
            ),
        )
        return response

    # ── 5. explanation (reads from DB) ─────────────────────────────
    async def get_explanation(self, forecast_id: UUID, user_id: UUID) -> dict:
        row = await self._find(forecast_id, user_id)
        response = row.response_payload or {}
        primary = response.get("primary_drivers") or []
        drivers = [
            {
                "feature": d.get("feature_name") or d.get("feature"),
                "shap_value": d.get("shap_value"),
                "direction": d.get("contribution_direction"),
            }
            for d in primary
        ]
        return {
            "forecast_id": str(forecast_id),
            "analysis_type": row.analysis_type.value,
            "series_name": row.series_name,
            "horizon_days": row.horizon_days,
            "drivers": drivers,
            "narrative": row.interpretation
            or response.get("interpretation")
            or "",
        }

    # ── 5a. detail (reads from DB) ─────────────────────────────────
    async def get_forecast_detail(
        self, forecast_id: UUID, user_id: UUID
    ) -> ForecastAnalysisDetailResponse:
        """Reconstruct one persisted forecast row. Backs the audit-feed
        deep-link (TASK-033). 404 via `_find` when not yours."""
        row = await self._find(forecast_id, user_id)
        return ForecastAnalysisDetailResponse(
            forecast_id=row.id,
            analysis_type=row.analysis_type.value,
            series_name=row.series_name,
            created_at=row.created_at,
            model_version=row.model_version,
            processing_time_ms=row.processing_time_ms,
            horizon_days=row.horizon_days,
            base_end_value=row.base_end_value,
            bull_end_value=row.bull_end_value,
            bear_end_value=row.bear_end_value,
            mape=row.mape,
            interpretation=row.interpretation,
            request_payload=row.request_payload or {},
            response_payload=row.response_payload or {},
        )

    # ── 6. history (reads from DB, paged) ──────────────────────────
    async def list_history(
        self,
        user_id: UUID,
        series_name: str | None,
        analysis_type: str | None,
        page: int,
        page_size: int,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> dict:
        page = max(1, page)
        page_size = max(1, min(page_size, 100))
        offset = (page - 1) * page_size

        filters = [ForecastAnalysis.user_id == user_id]
        if series_name is not None:
            filters.append(ForecastAnalysis.series_name == series_name)
        if analysis_type is not None:
            try:
                typed = ForecastAnalysisType(analysis_type)
            except ValueError as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Unknown analysis_type {analysis_type!r}",
                ) from e
            filters.append(ForecastAnalysis.analysis_type == typed)
        # Date-range filter (TASK-037).
        if since is not None:
            filters.append(ForecastAnalysis.created_at >= since)
        if until is not None:
            filters.append(ForecastAnalysis.created_at <= until)

        total = await self.db.scalar(
            select(func.count()).select_from(ForecastAnalysis).where(*filters)
        )
        rows = await self.db.execute(
            select(ForecastAnalysis)
            .where(*filters)
            .order_by(ForecastAnalysis.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        items = [
            {
                "forecast_id": str(r.id),
                "analysis_type": r.analysis_type.value,
                "series_name": r.series_name,
                "horizon_days": r.horizon_days,
                "base_end_value": r.base_end_value,
                "bull_end_value": r.bull_end_value,
                "bear_end_value": r.bear_end_value,
                "mape": r.mape,
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
        forecast_id: UUID,
        user_id: UUID,
        analysis_type: ForecastAnalysisType,
        series_name: str | None,
        request: Any,
        response: Any,
        processing_time_ms: float,
        horizon_days: int | None = None,
        base_end_value: float | None = None,
        bull_end_value: float | None = None,
        bear_end_value: float | None = None,
        mape: float | None = None,
        interpretation: str | None = None,
    ) -> None:
        model_version = _current_model_version()
        row = ForecastAnalysis(
            id=forecast_id,
            user_id=user_id,
            analysis_type=analysis_type,
            series_name=series_name,
            request_payload=request.model_dump(mode="json"),
            response_payload=response.model_dump(mode="json"),
            horizon_days=horizon_days,
            base_end_value=base_end_value,
            bull_end_value=bull_end_value,
            bear_end_value=bear_end_value,
            mape=mape,
            model_version=model_version,
            processing_time_ms=round(processing_time_ms, 3),
            interpretation=interpretation,
        )
        self.db.add(row)
        await self.db.flush()

        # Cross-module audit log (ADR-031). Fire-and-forget. Primary
        # drivers serve as the explanation summary for `forecast` /
        # `cross_module`; `sensitivity` has tornado bars rather than
        # SHAP features (omitted — Phase-4 dashboards treat absence as
        # "no per-driver attribution available").
        response_dump = response.model_dump(mode="json")
        primary_drivers = response_dump.get("primary_drivers") or []
        await AuditService(self.db).record(
            user_id=user_id,
            module=AuditModule.FORECASTING,
            action=analysis_type.value,
            reference_id=forecast_id,
            reference_type="forecast_analysis",
            request_summary={
                "series_name": series_name,
                "horizon_days": horizon_days,
                "include_pricing_signals": getattr(
                    request, "include_pricing_signals", None
                ),
                "include_recruitment_signals": getattr(
                    request, "include_recruitment_signals", None
                ),
                "include_esg_signals": getattr(request, "include_esg_signals", None),
            },
            response_summary={
                "base_end_value": base_end_value,
                "bull_end_value": bull_end_value,
                "bear_end_value": bear_end_value,
                "mape": mape,
                "delta_pct": response_dump.get("delta_pct"),
            },
            explanation_summary=(
                {"primary_drivers": primary_drivers[:3]} if primary_drivers else None
            ),
            risk_tier=None,  # forecasting has no fairness risk tier today
            model_version=model_version,
            latency_ms=round(processing_time_ms, 3),
        )

    async def _find(self, forecast_id: UUID, user_id: UUID) -> ForecastAnalysis:
        result = await self.db.execute(
            select(ForecastAnalysis).where(
                ForecastAnalysis.id == forecast_id,
                ForecastAnalysis.user_id == user_id,
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Forecast analysis {forecast_id} not found",
            )
        return row
