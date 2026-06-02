"""
Vector store — abstract `VectorStore` interface + numpy backend.

`NumpyVectorStore` is a pure-numpy linear-scan cosine search. Fast
enough for ≤ 10k documents (which is what the AS-005 fixture lives
in). Wave-2 swaps in a pgvector or FAISS backend behind the same
`VectorStore` ABC — the retriever and benchmark harness don't change.

Cosine similarity collapses to a dot product because the
`EmbeddingClient` contract guarantees unit-norm vectors (see
`embeddings.base.EmbeddingClient.embed`).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence

import numpy as np

from ml.chatbot.data.schema import Document, RetrievedChunk


class VectorStore(ABC):
    """Stores document embeddings + retrieves the top-k for a query vector."""

    @abstractmethod
    def add(self, documents: Sequence[Document], embeddings: np.ndarray) -> None:
        """Index `documents` with their pre-computed embeddings.

        `embeddings` must be shape `(len(documents), dim)`.
        """

    @abstractmethod
    def search(
        self,
        query_vec: np.ndarray,
        top_k: int = 5,
        module_filter: str | None = None,
    ) -> tuple[RetrievedChunk, ...]:
        """Return the top-k most-similar chunks, ranked from most to least.

        `module_filter` (optional) restricts to a single BizVision module."""

    @abstractmethod
    def __len__(self) -> int: ...


class NumpyVectorStore(VectorStore):
    """Linear-scan cosine search backed by a stacked numpy matrix.

    Memory: O(n · dim · 8 bytes). For dim=256 and n=10k that's ~20 MB
    — fits easily on every dev machine.
    """

    def __init__(self) -> None:
        self._documents: tuple[Document, ...] = ()
        self._matrix: np.ndarray = np.zeros((0, 0), dtype=np.float64)

    def __len__(self) -> int:
        return len(self._documents)

    def add(self, documents: Sequence[Document], embeddings: np.ndarray) -> None:
        if len(documents) != embeddings.shape[0]:
            raise ValueError(
                f"document/embedding count mismatch: "
                f"{len(documents)} vs {embeddings.shape[0]}"
            )
        if not documents:
            return
        if self._matrix.size == 0:
            self._documents = tuple(documents)
            self._matrix = np.asarray(embeddings, dtype=np.float64).copy()
            return
        if embeddings.shape[1] != self._matrix.shape[1]:
            raise ValueError(
                f"embedding dim mismatch: existing {self._matrix.shape[1]} "
                f"vs new {embeddings.shape[1]}"
            )
        self._documents = self._documents + tuple(documents)
        self._matrix = np.vstack([self._matrix, np.asarray(embeddings, dtype=np.float64)])

    def search(
        self,
        query_vec: np.ndarray,
        top_k: int = 5,
        module_filter: str | None = None,
    ) -> tuple[RetrievedChunk, ...]:
        if self._matrix.size == 0:
            return ()
        if top_k <= 0:
            raise ValueError("top_k must be > 0")
        q = np.asarray(query_vec, dtype=np.float64).ravel()
        if q.shape[0] != self._matrix.shape[1]:
            raise ValueError(
                f"query dim {q.shape[0]} != store dim {self._matrix.shape[1]}"
            )
        # Cosine similarity = dot product (both are unit-norm by contract).
        sims = self._matrix @ q
        if module_filter is not None:
            mask = np.array(
                [d.module == module_filter for d in self._documents], dtype=bool
            )
            if not mask.any():
                return ()
            # Push non-matching scores to -inf so argsort filters them out.
            sims = np.where(mask, sims, -np.inf)
        # argsort returns ascending; reverse and take top_k.
        order = np.argsort(-sims)[: top_k]
        results: list[RetrievedChunk] = []
        for rank, idx in enumerate(order):
            score = float(sims[idx])
            if score == -np.inf:
                break
            results.append(
                RetrievedChunk(
                    document=self._documents[int(idx)],
                    score=score,
                    rank=rank,
                )
            )
        return tuple(results)
