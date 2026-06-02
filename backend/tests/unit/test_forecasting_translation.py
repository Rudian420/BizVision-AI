"""Offline tests for the forecasting API↔ml.forecasting translation layer.

Pure-Python — no DB, no FastAPI fixtures. Verifies that the schema
translation preserves field shapes, applies the bull/bear multipliers
correctly, and surfaces the model's sub_scores as `primary_drivers`.

Mirrors `test_pricing_translation.py` (TASK-011) for the forecasting
equivalent (TASK-016).
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path
from uuid import uuid4

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

pytest.importorskip("ml.forecasting.data.schema")

from ml.forecasting.data.schema import (  # noqa: E402
    ForecastInterval,
    ForecastResult,
)
from src.api.v1.schemas.forecasting import (  # noqa: E402
    CrossModuleForecastRequest,
    ForecastRequest,
    TimeSeriesPoint,
    WhatIfRequest,
)
from src.services.forecasting.ml_translation import (  # noqa: E402
    adjustment_factor,
    api_history_to_ml_dataset,
    ml_cross_module_to_api,
    ml_forecast_to_api,
    ml_what_if_to_api,
)


def _history(n: int = 10, start_value: float = 100.0):
    return [
        TimeSeriesPoint(ds=date(2026, 1, i + 1), y=start_value + i)
        for i in range(n)
    ]


def _ml_result(
    *,
    n_points: int = 5,
    base_yhat: float = 110.0,
    model_name: str = "Theta",
    sub_scores: dict[str, float] | None = None,
) -> ForecastResult:
    points = tuple(
        ForecastInterval(
            ds=f"2026-02-{i + 1:02d}",
            yhat=base_yhat + i,
            yhat_lower=(base_yhat + i) * 0.95,
            yhat_upper=(base_yhat + i) * 1.05,
        )
        for i in range(n_points)
    )
    return ForecastResult(
        series_id="profit",
        horizon_days=n_points,
        points=points,
        end_value=points[-1].yhat,
        cumulative_value=sum(p.yhat for p in points),
        model_name=model_name,
        sub_scores=sub_scores or {},
    )


# ── api_history_to_ml_dataset ──────────────────────────────────────


def test_history_to_ml_dataset_preserves_order_and_values():
    history = _history(5, start_value=100.0)
    ds = api_history_to_ml_dataset(history, series_id="profit")
    assert ds.series_id == "profit"
    assert ds.frequency == "D"
    assert len(ds.points) == 5
    assert ds.points[0].ds == "2026-01-01"
    assert ds.points[0].y == 100.0
    assert ds.points[-1].y == 104.0


# ── ml_forecast_to_api ─────────────────────────────────────────────


def test_forecast_response_has_three_scenarios_with_correct_multipliers():
    request = ForecastRequest(
        history=_history(10), forecast_horizon_days=5
    )
    result = _ml_result(n_points=5, base_yhat=200.0)
    response = ml_forecast_to_api(
        result=result, request=request, backtest_mape=0.04
    )
    assert set(response.scenarios.keys()) == {"base", "bull", "bear"}

    base_last = response.scenarios["base"].points[-1].yhat
    bull_last = response.scenarios["bull"].points[-1].yhat
    bear_last = response.scenarios["bear"].points[-1].yhat
    assert bull_last == pytest.approx(base_last * 1.15, rel=1e-3)
    assert bear_last == pytest.approx(base_last * 0.85, rel=1e-3)


def test_forecast_response_surfaces_theta_sub_scores_as_drivers():
    request = ForecastRequest(history=_history(10), forecast_horizon_days=3)
    result = _ml_result(
        sub_scores={"alpha": 0.4, "trend_slope": 1.2, "trend_intercept": 50.0}
    )
    response = ml_forecast_to_api(result=result, request=request, backtest_mape=0.05)
    feature_names = {d.feature_name for d in response.primary_drivers}
    assert "trend" in feature_names
    assert "level_smoothing" in feature_names


def test_forecast_response_drivers_fallback_when_no_sub_scores():
    """A model with empty sub_scores (e.g. NaiveLast) still gets one
    `model` driver entry — so the response always has ≥ 1 driver."""
    request = ForecastRequest(history=_history(10), forecast_horizon_days=3)
    result = _ml_result(model_name="NaiveLast", sub_scores={})
    response = ml_forecast_to_api(result=result, request=request, backtest_mape=None)
    assert len(response.primary_drivers) == 1
    assert response.primary_drivers[0].feature_name == "model"
    assert response.primary_drivers[0].feature_value == "NaiveLast"


def test_forecast_response_mape_is_scaled_to_percentage():
    """The API contract surfaces MAPE as a *percentage* (e.g. 4.2),
    while `ml.forecasting` returns it as a *fraction* (e.g. 0.042)."""
    request = ForecastRequest(history=_history(10), forecast_horizon_days=3)
    result = _ml_result()
    response = ml_forecast_to_api(result=result, request=request, backtest_mape=0.042)
    assert response.mape == pytest.approx(4.2)


def test_forecast_response_mape_zero_when_backtest_unavailable():
    request = ForecastRequest(history=_history(10), forecast_horizon_days=3)
    response = ml_forecast_to_api(
        result=_ml_result(), request=request, backtest_mape=None
    )
    assert response.mape == 0.0


# ── ml_what_if_to_api ──────────────────────────────────────────────


def test_what_if_delta_is_signed_fraction():
    request = WhatIfRequest(
        history=_history(10),
        adjustments={"price_uplift_pct": 5.0},
        forecast_horizon_days=3,
    )
    baseline = _ml_result(n_points=3, base_yhat=100.0)
    adjusted = _ml_result(n_points=3, base_yhat=105.0)
    response = ml_what_if_to_api(
        baseline_result=baseline, adjusted_result=adjusted, request=request
    )
    # adjusted end - baseline end = 107 - 102 = 5; baseline end = 102
    assert response.baseline_end_value == pytest.approx(102.0)
    assert response.adjusted_end_value == pytest.approx(107.0)
    assert response.delta_pct == pytest.approx((107.0 - 102.0) / 102.0, rel=1e-3)


def test_what_if_points_reflect_adjusted_leg():
    request = WhatIfRequest(
        history=_history(10),
        adjustments={"k": 1.0},
        forecast_horizon_days=3,
    )
    baseline = _ml_result(n_points=3, base_yhat=100.0)
    adjusted = _ml_result(n_points=3, base_yhat=120.0)
    response = ml_what_if_to_api(
        baseline_result=baseline, adjusted_result=adjusted, request=request
    )
    # Adjusted result has yhats 120, 121, 122
    assert response.points[0].yhat == pytest.approx(120.0)
    assert response.points[-1].yhat == pytest.approx(122.0)


# ── ml_cross_module_to_api ─────────────────────────────────────────


def test_cross_module_response_uses_signal_drivers_not_model_subscores():
    """`/cross-module` ignores model sub_scores — it surfaces the
    pricing/recruitment/ESG toggles as drivers regardless."""
    request = CrossModuleForecastRequest(
        history=_history(10),
        forecast_horizon_days=3,
        include_pricing_signals=True,
        include_recruitment_signals=False,
        include_esg_signals=True,
    )
    # The result HAS sub_scores; the response should not surface them.
    result = _ml_result(sub_scores={"alpha": 0.5, "trend_slope": 1.0})
    response = ml_cross_module_to_api(
        result=result, request=request, backtest_mape=0.03
    )
    feature_names = [d.feature_name for d in response.primary_drivers]
    assert feature_names == [
        "pricing_signal",
        "recruitment_cost_signal",
        "esg_risk_signal",
    ]
    # The toggle values reflect the request flags.
    pricing_driver = response.primary_drivers[0]
    assert pricing_driver.feature_value == "active"
    recruitment_driver = response.primary_drivers[1]
    assert recruitment_driver.feature_value == "off"


def test_cross_module_response_overrides_series_name():
    """Regardless of the inline request, cross-module always uses the
    canonical `profit_cross_module` series_name."""
    request = CrossModuleForecastRequest(
        history=_history(10), forecast_horizon_days=3
    )
    response = ml_cross_module_to_api(
        result=_ml_result(), request=request, backtest_mape=None
    )
    assert response.series_name == "profit_cross_module"


# ── adjustment_factor ──────────────────────────────────────────────


def test_adjustment_factor_handworked_mean():
    """factor = 1 + mean(adjustments)/100, matching the mock branch."""
    assert adjustment_factor({"a": 5.0, "b": 15.0}) == pytest.approx(1.10)
    # negative adjustments shrink
    assert adjustment_factor({"a": -10.0, "b": -20.0}) == pytest.approx(0.85)


def test_adjustment_factor_empty_returns_unity():
    assert adjustment_factor({}) == 1.0


# ── forecast_id round-trip ─────────────────────────────────────────


def test_forecast_id_is_used_when_provided():
    fixed_id = uuid4()
    request = ForecastRequest(history=_history(10), forecast_horizon_days=3)
    response = ml_forecast_to_api(
        result=_ml_result(), request=request, backtest_mape=None, forecast_id=fixed_id
    )
    assert response.forecast_id == fixed_id
