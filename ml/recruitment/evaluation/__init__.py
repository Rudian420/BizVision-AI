"""Evaluation harness: metrics, deterministic splits, benchmark runner."""

from ml.recruitment.evaluation.benchmark import BenchmarkResult, run_benchmark
from ml.recruitment.evaluation.metrics import (
    average_precision_at_k,
    compute_ranking_metrics,
    mean_reciprocal_rank,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
    roc_auc,
    spearman_correlation,
)
from ml.recruitment.evaluation.splits import group_by_query

__all__ = [
    "BenchmarkResult",
    "average_precision_at_k",
    "compute_ranking_metrics",
    "group_by_query",
    "mean_reciprocal_rank",
    "ndcg_at_k",
    "precision_at_k",
    "recall_at_k",
    "roc_auc",
    "run_benchmark",
    "spearman_correlation",
]
