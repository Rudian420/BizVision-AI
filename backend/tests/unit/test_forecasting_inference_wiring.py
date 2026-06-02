"""Offline tests for the forecasting inference orchestrator.

Verifies the wiring (request translation → model fit/predict → response
translation) for all three model-backed endpoints without booting any
heavy ML backbone. We inject a hand-rolled `ForecastModel` factory so
the test doesn't pay the Theta-fit cost; `/sensitivity` is closed-form
and lives in the service layer, not in the inference client.

Mirrors `test_pricing_inference_wiring.py` (TASK-011) for the
forecasting equivalent (TASK-016).
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

pytest.importorskip("ml.forecasting.models.base")

from ml.forecasting.data.schema import (  # noqa: E402
    ForecastInterval,
    ForecastResult,
)
from ml.forecasting.models.base import ForecastModel  # noqa: E402
from src.api.v1.schemas.forecasting import (  # noqa: E402
    CrossModuleForecastRequest,
    ForecastRequest,
    TimeSeriesPoint,
    WhatIfRequest,
)
from src.services.forecasting.inference import (  # noqa: E402
    ForecastingInferenceClient,
    _backtest_mape,
    _scale_dataset,
    get_inference_client,
    reset_inference_client,
)
from src.services.forecasting.ml_translation import (  # noqa: E402
    api_history_to_ml_dataset,
)


# ── Stub model — deterministic, no real fit ─────────────────────────


class StubForecastModel(ForecastModel):
    """Predicts a flat line at `level`. Used to keep the wiring tests
    free of any data-shape dependency."""

    requires_training = False

    def __init__(self, level: float = 100.0) -> None:
        self.level = level
        self.last_fitted_n = 0

    @property
    def name(self) -> str:
        return f"Stub(level={self.level})"

    def fit(self, dataset):
        self.last_fitted_n = len(dataset.points)
        # Reflect the last-value of the dataset so what-if test can
        # distinguish baseline vs adjusted legs.
        self.level = float(dataset.points[-1].y)
        return self

    def predict(self, dataset, horizon: int, pi_alpha: float = 0.05):
        last_ds = dataset.points[-1].ds
        # Build successive ISO date strings for the horizon.
        from datetime import date as _date, timedelta

        start = _date.fromisoformat(last_ds)
        points = tuple(
            ForecastInterval(
                ds=(start + timedelta(days=i + 1)).isoformat(),
                yhat=self.level,
                yhat_lower=self.level * 0.95,
                yhat_upper=self.level * 1.05,
            )
            for i in range(horizon)
        )
        return ForecastResult(
            series_id=dataset.series_id,
            horizon_days=horizon,
            points=points,
            end_value=self.level,
            cumulative_value=self.level * horizon,
            model_name=self.name,
            sub_scores={"alpha": 0.3, "trend_slope": 0.0},
        )


def _history(n: int = 20):
    """Long enough that the per-call backtest split runs."""
    return [TimeSeriesPoint(ds=date(2026, 1, 1 + i), y=100.0 + i) for i in range(n)]


@pytest.fixture(autouse=True)
def reset_singleton():
    reset_inference_client(None)
    yield
    reset_inference_client(None)


# ── forecast ────────────────────────────────────────────────────────


def test_forecast_uses_injected_factory_and_returns_three_scenarios():
    client = ForecastingInferenceClient(model_factory=StubForecastModel)
    request = ForecastRequest(
        history=_history(20),
        series_name="profit",
        forecast_horizon_days=5,
    )
    response = client.forecast(request)

    assert set(response.scenarios.keys()) == {"base", "bull", "bear"}
    base_last = response.scenarios["base"].points[-1].yhat
    bull_last = response.scenarios["bull"].points[-1].yhat
    assert bull_last == pytest.approx(base_last * 1.15, rel=1e-3)
    assert response.model_version == "Stub(level=119.0)"


def test_forecast_id_round_trip():
    client = ForecastingInferenceClient(model_factory=StubForecastModel)
    fixed_id = uuid4()
    request = ForecastRequest(
        history=_history(15), forecast_horizon_days=3
    )
    response = client.forecast(request, forecast_id=fixed_id)
    assert response.forecast_id == fixed_id


# ── what_if ─────────────────────────────────────────────────────────


def test_what_if_baseline_and_adjusted_differ_by_adjustment_factor():
    """The Stub model reads the last value of its training dataset; the
    adjusted leg multiplies the dataset by `factor` before fitting, so
    the adjusted level should be `baseline · factor` (within rounding)."""
    client = ForecastingInferenceClient(model_factory=StubForecastModel)
    request = WhatIfRequest(
        history=_history(20),
        adjustments={"price_uplift_pct": 10.0},
        forecast_horizon_days=3,
    )
    response = client.what_if(request)
    # mean adjustment / 100 = 0.10 -> factor = 1.10
    assert response.baseline_end_value == pytest.approx(119.0)  # last(history) = 100+19
    assert response.adjusted_end_value == pytest.approx(119.0 * 1.10)
    assert response.delta_pct == pytest.approx(0.10, rel=1e-3)


def test_what_if_zero_adjustments_gives_zero_delta():
    client = ForecastingInferenceClient(model_factory=StubForecastModel)
    request = WhatIfRequest(
        history=_history(20),
        adjustments={"a": 0.0, "b": 0.0},
        forecast_horizon_days=3,
    )
    response = client.what_if(request)
    assert response.delta_pct == pytest.approx(0.0)
    assert response.baseline_end_value == pytest.approx(response.adjusted_end_value)


# ── cross_module ────────────────────────────────────────────────────


def test_cross_module_response_uses_signal_drivers():
    client = ForecastingInferenceClient(model_factory=StubForecastModel)
    request = CrossModuleForecastRequest(
        history=_history(20),
        forecast_horizon_days=3,
        include_pricing_signals=False,
        include_recruitment_signals=True,
        include_esg_signals=False,
    )
    response = client.cross_module(request)
    feature_names = [d.feature_name for d in response.primary_drivers]
    assert feature_names == [
        "pricing_signal",
        "recruitment_cost_signal",
        "esg_risk_signal",
    ]
    assert response.primary_drivers[0].feature_value == "off"
    assert response.primary_drivers[1].feature_value == "active"
    assert response.series_name == "profit_cross_module"


# ── source tracking + singleton ─────────────────────────────────────


def test_source_is_injected_when_factory_provided():
    """When a factory is injected the client stays at the
    `uninitialised` source — production sets it via the loader."""
    client = ForecastingInferenceClient(model_factory=StubForecastModel)
    # Trigger a call so `source` would otherwise be set by `_load_model_class`.
    request = ForecastRequest(history=_history(15), forecast_horizon_days=3)
    _ = client.forecast(request)
    # Injection path never touches the registry/bootstrap loader.
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


# ── _scale_dataset (helper) ─────────────────────────────────────────


def test_scale_dataset_preserves_length_and_series_id():
    ds = api_history_to_ml_dataset(_history(10), series_id="test")
    scaled = _scale_dataset(ds, factor=1.5)
    assert len(scaled.points) == 10
    assert scaled.series_id == "test"
    # First original value was 100 -> scaled = 150
    assert scaled.points[0].y == pytest.approx(150.0)
    assert scaled.points[-1].y == pytest.approx(scaled.points[-1].y)


def test_scale_dataset_unity_factor_preserves_values():
    ds = api_history_to_ml_dataset(_history(5))
    scaled = _scale_dataset(ds, factor=1.0)
    assert [p.y for p in scaled.points] == [p.y for p in ds.points]


# ── _backtest_mape ───────────────────────────────────────────────────


def test_backtest_mape_returns_none_when_history_too_short():
    """The helper protects the request-path latency budget by skipping
    backtest on histories too short to split."""
    short_ds = api_history_to_ml_dataset(_history(7))
    out = _backtest_mape(model_factory=StubForecastModel, dataset=short_ds)
    assert out is None


def test_backtest_mape_returns_fraction_on_sufficient_history():
    """With a flat-line stub on a slightly trending series, MAPE should
    be a small positive fraction (NOT NaN, NOT a percentage)."""
    ds = api_history_to_ml_dataset(_history(50))
    out = _backtest_mape(model_factory=StubForecastModel, dataset=ds)
    assert out is not None
    assert 0.0 <= out <= 1.0
