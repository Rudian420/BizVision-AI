"""
AS-003 ablation runner.

Scores every named arm on identical rolling-origin folds + identical
seeds, returns an `ArmResult` per arm. Matches AS-001 (recruitment) /
AS-002 (pricing) — single source of truth for *the* forecasting
ablation experiment that fills `ml-experiments.md` EXP-FOR-001..003.

Arm catalog (kept stable for thesis reproducibility):
    NaiveLast            — flat at last value (random-walk baseline)
    NaiveSeasonal        — seasonal naive (period = config.season_length)
    HoltWinters          — additive trend + additive seasonality
    Theta                — classical θ=2 (M3/M4 strong baseline)
"""

from __future__ import annotations

from dataclasses import asdict

import numpy as np

from ml.forecasting.data.loader import generate_synthetic_series
from ml.forecasting.evaluation.benchmark import ArmResult, rolling_origin_backtest
from ml.forecasting.models.base import ForecastModel
from ml.forecasting.models.baselines import NaiveLast, NaiveSeasonal
from ml.forecasting.models.exp_smoothing import HoltWintersForecaster
from ml.forecasting.models.theta import ThetaForecaster
from ml.forecasting.reproducibility import seed_everything
from ml.forecasting.training.config import TrainConfig


def _build_arm(name: str, season_length: int) -> ForecastModel:
    if name == "NaiveLast":
        return NaiveLast()
    if name == "NaiveSeasonal":
        return NaiveSeasonal(season_length=season_length)
    if name == "HoltWinters":
        return HoltWintersForecaster(season_length=season_length)
    if name == "Theta":
        return ThetaForecaster()
    raise ValueError(f"unknown forecasting arm: {name!r}")


def run(
    config: TrainConfig | None = None,
    seeds: tuple[int, ...] = (42, 1337, 31337),
) -> dict[str, list[ArmResult]]:
    """Run every arm × every seed. Returns name → list of `ArmResult`."""
    cfg = config or TrainConfig()
    results: dict[str, list[ArmResult]] = {arm: [] for arm in cfg.arms}

    for seed in seeds:
        seed_everything(seed)
        dataset = generate_synthetic_series(n_days=cfg.n_days, seed=seed)
        for arm in cfg.arms:
            model = _build_arm(arm, cfg.season_length)
            result = rolling_origin_backtest(
                dataset=dataset,
                model=model,
                horizon=cfg.horizon,
                n_folds=cfg.n_folds,
                season_length=cfg.season_length,
                pi_alpha=cfg.pi_alpha,
            )
            results[arm].append(result)

    try:  # pragma: no cover - optional dep
        import mlflow

        mlflow.set_experiment(cfg.mlflow_experiment)
        for arm, runs in results.items():
            with mlflow.start_run(run_name=f"ablation-{arm}"):
                mlflow.log_params({**asdict(cfg), "arm": arm, "n_seeds": len(seeds)})
                mlflow.log_metrics(
                    {
                        "mape_mean": float(np.mean([r.mape for r in runs])),
                        "smape_mean": float(np.mean([r.smape for r in runs])),
                        "rmse_mean": float(np.mean([r.rmse for r in runs])),
                        "mase_mean": float(np.mean([r.mase for r in runs])),
                        "winkler_mean": float(np.mean([r.winkler for r in runs])),
                        "coverage_mean": float(np.mean([r.coverage for r in runs])),
                    }
                )
    except ImportError:
        pass

    return results
