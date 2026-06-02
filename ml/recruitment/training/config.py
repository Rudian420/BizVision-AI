"""Training configuration — typed, default-rich, YAML-loadable."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class TrainingConfig:
    """Single source of truth for a training run.

    Captured verbatim into MLflow tags + the run artifact so any historical
    run can be reproduced from the config alone (plus the env capture).
    """

    # ── data ──────────────────────────────────────────────────────
    n_synthetic_candidates: int = 2000
    train_pct: float = 0.7
    val_pct: float = 0.15
    seed: int = 42

    # ── models ────────────────────────────────────────────────────
    sbert_model: str = "sentence-transformers/all-mpnet-base-v2"
    sbert_normalise: bool = True

    xgb_params: dict = field(
        default_factory=lambda: {
            "n_estimators": 400,
            "max_depth": 6,
            "learning_rate": 0.05,
            "subsample": 0.85,
            "colsample_bytree": 0.85,
        }
    )

    ensemble_grid: tuple[float, ...] = (0.3, 0.4, 0.5, 0.6, 0.7)

    # ── evaluation ────────────────────────────────────────────────
    ks: tuple[int, ...] = (1, 3, 5, 10)
    fairness_topk: int = 5
    protected_attributes: tuple[str, ...] = ("gender",)

    # ── MLflow ────────────────────────────────────────────────────
    experiment_name: str = "recruitment"
    run_name: str | None = None

    def as_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_yaml(cls, path: str | Path) -> TrainingConfig:
        import yaml

        with Path(path).open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        return cls(**data)
