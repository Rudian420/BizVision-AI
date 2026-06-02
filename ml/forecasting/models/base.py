"""
Uniform `ForecastModel` interface.

One ABC — matching recruitment's single `RankingModel` shape rather
than pricing's dual `DemandModel` / `PricingPolicy` split. Forecasting
has *one* role: given a history, produce an N-step-ahead forecast with
a prediction interval. The ablation harness in `evaluation.benchmark`
treats every arm the same; the AS-003 campaign (TASK-015, Phase 3) will
score them on identical splits.

`requires_training` lets unsupervised baselines (NaiveLast,
NaiveSeasonal) skip the fit call without polluting the harness with
type checks.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ml.forecasting.data.schema import ForecastResult, TimeSeriesDataset


class ForecastModel(ABC):
    """Predicts the next `horizon` points of a time series."""

    requires_training: bool = True

    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def fit(self, dataset: TimeSeriesDataset) -> ForecastModel:
        """Train on a history. May be a no-op for unsupervised arms."""

    @abstractmethod
    def predict(
        self,
        dataset: TimeSeriesDataset,
        horizon: int,
        pi_alpha: float = 0.05,
    ) -> ForecastResult:
        """Forecast the next `horizon` points.

        `pi_alpha` is the *two-sided* significance level — `0.05` gives
        a 95% prediction interval. Implementations that don't produce
        a model-derived PI fall back to a residual-quantile band on
        the training set so every arm produces a valid `ForecastResult`
        for downstream PI scoring (Winkler).
        """
