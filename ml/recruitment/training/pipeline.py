"""
End-to-end recruitment training pipeline.

Orchestrates: data → models (5 arms) → benchmark → fairness audit →
ensemble weight search → MLflow logging. Returns a `TrainingResult`
suitable for both the CLI (`python -m ml.recruitment.cli train`) and the
ablation runner.

Tags every run with the environment capture + the full `TrainingConfig`
so a future reader can reproduce the exact toolchain.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from ml.recruitment.data.loader import RecruitmentDataLoader
from ml.recruitment.evaluation.benchmark import BenchmarkResult, run_benchmark
from ml.recruitment.fairness.auditor import FairnessReport, intersectional_audit
from ml.recruitment.models.baselines import BM25Ranker, RandomRanker, TFIDFRanker
from ml.recruitment.models.ensemble import EnsembleRanker, find_optimal_weight
from ml.recruitment.models.semantic import SBERTRanker
from ml.recruitment.models.structured import XGBoostRanker
from ml.recruitment.reproducibility.env import capture_environment
from ml.recruitment.reproducibility.seed import set_global_seed
from ml.recruitment.training.config import TrainingConfig
from ml.shared.mlflow_utils import start_run


@dataclass
class TrainingResult:
    config: TrainingConfig
    benchmark: BenchmarkResult
    fairness_reports: dict[str, FairnessReport]
    best_weight: float
    weight_search: dict[float, float]
    env: dict[str, str]


def train_pipeline(config: TrainingConfig | None = None) -> TrainingResult:
    cfg = config or TrainingConfig()
    set_global_seed(cfg.seed)
    env = capture_environment()

    # ── data ──────────────────────────────────────────────────────
    loader = RecruitmentDataLoader()
    dataset = loader.load_synthetic(n_candidates=cfg.n_synthetic_candidates, seed=cfg.seed)
    train, val, test = dataset.split(train=cfg.train_pct, val=cfg.val_pct, seed=cfg.seed)

    # ── candidate models (5 arms of AS-001) ──────────────────────
    sbert = SBERTRanker()
    xgb = XGBoostRanker(**cfg.xgb_params)
    models: list[Any] = [
        RandomRanker(seed=cfg.seed),
        TFIDFRanker(),
        BM25Ranker(),
        sbert,
        xgb,
    ]
    # Train the structured + ensemble legs once on the full train pool.
    sbert.fit(train.pairs)
    xgb.fit(train.pairs)

    ensemble = EnsembleRanker(sbert, xgb, weight=0.6).fit(train.pairs)
    best_weight, weight_search = find_optimal_weight(
        ensemble, val.pairs, grid=cfg.ensemble_grid, k=5
    )
    ensemble.set_weight(best_weight)
    models.append(ensemble)

    # ── benchmark ─────────────────────────────────────────────────
    bench = run_benchmark(models, train=train.pairs, test=test.pairs, ks=cfg.ks)

    # ── fairness ──────────────────────────────────────────────────
    test_scores = bench.raw[ensemble.name]["scores"]
    test_labels = bench.raw[ensemble.name]["labels"]
    test_protected = _extract_protected(test.pairs, cfg.protected_attributes)
    fairness_reports = intersectional_audit(
        scores=test_scores,
        y_true=test_labels,
        attributes=test_protected,
        top_k=cfg.fairness_topk,
    )

    # ── MLflow ────────────────────────────────────────────────────
    with start_run("recruitment", run_name=cfg.run_name, tags=env) as _:
        _log_to_mlflow(
            cfg=cfg,
            bench=bench,
            fairness=fairness_reports,
            best_weight=best_weight,
            weight_search=weight_search,
            env=env,
        )

    return TrainingResult(
        config=cfg,
        benchmark=bench,
        fairness_reports=fairness_reports,
        best_weight=best_weight,
        weight_search=weight_search,
        env=env,
    )


# ── helpers ──────────────────────────────────────────────────────────


def _extract_protected(pairs, attributes: tuple[str, ...]) -> dict[str, np.ndarray]:
    out: dict[str, np.ndarray] = {}
    for attr in attributes:
        values = []
        for p in pairs:
            v = getattr(p.candidate.protected, attr, None)
            values.append(v if v is not None else "unknown")
        out[attr] = np.array(values, dtype=object)
    return out


def _log_to_mlflow(
    *,
    cfg: TrainingConfig,
    bench: BenchmarkResult,
    fairness: dict[str, FairnessReport],
    best_weight: float,
    weight_search: dict[float, float],
    env: dict[str, str],
) -> None:
    import mlflow

    mlflow.log_params({"config": str(cfg.as_dict())})
    mlflow.log_params({f"env.{k}": v for k, v in env.items()})
    mlflow.log_param("best_ensemble_weight", best_weight)
    for w, ndcg in weight_search.items():
        mlflow.log_metric(f"weight_search.ndcg@5.w{int(w*100):03d}", float(ndcg))
    for model_name, metrics in bench.metrics.items():
        clean = model_name.replace("::", "__").replace("/", "_").replace("(", "_").replace(")", "_")
        for metric, value in metrics.items():
            mlflow.log_metric(f"{clean}.{metric}", float(value))
    for attr, rep in fairness.items():
        clean = attr.replace("×", "_x_")
        mlflow.log_metric(f"fairness.{clean}.dpd", rep.demographic_parity_difference)
        mlflow.log_metric(f"fairness.{clean}.di", rep.disparate_impact)
        if rep.equalized_odds_difference is not None:
            mlflow.log_metric(f"fairness.{clean}.eod", rep.equalized_odds_difference)
