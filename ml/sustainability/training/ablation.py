"""
AS-004 ablation runner.

Scores every named arm on identical holdout folds + identical seeds,
returns an `ArmResult` per arm. Matches AS-001 (recruitment), AS-002
(pricing), AS-003 (forecasting) — single source of truth for *the*
sustainability ablation experiment that fills `ml-experiments.md`
EXP-ESG-001..003.

Arm catalog (kept stable for thesis reproducibility):
    MajorityLabel              — globally most-common label (random floor)
    IndustryBaseline           — per-industry mean per-pillar label rate
    LinearLogisticMultiLabel   — binary-relevance logistic regression
                                  (the recommended Phase-3 production arm)
"""

from __future__ import annotations

from dataclasses import asdict

import numpy as np

from ml.sustainability.data.loader import generate_synthetic_dataset
from ml.sustainability.evaluation.benchmark import ArmResult, benchmark_arm
from ml.sustainability.models.base import ESGScorer
from ml.sustainability.models.baselines import IndustryBaselineScorer, MajorityLabelScorer
from ml.sustainability.models.multilabel import LinearLogisticMultiLabel
from ml.sustainability.reproducibility import seed_everything
from ml.sustainability.training.config import TrainConfig


def _build_arm(name: str) -> ESGScorer:
    if name == "MajorityLabel":
        return MajorityLabelScorer()
    if name == "IndustryBaseline":
        return IndustryBaselineScorer()
    if name == "LinearLogisticMultiLabel":
        return LinearLogisticMultiLabel()
    raise ValueError(f"unknown sustainability arm: {name!r}")


def run(
    config: TrainConfig | None = None,
    seeds: tuple[int, ...] = (42, 1337, 31337),
) -> dict[str, list[ArmResult]]:
    """Run every arm × every seed. Returns name → list of `ArmResult`."""
    cfg = config or TrainConfig()
    results: dict[str, list[ArmResult]] = {arm: [] for arm in cfg.arms}

    for seed in seeds:
        seed_everything(seed)
        dataset = generate_synthetic_dataset(n_companies=cfg.n_companies, seed=seed)
        for arm in cfg.arms:
            model = _build_arm(arm)
            result = benchmark_arm(
                dataset=dataset,
                model=model,
                n_folds=cfg.n_folds,
                test_fraction=cfg.test_fraction,
                base_seed=seed,
                threshold=cfg.threshold,
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
                        "macro_f1_mean": float(np.mean([r.macro_f1 for r in runs])),
                        "accuracy_mean": float(np.mean([r.accuracy for r in runs])),
                        "hamming_mean": float(np.mean([r.hamming_loss for r in runs])),
                        "brier_mean": float(np.mean([r.brier_score for r in runs])),
                        "ece_mean": float(
                            np.mean([r.expected_calibration_error for r in runs])
                        ),
                    }
                )
    except ImportError:
        pass

    return results
