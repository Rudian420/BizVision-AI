"""Evaluation harness: metrics + benchmark runner."""

from ml.pricing.evaluation.benchmark import BenchmarkResult, run_benchmark
from ml.pricing.evaluation.metrics import (
    mean_absolute_percentage_error,
    revenue_uplift,
    root_mean_squared_error,
    sharpe_ratio,
    value_at_risk,
    win_rate,
)

__all__ = [
    "BenchmarkResult",
    "mean_absolute_percentage_error",
    "revenue_uplift",
    "root_mean_squared_error",
    "run_benchmark",
    "sharpe_ratio",
    "value_at_risk",
    "win_rate",
]
