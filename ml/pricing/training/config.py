"""Pricing training configuration — typed, default-rich, YAML-loadable."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class PricingTrainingConfig:
    """Single source of truth for a pricing training run.

    Captured verbatim into MLflow tags so any historical run can be
    reproduced from the config alone (plus the env capture)."""

    # ── data ─────────────────────────────────────────────────────
    n_synthetic_observations: int = 3_000
    train_pct: float = 0.7
    val_pct: float = 0.15
    seed: int = 42

    # ── models ───────────────────────────────────────────────────
    lightgbm_params: dict = field(
        default_factory=lambda: {
            "n_estimators": 400,
            "num_leaves": 31,
            "learning_rate": 0.05,
            "subsample": 0.85,
            "colsample_bytree": 0.85,
        }
    )
    ppo_total_timesteps: int = 50_000

    # ── MLflow ───────────────────────────────────────────────────
    experiment_name: str = "pricing"
    run_name: str | None = None

    def as_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_yaml(cls, path: str | Path) -> PricingTrainingConfig:
        import yaml

        with Path(path).open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        return cls(**data)
