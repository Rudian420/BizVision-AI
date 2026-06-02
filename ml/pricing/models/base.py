"""
Uniform interfaces for the pricing module.

We deliberately use *two* abstract classes here rather than one (cf.
recruitment's single `RankingModel`): pricing has two distinct
roles — predicting *how* demand responds to price (`DemandModel`) and
recommending *what* price to charge (`PricingPolicy`). Policies often
compose a demand model internally; keeping the contracts separate makes
that composition explicit and the benchmark harness simpler.

Both are generic over a `Sequence[PriceObservation]` training input so
the ablation runner can pass the same fitted training pool to every arm.
Both expose `requires_training` so unsupervised arms (constant baseline,
competitor match) don't pay for a no-op `fit` call site discipline.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from ml.pricing.data.schema import (
        PriceObservation,
        PriceRecommendation,
        Product,
    )


class DemandModel(ABC):
    """Predicts demand at a given price (and optional context)."""

    requires_training: bool = True

    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def fit(self, observations: Sequence[PriceObservation]) -> DemandModel:
        """Train on a list of historical observations."""

    @abstractmethod
    def predict_demand(
        self,
        prices: np.ndarray,
        context: Sequence[PriceObservation] | None = None,
    ) -> np.ndarray:
        """Return predicted demand at each price.

        `context` (optional) supplies non-price features (season, competitor,
        promotion) one per row matching `prices`. When omitted the model
        uses its training-time defaults.
        """


class PricingPolicy(ABC):
    """Recommends a price for a single product, given the demand context."""

    requires_training: bool = True

    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def fit(self, observations: Sequence[PriceObservation]) -> PricingPolicy:
        """Train on historical observations (or no-op for unsupervised policies)."""

    @abstractmethod
    def recommend_price(
        self,
        product: Product,
        context: Sequence[PriceObservation] | None = None,
    ) -> PriceRecommendation:
        """Return the recommended price + a structured rationale."""
