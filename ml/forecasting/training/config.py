"""Forecasting training config — frozen dataclass, JSON-round-trippable."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TrainConfig:
    """Knobs for `pipeline.train` and `ablation.run`.

    Identical posture to `ml.pricing.training.config.TrainConfig`:
    a frozen dataclass that the CLI deserialises from CLI flags or a
    YAML file. The defaults are tuned for the synthetic 2-year daily
    fixture from `data.loader.generate_synthetic_series`.
    """

    n_days: int = 365 * 2
    horizon: int = 90
    n_folds: int = 5
    season_length: int = 7
    pi_alpha: float = 0.05
    seed: int = 42
    arms: tuple[str, ...] = (
        "NaiveLast",
        "NaiveSeasonal",
        "HoltWinters",
        "Theta",
    )
    mlflow_experiment: str = "bizvision.forecasting"
