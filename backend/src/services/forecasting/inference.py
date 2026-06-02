"""
Forecasting ML Inference Client.

Wraps `ml.forecasting` for the backend — the forecasting analogue of
`PricingInferenceClient` (ADR-024) and `RecruitmentInferenceClient`.
Owns the lifecycle of the fitted forecast model:

    1. **Singleton cache** — one client per worker process; instantiated
       lazily on first call so an idle backend never imports
       `ml.forecasting` and its numpy chain.
    2. **MLflow Model Registry** — preferred source of a fitted model,
       loaded from the `profit-forecasting-ensemble` Production stage
       when present.
    3. **Deterministic bootstrap** — if no registered model exists,
       instantiate a `ThetaForecaster` (closed-form, no fit cost at
       construction time; per-call `fit` on the request's inline
       history). Logged loudly so operators can't miss the fallback.

The `ml.forecasting` import (with its numpy chain) happens **inside**
`_load_model_class` — when `FORECASTING_USE_REAL_ML` is off, this
module imports cleanly. The translation layer (`ml_translation.py`)
is pure-Python and *never* touches a heavy import, so unit tests for
translation run in the backend's lean dev venv.

Endpoints handled:
  • `forecast(request)`           →  `/forecasting/forecast`
  • `what_if(request)`            →  `/forecasting/what-if`
  • `cross_module(request)`       →  `/forecasting/cross-module`

`/sensitivity` stays closed-form (tornado from perturbation pct, no
fitted model needed) — same posture as pricing's `/elasticity` per
the pricing inference client. The forecasting service applies the
closed-form path inline rather than routing through this client.

Unlike pricing — which carries a single fitted policy across requests
— forecasting requires a fit *per request* because the caller supplies
its own inline history. The "model" the inference client holds is
therefore the *model class* (an unfitted constructor) plus its
hyperparameters; `fit` runs on every request against the caller's
history. This is cheap for Theta (closed-form OLS + SES) and
HoltWinters (numpy recursion over a small grid).
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING, Any
from uuid import UUID

from src.api.v1.schemas.forecasting import (
    CrossModuleForecastRequest,
    ForecastRequest,
    ForecastResponse,
    WhatIfRequest,
    WhatIfResponse,
)
from src.core.logging import get_logger
from src.services.forecasting.ml_translation import (
    adjustment_factor,
    api_history_to_ml_dataset,
    ml_cross_module_to_api,
    ml_forecast_to_api,
    ml_what_if_to_api,
)

if TYPE_CHECKING:
    from ml.forecasting.models.base import ForecastModel

logger = get_logger(__name__)


# ── Public API ────────────────────────────────────────────────────────


class ForecastingInferenceClient:
    """Thread-safe lazy holder for the forecasting model class.

    Construction is cheap — heavy imports happen on the first call to
    `forecast` / `what_if` / `cross_module`. The `_lock` makes first-
    call init safe under FastAPI's threadpool concurrency.
    """

    def __init__(
        self,
        *,
        model_factory: Any | None = None,
        season_length: int = 7,
        pi_alpha: float = 0.05,
    ) -> None:
        # Injection seam for tests; production leaves it None.
        # The factory is `() -> ForecastModel`; we call it per request.
        self._model_factory: Any | None = model_factory
        self._season_length = season_length
        self._pi_alpha = pi_alpha
        self._lock = threading.Lock()
        self._source: str = "uninitialised"

    @property
    def source(self) -> str:
        """`mlflow:v3` / `theta-bootstrap` / `injected` / `uninitialised`."""
        return self._source

    # ── 1. /forecast ────────────────────────────────────────────────
    def forecast(
        self,
        request: ForecastRequest,
        *,
        forecast_id: UUID | None = None,
    ) -> ForecastResponse:
        model = self._build_model()
        dataset = api_history_to_ml_dataset(request.history, series_id=request.series_name)
        model.fit(dataset)
        result = model.predict(
            dataset,
            horizon=request.forecast_horizon_days,
            pi_alpha=self._pi_alpha,
        )
        backtest_mape = _backtest_mape(model_factory=self._build_model, dataset=dataset)
        return ml_forecast_to_api(
            result=result,
            request=request,
            backtest_mape=backtest_mape,
            forecast_id=forecast_id,
        )

    # ── 2. /what-if ─────────────────────────────────────────────────
    def what_if(
        self,
        request: WhatIfRequest,
        *,
        forecast_id: UUID | None = None,
    ) -> WhatIfResponse:
        dataset = api_history_to_ml_dataset(request.history)
        # Baseline: fit on the inline history, no adjustment.
        baseline_model = self._build_model().fit(dataset)
        baseline_result = baseline_model.predict(
            dataset,
            horizon=request.forecast_horizon_days,
            pi_alpha=self._pi_alpha,
        )
        # Adjusted: apply a scalar to the inline history's last-N levels
        # so the same model reflects the what-if uplift / cut. Simpler and
        # more faithful than re-fitting on a shifted series — the mock
        # uses the identical posture.
        factor = adjustment_factor(request.adjustments)
        adjusted_dataset = _scale_dataset(dataset, factor)
        adjusted_model = self._build_model().fit(adjusted_dataset)
        adjusted_result = adjusted_model.predict(
            adjusted_dataset,
            horizon=request.forecast_horizon_days,
            pi_alpha=self._pi_alpha,
        )
        return ml_what_if_to_api(
            baseline_result=baseline_result,
            adjusted_result=adjusted_result,
            request=request,
            forecast_id=forecast_id,
        )

    # ── 3. /cross-module ────────────────────────────────────────────
    def cross_module(
        self,
        request: CrossModuleForecastRequest,
        *,
        forecast_id: UUID | None = None,
    ) -> ForecastResponse:
        model = self._build_model()
        dataset = api_history_to_ml_dataset(request.history, series_id="profit_cross_module")
        model.fit(dataset)
        result = model.predict(
            dataset,
            horizon=request.forecast_horizon_days,
            pi_alpha=self._pi_alpha,
        )
        backtest_mape = _backtest_mape(model_factory=self._build_model, dataset=dataset)
        return ml_cross_module_to_api(
            result=result,
            request=request,
            backtest_mape=backtest_mape,
            forecast_id=forecast_id,
        )

    # ── internals ────────────────────────────────────────────────────
    def _build_model(self) -> ForecastModel:
        """Return a fresh, unfitted `ForecastModel` instance."""
        factory = self._resolve_factory()
        return factory()

    def _resolve_factory(self) -> Any:
        if self._model_factory is not None:
            return self._model_factory
        with self._lock:
            if self._model_factory is None:
                factory, source = _load_model_class()
                self._model_factory = factory
                self._source = source
                logger.info("Forecasting model initialised from {}", self._source)
        return self._model_factory


# ── Loader ────────────────────────────────────────────────────────────


def _load_model_class() -> tuple[Any, str]:
    """Choose a model-class source in priority order.

    The `ml.forecasting` imports live here so the backend stays
    importable without the ML deps.
    """
    try:  # ensure ml.forecasting is importable before we try anything
        from ml.forecasting.models.theta import ThetaForecaster  # noqa: F401
    except ImportError as exc:
        raise RuntimeError(
            "FORECASTING_USE_REAL_ML=True but `ml.forecasting` is not importable. "
            "Install ml/requirements.txt or run the backend inside the ml-dev container."
        ) from exc

    # ── 1. MLflow Production model, if present ────────────────────
    registry_model = _load_from_registry()
    if registry_model is not None:
        factory, version = registry_model
        return factory, f"mlflow:{version}"

    # ── 2. Deterministic Theta bootstrap ──────────────────────────
    logger.warning(
        "No Production `profit-forecasting-ensemble` in MLflow — "
        "bootstrapping ThetaForecaster (closed-form). Replace via "
        "`python -m ml.forecasting.cli train`."
    )
    from ml.forecasting.models.theta import ThetaForecaster

    return ThetaForecaster, "theta-bootstrap"


def _load_from_registry() -> tuple[Any, str] | None:
    """Try MLflow Model Registry; swallow errors so a missing tracking
    server falls back to the bootstrap rather than crashing."""
    try:
        from ml.forecasting.registry.model_registry import latest_production

        version = latest_production()
        if version is None:
            return None
        import mlflow.pyfunc

        loaded = mlflow.pyfunc.load_model(version.source)

        # Wrap the loaded pyfunc in a no-arg factory so the rest of the
        # client treats it like any other model class. The loaded model
        # is expected to expose `fit` + `predict` matching the
        # `ForecastModel` ABC; production training runs register exactly
        # that shape.
        def _factory():
            return loaded

        return _factory, str(version.version)
    except Exception as exc:  # pragma: no cover - depends on live MLflow
        logger.info("MLflow Model Registry unavailable ({}); using bootstrap.", exc)
        return None


# ── Helpers ───────────────────────────────────────────────────────────


def _scale_dataset(dataset: Any, factor: float) -> Any:
    """Return a `TimeSeriesDataset` with every value multiplied by `factor`.

    Pure helper — kept here rather than in `ml_translation` because it
    operates on `ml.forecasting` dataclasses and is only used by the
    inference client's what-if path.
    """
    from ml.forecasting.data.schema import (
        TimeSeriesDataset as MLTimeSeriesDataset,
    )
    from ml.forecasting.data.schema import (
        TimeSeriesPoint as MLTimeSeriesPoint,
    )

    return MLTimeSeriesDataset(
        series_id=dataset.series_id,
        frequency=dataset.frequency,
        points=tuple(
            MLTimeSeriesPoint(ds=p.ds, y=p.y * factor, series_id=p.series_id)
            for p in dataset.points
        ),
    )


def _backtest_mape(*, model_factory: Any, dataset: Any) -> float | None:
    """Run a single-fold holdout backtest on the inline history.

    The harness's full rolling-origin backtest is too heavy to run per
    request (multiple refits). One holdout fold gives a defensible MAPE
    for the response payload's `mape` field without blowing the latency
    budget. Returns `None` if the history is too short to split.
    """
    n = len(dataset)
    horizon = max(7, n // 10)
    if n <= horizon + 7:
        return None
    try:
        from ml.forecasting.data.loader import split_train_test
        from ml.forecasting.evaluation.metrics import (
            mean_absolute_percentage_error,
        )

        train_ds, test_ds = split_train_test(dataset, horizon=horizon)
        model = model_factory()
        model.fit(train_ds)
        result = model.predict(train_ds, horizon=horizon)
        y_true = [p.y for p in test_ds.points]
        y_pred = [p.yhat for p in result.points]
        return float(mean_absolute_percentage_error(y_true, y_pred))
    except Exception as exc:  # pragma: no cover - defensive
        logger.info("Backtest skipped ({}); response.mape will be 0.", exc)
        return None


# ── Module-level singleton ──────────────────────────────────────────
# Created once per process. Construction is cheap (no heavy imports);
# `forecast` / `what_if` / `cross_module` trigger the first load.


_client_singleton: ForecastingInferenceClient | None = None
_singleton_lock = threading.Lock()


def get_inference_client() -> ForecastingInferenceClient:
    """Return the process-wide forecasting inference client."""
    global _client_singleton
    if _client_singleton is None:
        with _singleton_lock:
            if _client_singleton is None:
                _client_singleton = ForecastingInferenceClient()
    return _client_singleton


def reset_inference_client(client: ForecastingInferenceClient | None = None) -> None:
    """Replace the singleton — testing seam only. Pass `None` to clear."""
    global _client_singleton
    with _singleton_lock:
        _client_singleton = client
