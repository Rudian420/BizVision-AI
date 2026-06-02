"""
Forecasting training pipeline.

Mirrors `ml.pricing.training.pipeline.train`. Steps:

  1. seed → load synthetic → split train/test
  2. fit Theta (the recommended production arm) on the train window
  3. score it on the test window with the same metric basket the
     benchmark harness uses
  4. log everything to MLflow

This is the *single-arm* training entry — the full AS-003 ablation
campaign lives in `training.ablation.run` and scores every arm on the
same rolling-origin folds. Both share the same metric definitions.

`python -m ml.forecasting.training.pipeline` runs it once with defaults.
"""

from __future__ import annotations

from dataclasses import asdict

import numpy as np

from ml.forecasting.data.loader import generate_synthetic_series, split_train_test
from ml.forecasting.evaluation.metrics import (
    coverage,
    mean_absolute_percentage_error,
    mean_absolute_scaled_error,
    root_mean_squared_error,
    symmetric_mape,
    winkler_score,
)
from ml.forecasting.models.theta import ThetaForecaster
from ml.forecasting.reproducibility import capture_env_snapshot, seed_everything
from ml.forecasting.training.config import TrainConfig


def train(config: TrainConfig | None = None) -> dict:
    """Train the recommended single-arm forecaster and return its metrics."""
    cfg = config or TrainConfig()
    seed_everything(cfg.seed)

    dataset = generate_synthetic_series(n_days=cfg.n_days, seed=cfg.seed)
    train_ds, test_ds = split_train_test(dataset, horizon=cfg.horizon)

    model = ThetaForecaster().fit(train_ds)
    result = model.predict(train_ds, horizon=cfg.horizon, pi_alpha=cfg.pi_alpha)

    y_true = np.array(test_ds.values, dtype=np.float64)
    y_pred = np.array([p.yhat for p in result.points], dtype=np.float64)
    y_lower = np.array([p.yhat_lower for p in result.points], dtype=np.float64)
    y_upper = np.array([p.yhat_upper for p in result.points], dtype=np.float64)
    y_train = np.array(train_ds.values, dtype=np.float64)

    metrics: dict[str, float] = {
        "mape": mean_absolute_percentage_error(y_true, y_pred),
        "smape": symmetric_mape(y_true, y_pred),
        "rmse": root_mean_squared_error(y_true, y_pred),
        "mase": mean_absolute_scaled_error(y_true, y_pred, y_train, cfg.season_length),
        "winkler": winkler_score(y_true, y_lower, y_upper, cfg.pi_alpha),
        "coverage": coverage(y_true, y_lower, y_upper),
    }

    # MLflow logging — optional; skipped if mlflow isn't installed.
    try:  # pragma: no cover - optional dep
        import mlflow

        mlflow.set_experiment(cfg.mlflow_experiment)
        with mlflow.start_run(run_name=f"{model.name}-baseline"):
            mlflow.log_params(asdict(cfg))
            mlflow.log_params(capture_env_snapshot())
            mlflow.log_metrics(metrics)
    except ImportError:
        pass

    return {
        "model": model.name,
        "metrics": metrics,
        "config": asdict(cfg),
    }


if __name__ == "__main__":  # pragma: no cover
    out = train()
    print(out)
