"""
API ↔ `ml.forecasting` schema translation.

Pure Python, zero heavy ML imports — same architectural seam as
`backend/src/services/pricing/ml_translation.py` (ADR-024). The backend
speaks **Pydantic schemas** (`src.api.v1.schemas.forecasting`); the ML
package speaks **frozen dataclasses** (`ml.forecasting.data.schema`);
this module is the *only* place that knows about both.

Forecasting has four endpoints (`/forecast` · `/sensitivity` · `/what-if`
· `/cross-module`), three of which are model-backed and one of which is
closed-form (`/sensitivity` — tornado from perturbation pct). We provide
one function per direction per endpoint and keep them pure (no I/O, no
module-level imports of `ml.forecasting.models.*`).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from src.api.v1.schemas.common import SHAPFeature
from src.api.v1.schemas.forecasting import (
    CrossModuleForecastRequest,
    ForecastPoint,
    ForecastRequest,
    ForecastResponse,
    ScenarioForecast,
    WhatIfRequest,
    WhatIfResponse,
)

if TYPE_CHECKING:
    # Imports for type-checker only — keeps this module importable in the
    # backend's lean runtime image where ml/ may not be on sys.path.
    from ml.forecasting.data.schema import (
        ForecastResult as MLForecastResult,
    )
    from ml.forecasting.data.schema import (
        TimeSeriesDataset as MLTimeSeriesDataset,
    )

# Scenario multipliers — kept in sync with the mock branch in
# `forecasting_service.py`. ±15% spread is the convention from the
# original Phase-1 service.
_BULL_MULTIPLIER = 1.15
_BEAR_MULTIPLIER = 0.85


# ── API → ml.forecasting ────────────────────────────────────────────


def api_history_to_ml_dataset(
    history,  # list[TimeSeriesPoint] from any forecasting request
    series_id: str = "default",
) -> MLTimeSeriesDataset:
    """Convert a Pydantic history list to an `ml.forecasting.TimeSeriesDataset`."""
    from ml.forecasting.data.schema import (
        TimeSeriesDataset as MLTimeSeriesDatasetImpl,
    )
    from ml.forecasting.data.schema import (
        TimeSeriesPoint as MLTimeSeriesPointImpl,
    )

    points = tuple(
        MLTimeSeriesPointImpl(ds=p.ds.isoformat(), y=float(p.y), series_id=series_id)
        for p in history
    )
    return MLTimeSeriesDatasetImpl(
        series_id=series_id,
        frequency="D",
        points=points,
    )


# ── ml.forecasting → API ────────────────────────────────────────────


def _scale_result(
    result: MLForecastResult, multiplier: float, label: str
) -> ScenarioForecast:
    """Apply a scalar multiplier to a point forecast → ScenarioForecast.

    Used to derive `bull` / `bear` scenarios from a single fitted
    model — matching the Phase-1 mock's posture so the response shape
    is identical whichever branch ran. Lower/upper bounds scale with
    the centre so the PI is preserved relative to the new level.
    """
    from datetime import date

    api_points: list[ForecastPoint] = []
    cumulative = 0.0
    for p in result.points:
        centre = p.yhat * multiplier
        half_width = (p.yhat_upper - p.yhat_lower) / 2.0 * multiplier
        api_points.append(
            ForecastPoint(
                ds=date.fromisoformat(p.ds),
                yhat=round(centre, 2),
                yhat_lower=round(centre - half_width, 2),
                yhat_upper=round(centre + half_width, 2),
            )
        )
        cumulative += centre
    return ScenarioForecast(
        scenario=label,
        points=api_points,
        end_value=round(api_points[-1].yhat, 2) if api_points else 0.0,
        cumulative_value=round(cumulative, 2),
    )


def _drivers_from_sub_scores(
    sub_scores: dict[str, float] | None,
    model_name: str,
) -> list[SHAPFeature]:
    """Translate a model's `sub_scores` into the API's `SHAPFeature` list.

    Phase-3 wave 1 uses classical arms (Theta / HoltWinters) whose
    sub_scores are smoothing coefficients (α/β/γ) or trend stats, not
    true SHAP values. We surface them with neutral magnitudes and
    informative names so the response shape stays stable; real SHAP
    arrives when LightGBM / XGBoost arms land (ML-FOR-002 expansion).
    """
    sub_scores = sub_scores or {}
    drivers: list[SHAPFeature] = []
    if "trend_slope" in sub_scores:
        slope = float(sub_scores["trend_slope"])
        drivers.append(
            SHAPFeature(
                feature_name="trend",
                shap_value=abs(slope),
                feature_value="upward" if slope >= 0 else "downward",
                contribution_direction="positive" if slope >= 0 else "negative",
                importance_rank=1,
            )
        )
    if "alpha" in sub_scores:
        drivers.append(
            SHAPFeature(
                feature_name="level_smoothing",
                shap_value=float(sub_scores["alpha"]),
                feature_value=f"α={sub_scores['alpha']:.2f}",
                contribution_direction="positive",
                importance_rank=len(drivers) + 1,
            )
        )
    if "gamma" in sub_scores:
        drivers.append(
            SHAPFeature(
                feature_name="seasonal_smoothing",
                shap_value=float(sub_scores["gamma"]),
                feature_value=f"γ={sub_scores['gamma']:.2f}",
                contribution_direction="positive",
                importance_rank=len(drivers) + 1,
            )
        )
    if not drivers:
        drivers.append(
            SHAPFeature(
                feature_name="model",
                shap_value=0.0,
                feature_value=model_name,
                contribution_direction="positive",
                importance_rank=1,
            )
        )
    return drivers


def ml_forecast_to_api(
    *,
    result: MLForecastResult,
    request: ForecastRequest,
    backtest_mape: float | None,
    forecast_id: UUID | None = None,
) -> ForecastResponse:
    """Wrap a single `ml.forecasting.ForecastResult` into the
    `/forecast` API response, expanding scenarios from the base centre."""
    base = _scale_result(result, multiplier=1.0, label="base")
    bull = _scale_result(result, multiplier=_BULL_MULTIPLIER, label="bull")
    bear = _scale_result(result, multiplier=_BEAR_MULTIPLIER, label="bear")

    return ForecastResponse(
        forecast_id=forecast_id or uuid4(),
        series_name=request.series_name,
        generated_at=datetime.now(timezone.utc),
        horizon_days=request.forecast_horizon_days,
        scenarios={"base": base, "bull": bull, "bear": bear},
        primary_drivers=_drivers_from_sub_scores(result.sub_scores, result.model_name),
        mape=round(backtest_mape * 100.0, 2) if backtest_mape is not None else 0.0,
        model_version=result.model_name,
    )


def ml_what_if_to_api(
    *,
    baseline_result: MLForecastResult,
    adjusted_result: MLForecastResult,
    request: WhatIfRequest,
    forecast_id: UUID | None = None,
) -> WhatIfResponse:
    """Translate paired (baseline, adjusted) forecasts into a `/what-if`
    API response. The `points` list reflects the adjusted leg, matching
    the mock service's convention."""
    from datetime import date

    base_end = baseline_result.end_value
    adj_end = adjusted_result.end_value
    delta = (adj_end - base_end) / base_end if base_end else 0.0

    points = [
        ForecastPoint(
            ds=date.fromisoformat(p.ds),
            yhat=round(p.yhat, 2),
            yhat_lower=round(p.yhat_lower, 2),
            yhat_upper=round(p.yhat_upper, 2),
        )
        for p in adjusted_result.points
    ]
    return WhatIfResponse(
        forecast_id=forecast_id or uuid4(),
        baseline_end_value=round(base_end, 2),
        adjusted_end_value=round(adj_end, 2),
        delta_pct=round(delta, 4),
        points=points,
    )


