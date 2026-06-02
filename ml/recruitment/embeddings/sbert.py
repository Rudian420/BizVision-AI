"""
Sentence-BERT encoder (`all-mpnet-base-v2` by default — 768-dim).

The heavy dep (`sentence-transformers` + `torch`) is imported lazily inside
`_load_model()` so this module imports cleanly in environments without it
(CI lint, dev venv). Cache is enabled by default — embedding 5 000 CVs
twice in an ablation run is a 60-second-vs-60-minute difference.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np

from ml.recruitment.embeddings.base import Encoder
from ml.recruitment.embeddings.cache import EmbeddingCache

DEFAULT_MODEL = "sentence-transformers/all-mpnet-base-v2"
_DIM_BY_MODEL: dict[str, int] = {
    "sentence-transformers/all-mpnet-base-v2": 768,
    "sentence-transformers/all-MiniLM-L6-v2": 384,
}


class SBERTEncoder(Encoder):
    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
        *,
        batch_size: int = 64,
        normalize: bool = True,
        cache: EmbeddingCache | None = None,
    ) -> None:
        self._model_name = model_name
        self._batch_size = batch_size
        self._normalize = normalize
        self._model: Any | None = None
        self._cache = cache if cache is not None else EmbeddingCache(self.name)

    # ── Encoder interface ──────────────────────────────────────────
    @property
    def name(self) -> str:
        return f"sbert::{self._model_name}"

    @property
    def dim(self) -> int:
        return _DIM_BY_MODEL.get(self._model_name, 768)

    def encode(self, texts: Sequence[str]) -> np.ndarray:
        if len(texts) == 0:
            return np.empty((0, self.dim), dtype=np.float32)

        # First pass: cache lookup so we only forward-pass the misses.
        out = np.empty((len(texts), self.dim), dtype=np.float32)
        miss_idx: list[int] = []
        miss_texts: list[str] = []
        for i, text in enumerate(texts):
            cached = self._cache.get(text)
            if cached is not None:
                out[i] = cached
            else:
                miss_idx.append(i)
                miss_texts.append(text)

        if miss_texts:
            new_vecs = self._embed(miss_texts)
            for i, vec in zip(miss_idx, new_vecs, strict=False):
                out[i] = vec
                self._cache.put(texts[i], vec)
        return out

    # ── internals ───────────────────────────────────────────────────
    def _load_model(self) -> Any:
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:  # pragma: no cover
                raise RuntimeError(
                    "SBERTEncoder requires `sentence-transformers`. "
                    "Install via the `ml` extras (`pip install -r ml/requirements.txt`)."
                ) from exc
            self._model = SentenceTransformer(self._model_name)
        return self._model

    def _embed(self, texts: list[str]) -> np.ndarray:
        model = self._load_model()
        vecs = model.encode(
            texts,
            batch_size=self._batch_size,
            normalize_embeddings=self._normalize,
            show_progress_bar=False,
            convert_to_numpy=True,
        )
        return np.asarray(vecs, dtype=np.float32)
