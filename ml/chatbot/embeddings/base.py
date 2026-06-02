"""
Uniform `EmbeddingClient` interface.

One ABC — same posture as ESG's `ESGScorer`, forecasting's
`ForecastModel`, recruitment's `RankingModel`. Wave-1 ships one
concrete implementation (`HashEmbedder`, deterministic bag-of-words
feature hashing). Wave-2 swaps in a real SBERT (`all-mpnet-base-v2`)
behind the same ABC without touching the retriever / agents — the
"lazy heavy dep" pattern from ADR-024.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence

import numpy as np


class EmbeddingClient(ABC):
    """Embeds text into a fixed-dimensional vector space."""

    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Embedding dimensionality. Locked at construction time."""

    @abstractmethod
    def embed(self, text: str) -> np.ndarray:
        """Return a unit-norm embedding for one document / query.

        Returns a 1-D array of shape `(dimension,)`. The unit-norm
        invariant lets cosine similarity in `retrieval.vector_store`
        collapse to a plain dot product."""

    def embed_batch(self, texts: Sequence[str]) -> np.ndarray:
        """Stack `embed` over a sequence → (n, dimension)."""
        if not texts:
            return np.zeros((0, self.dimension), dtype=np.float64)
        rows = [self.embed(t) for t in texts]
        return np.stack(rows, axis=0)