def ml_cross_module_to_api(
    *,
    result: MLForecastResult,
    request: CrossModuleForecastRequest,
    backtest_mape: float | None,
    forecast_id: UUID | None = None,
) -> ForecastResponse:
    """`/cross-module` translates the same way as `/forecast`, but
    `primary_drivers` includes the cross-module signal toggles instead
    of the model's internal sub-scores. Keeps response shape parity
    with the mock branch in `forecasting_service.cross_module_forecast`."""
    base = _scale_result(result, multiplier=1.0, label="base")
    bull = _scale_result(result, multiplier=_BULL_MULTIPLIER, label="bull")
    bear = _scale_result(result, multiplier=_BEAR_MULTIPLIER, label="bear")

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
    return ForecastResponse(
        forecast_id=forecast_id or uuid4(),
        series_name="profit_cross_module",
        generated_at=datetime.now(timezone.utc),
        horizon_days=request.forecast_horizon_days,
        scenarios={"base": base, "bull": bull, "bear": bear},
        primary_drivers=drivers,
        mape=round(backtest_mape * 100.0, 2) if backtest_mape is not None else 0.0,
        model_version=result.model_name,
    )


# ── What-if adjustment derivation ───────────────────────────────────


def adjustment_factor(adjustments: dict[str, float]) -> float:
    """Aggregate a `/what-if` adjustments dict into a single scalar.

    Mirrors the mock branch:
      `factor = 1 + (mean(adjustments.values()) / 100)`

    Keeping this in one place makes it trivial to swap in a driver-aware
    formula later (e.g. fitted price-elasticity on the *pricing* signal,
    capacity scaling on the *headcount* signal). For wave 1 we stay
    aligned with the mock so flag flips don't change behaviour shape.
    """
    if not adjustments:
        return 1.0
    mean_pct = sum(adjustments.values()) / len(adjustments)
    return 1.0 + (mean_pct / 100.0)
