"""
Encoder interface — every text encoder in the package implements it.

We deliberately keep the interface narrow (`encode`, `dim`, `name`):
ranking models depend on the interface, not on concrete encoder classes,
so swapping SBERT for `all-MiniLM-L6-v2`, OpenAI embeddings, or a domain
fine-tune is a one-line change.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence

import numpy as np


class Encoder(ABC):
    """Abstract text encoder."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Short identifier used for MLflow tags and cache keys."""

    @property
    @abstractmethod
    def dim(self) -> int:
        """Embedding dimensionality."""

    @abstractmethod
    def encode(self, texts: Sequence[str]) -> np.ndarray:
        """Return an ``(n_texts, dim)`` float32 array."""
