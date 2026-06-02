"""
Bag-of-words feature-hashing embedder — wave 1.

Pure-numpy, no sentence-transformers / torch dependency. Each text is
tokenized (lowercase + simple punctuation strip), 1- and 2-grams are
hashed into a fixed `dimension` buckets, weighted by token frequency,
and L2-normalized to unit length.

This is the standard "hashing trick" (Weinberger et al. 2009) — known
to recover useful similarity on short documents without any learned
parameters. The wave-2 SBERT swap fits behind the same
`EmbeddingClient` ABC; harness and tests don't change.

The hashed-trick choice is also why we don't need an "is the model
loaded yet" guard — the embedder is deterministic and stateless past
its constructor.
"""

from __future__ import annotations

import re

import numpy as np

from ml.chatbot.embeddings.base import EmbeddingClient

# Conservative dimensionality: small enough to keep the vector store
# fast on the 100-doc fixture; large enough that hash collisions don't
# wreck retrieval quality. SBERT (wave 2) lifts this to 768.
_DEFAULT_DIM = 256

_TOKEN_RE = re.compile(r"[A-Za-z0-9]+")

# Common English stopwords (small list — bigger lists hurt rare-term
# matching on the technical corpus). Stays deterministic, no nltk
# dependency.
_STOPWORDS = frozenset(
    {
        "the",
        "a",
        "an",
        "and",
        "or",
        "but",
        "of",
        "to",
        "for",
        "in",
        "on",
        "at",
        "by",
        "from",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "with",
        "as",
        "it",
        "its",
        "this",
        "that",
        "these",
        "those",
        "i",
        "you",
        "he",
        "she",
        "we",
        "they",
        "do",
        "does",
        "did",
        "have",
        "has",
        "had",
        "what",
        "which",
        "who",
        "how",
        "when",
        "where",
        "why",
        "can",
        "could",
        "should",
        "would",
        "may",
        "might",
    }
)


def _tokenize(text: str) -> list[str]:
    """Lowercase + alphanumeric tokenization, stopword removal."""
    return [t for t in _TOKEN_RE.findall(text.lower()) if t not in _STOPWORDS]


def _hash_token(token: str, dim: int) -> int:
    """Stable Python `hash` is per-process random unless PYTHONHASHSEED
    is set; here we use a hand-rolled FNV-1a variant for full
    cross-process determinism (matters for thesis reproducibility)."""
    h = 2166136261
    for ch in token:
        h ^= ord(ch)
        h = (h * 16777619) & 0xFFFFFFFF
    return h % dim


class HashEmbedder(EmbeddingClient):
    """Deterministic bag-of-words feature-hashing embedder.

    1-gram + 2-gram tokens, hashed into `dimension` buckets with
    sign-flip (Weinberger et al. 2009 §4 to reduce hash collision
    bias). L2-normalized. No learned parameters; stateless after init.
    """

    def __init__(self, dimension: int = _DEFAULT_DIM) -> None:
        if dimension <= 0:
            raise ValueError("dimension must be > 0")
        self._dim = dimension

    @property
    def name(self) -> str:
        return f"HashEmbedder(dim={self._dim})"

    @property
    def dimension(self) -> int:
        return self._dim

    def embed(self, text: str) -> np.ndarray:
        vec = np.zeros(self._dim, dtype=np.float64)
        if not text:
            return vec
        tokens = _tokenize(text)
        if not tokens:
            return vec

        # 1-grams
        for tok in tokens:
            idx = _hash_token(tok, self._dim)
            sign = 1.0 if (idx % 2 == 0) else -1.0  # Weinberger sign trick
            vec[idx] += sign

        # 2-grams (concatenation captures local order signal)
        for i in range(len(tokens) - 1):
            bigram = tokens[i] + "_" + tokens[i + 1]
            idx = _hash_token(bigram, self._dim)
            sign = 1.0 if (idx % 2 == 0) else -1.0
            vec[idx] += sign

        norm = float(np.linalg.norm(vec))
        if norm == 0.0:
            return vec
        return vec / norm
