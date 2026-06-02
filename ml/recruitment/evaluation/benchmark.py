"""
Benchmark harness — run a list of ranking models against the same eval
split and produce a comparison table.

Outputs:
  • `BenchmarkResult.frame`   — pandas DataFrame (rows = models, cols = metrics)
  • `BenchmarkResult.raw`     — per-query metric arrays for confidence-interval analysis
  • `BenchmarkResult.runtime` — fit + inference seconds per model

The harness is intentionally *not* aware of MLflow — the training
pipeline logs each run; the benchmark is reproducible offline and in CI.
"""

from __future__ import annotations

import time
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np

from ml.recruitment.data.schema import Pair
from ml.recruitment.evaluation.metrics import compute_ranking_metrics
from ml.recruitment.evaluation.splits import group_by_query
from ml.recruitment.models.base import RankingModel


@dataclass
class BenchmarkResult:
    """Tidy result of one benchmark run.

    `frame` rows are model names; each cell is the mean metric across queries.
    `raw` is keyed by model_name → metric_name → numpy array of per-query values.
    """

    metrics: dict[str, dict[str, float]]
    raw: dict[str, dict[str, np.ndarray]]
    runtime: dict[str, dict[str, float]]
    ks: tuple[int, ...]

    def to_dataframe(self) -> Any:
        import pandas as pd

        return pd.DataFrame(self.metrics).T


def run_benchmark(
    models: Sequence[RankingModel],
    *,
    train: Sequence[Pair],
    test: Sequence[Pair],
    ks: tuple[int, ...] = (1, 3, 5, 10),
) -> BenchmarkResult:
    """Fit each model on `train`, evaluate against `test`, group by query.

    Returns a `BenchmarkResult` whose `frame` is the canonical comparison
    table for AS-001 / EXP-REC-* runs.
    """
    test_groups = group_by_query(test)

    metrics: dict[str, dict[str, float]] = {}
    raw: dict[str, dict[str, np.ndarray]] = {}
    runtime: dict[str, dict[str, float]] = {}

    for model in models:
        t0 = time.perf_counter()
        if model.requires_training:
            model.fit(train)
        t_fit = time.perf_counter() - t0

        # Inference per query.
        t0 = time.perf_counter()
        grouped_truth: list[np.ndarray] = []
        grouped_scores: list[np.ndarray] = []
        for _jd_id, items in test_groups.items():
            jd = items[0].job
            cands = [it.candidate for it in items]
            labels = np.asarray([it.label for it in items], dtype=np.int32)
            scores = np.asarray(model.score(jd, cands), dtype=np.float32)
            grouped_truth.append(labels)
            grouped_scores.append(scores)
        t_infer = time.perf_counter() - t0

        metrics[model.name] = compute_ranking_metrics(grouped_truth, grouped_scores, ks=ks)
        raw[model.name] = {
            "labels": np.concatenate(grouped_truth) if grouped_truth else np.array([]),
            "scores": np.concatenate(grouped_scores) if grouped_scores else np.array([]),
        }
        runtime[model.name] = {"fit_s": t_fit, "infer_s": t_infer}

    return BenchmarkResult(metrics=metrics, raw=raw, runtime=runtime, ks=tuple(ks))
