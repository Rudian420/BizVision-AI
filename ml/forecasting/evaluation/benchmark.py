"""
Backtest harness — rolling-origin evaluation.

Holdout split is fine for a single end-of-history report, but rolling-
origin (a.k.a. expanding-window cross-validation) is what the M4 / M5
competitions report on and what AS-003 will use.

Returns a per-arm summary dict with MAPE / sMAPE / RMSE / MASE / Winkler
/ coverage aggregated across folds. The harness treats every arm
uniformly — it only calls the `ForecastModel` ABC, never any concrete
class — which is why the uniform-interface decision (ADR-022 in
recruitment, applied here for forecasting) matters.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ml.forecasting.data.schema import TimeSeriesDataset
from ml.forecasting.evaluation.metrics import (
    coverage,
    mean_absolute_percentage_error,
    mean_absolute_scaled_error,
    root_mean_squared_error,
    symmetric_mape,
    winkler_score,
)
from ml.forecasting.models.base import ForecastModel


@dataclass(frozen=True)
class ArmResult:
    """Aggregated cross-fold metrics for a single forecasting arm."""

    name: str
    n_folds: int
    mape: float
    smape: float
    rmse: float
    mase: float
    winkler: float
    coverage: float


def rolling_origin_backtest(
    dataset: TimeSeriesDataset,
    model: ForecastModel,
    horizon: int,
    n_folds: int = 5,
    season_length: int = 7,
    pi_alpha: float = 0.05,
) -> ArmResult:
    """Expanding-window CV: refit on each fold, score on the next `horizon`.

    Fold 0 trains on `[0, n - n_folds·horizon)`; fold k trains on
    `[0, n - (n_folds-k)·horizon)`. Always strictly chronological — no
    look-ahead leakage. Refits the model each fold (slower but the
    correct posture for thesis-grade benchmark scoring).
    """
    n = len(dataset)
    if n_folds < 1:
        raise ValueError("n_folds must be ≥ 1")
    if horizon * n_folds >= n:
        raise ValueError(
            f"need history > horizon·n_folds; got {n} ≤ {horizon}·{n_folds}"
        )

    mapes, smapes, rmses, mases, winklers, covs = [], [], [], [], [], []
    for k in range(n_folds):
        train_end = n - (n_folds - k) * horizon
        train_points = dataset.points[:train_end]
        test_points = dataset.points[train_end : train_end + horizon]
        train_ds = TimeSeriesDataset(
            series_id=dataset.series_id,
            frequency=dataset.frequency,
            points=train_points,
        )

        fresh = type(model).__new__(type(model))
        # Copy hyperparameters but discard learned state — each fold refits.
        fresh.__dict__.update(
            {k: v for k, v in model.__dict__.items() if not k.startswith("_")}
        )
        # Init the underscored fields by re-running __init__ if possible.
        try:
            fresh.__init__()  # type: ignore[misc]
            fresh.__dict__.update(
                {k: v for k, v in model.__dict__.items() if not k.startswith("_")}
            )
        except TypeError:
            # Init takes required args — fall back to type() with bare new.
            pass
        fresh.fit(train_ds)

        result = fresh.predict(train_ds, horizon, pi_alpha=pi_alpha)
        y_true = np.array([p.y for p in test_points], dtype=np.float64)
        y_pred = np.array([p.yhat for p in result.points], dtype=np.float64)
        y_lower = np.array([p.yhat_lower for p in result.points], dtype=np.float64)
        y_upper = np.array([p.yhat_upper for p in result.points], dtype=np.float64)
        y_train = np.array(train_ds.values, dtype=np.float64)

        mapes.append(mean_absolute_percentage_error(y_true, y_pred))
        smapes.append(symmetric_mape(y_true, y_pred))
        rmses.append(root_mean_squared_error(y_true, y_pred))
        mases.append(mean_absolute_scaled_error(y_true, y_pred, y_train, season_length))
        winklers.append(winkler_score(y_true, y_lower, y_upper, pi_alpha))
        covs.append(coverage(y_true, y_lower, y_upper))

    return ArmResult(
        name=model.name,
        n_folds=n_folds,
        mape=float(np.mean(mapes)),
        smape=float(np.mean(smapes)),
        rmse=float(np.mean(rmses)),
        mase=float(np.mean(mases)),
        winkler=float(np.mean(winklers)),
        coverage=float(np.mean(covs)),
    )
