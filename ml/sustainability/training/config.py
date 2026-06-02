"""Sustainability training config — frozen dataclass, JSON-round-trippable."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TrainConfig:
    """Knobs for `pipeline.train` and `ablation.run`.

    Identical posture to `ml.forecasting.training.config.TrainConfig`:
    a frozen dataclass that the CLI deserialises from CLI flags or a
    YAML file. Defaults are tuned for the synthetic 600-company fixture
    from `data.loader.generate_synthetic_dataset`.
    """

    n_companies: int = 600
    test_fraction: float = 0.2
    n_folds: int = 3
    seed: int = 42
    threshold: float = 0.5
    arms: tuple[str, ...] = (
        "MajorityLabel",
        "IndustryBaseline",
        "LinearLogisticMultiLabel",
    )
    mlflow_experiment: str = "bizvision.sustainability"
