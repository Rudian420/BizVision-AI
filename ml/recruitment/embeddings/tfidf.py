"""
TF-IDF baseline encoder (EXP-REC-001).

A research-grade pipeline needs a strong classical baseline to make the
SBERT / ensemble gains attributable to semantic modelling rather than to
text-cleaning improvements. `TFIDFEncoder` fits a `TfidfVectorizer` on a
provided corpus and encodes new text into the same vocabulary.

Stateful — must be `fit` (or `fit_from`) before `encode`. Use it as the
baseline arm in `evaluation/benchmark.py`.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any

import numpy as np

from ml.recruitment.embeddings.base import Encoder


class TFIDFEncoder(Encoder):
    def __init__(
        self,
        *,
        max_features: int = 10_000,
        ngram_range: tuple[int, int] = (1, 2),
        min_df: int = 2,
    ) -> None:
        self._kwargs = {
            "max_features": max_features,
            "ngram_range": ngram_range,
            "min_df": min_df,
            "sublinear_tf": True,
            "strip_accents": "unicode",
            "lowercase": True,
        }
        self._vec: Any | None = None
        self._dim: int = 0

    @property
    def name(self) -> str:
        return "tfidf"

    @property
    def dim(self) -> int:
        if self._dim == 0:
            raise RuntimeError("TFIDFEncoder must be fit before reading `dim`.")
        return self._dim

    def fit(self, corpus: Iterable[str]) -> TFIDFEncoder:
        from sklearn.feature_extraction.text import TfidfVectorizer

        self._vec = TfidfVectorizer(**self._kwargs)
        self._vec.fit(list(corpus))
        self._dim = len(self._vec.vocabulary_)
        return self

    def encode(self, texts: Sequence[str]) -> np.ndarray:
        if self._vec is None:
            raise RuntimeError("TFIDFEncoder.encode called before fit().")
        if len(texts) == 0:
            return np.empty((0, self._dim), dtype=np.float32)
        # Returns a sparse matrix; densifying is acceptable at SME scale
        # (≤10 k CVs × 10 k features = ~800 MB; in practice we score one JD
        # against ≤50 candidates at a time, so densification is trivial).
        return np.asarray(self._vec.transform(list(texts)).toarray(), dtype=np.float32)
