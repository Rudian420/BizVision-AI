"""
Classical baselines: Random, TF-IDF cosine, Okapi BM25.

Together with `SBERTRanker` (no training) and `XGBoostRanker` (structured
features only) they form the four arms of AS-001 (recruitment ablation).
A real research paper *must* report these — without them, claimed gains
from the ensemble are unattributable.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Sequence
from typing import TYPE_CHECKING

import numpy as np

from ml.recruitment.embeddings.tfidf import TFIDFEncoder
from ml.recruitment.models.base import RankingModel

if TYPE_CHECKING:
    from ml.recruitment.data.schema import CandidateRecord, JobDescription, Pair


# ── 1. Random baseline ───────────────────────────────────────────────


class RandomRanker(RankingModel):
    """Uniform random scores. The floor every other model must beat."""

    requires_training = False

    def __init__(self, seed: int = 42) -> None:
        self._rng = np.random.default_rng(seed)

    @property
    def name(self) -> str:
        return "baseline-random"

    def fit(self, pairs: Sequence[Pair]) -> RankingModel:
        return self

    def score(self, jd: JobDescription, candidates: Sequence[CandidateRecord]) -> np.ndarray:
        return self._rng.random(len(candidates), dtype=np.float32)


# ── 2. TF-IDF cosine baseline (EXP-REC-001) ─────────────────────────


class TFIDFRanker(RankingModel):
    """Fit a TF-IDF vectoriser on the training corpus then score by cosine
    similarity between the JD vector and each CV vector."""

    requires_training = True

    def __init__(self, **encoder_kwargs: object) -> None:
        self._encoder = TFIDFEncoder(**encoder_kwargs)  # type: ignore[arg-type]
        self._fitted = False

    @property
    def name(self) -> str:
        return "baseline-tfidf"

    def fit(self, pairs: Sequence[Pair]) -> RankingModel:
        corpus: list[str] = []
        seen_cv: set[str] = set()
        seen_jd: set[str] = set()
        for p in pairs:
            if p.candidate.cv_text and p.candidate.candidate_id not in seen_cv:
                corpus.append(p.candidate.cv_text)
                seen_cv.add(p.candidate.candidate_id)
            if p.job.job_id not in seen_jd:
                jd_text = f"{p.job.title}\n{p.job.description}"
                corpus.append(jd_text)
                seen_jd.add(p.job.job_id)
        self._encoder.fit(corpus)
        self._fitted = True
        return self

    def score(self, jd: JobDescription, candidates: Sequence[CandidateRecord]) -> np.ndarray:
        if not self._fitted:
            raise RuntimeError("TFIDFRanker.score called before fit().")
        if len(candidates) == 0:
            return np.empty(0, dtype=np.float32)
        jd_vec = self._encoder.encode([f"{jd.title}\n{jd.description}"])[0]
        cv_vecs = self._encoder.encode([c.cv_text or "" for c in candidates])
        return _cosine(jd_vec, cv_vecs)


# ── 3. BM25 baseline ─────────────────────────────────────────────────


class BM25Ranker(RankingModel):
    """Okapi BM25 (Robertson et al.) — the gold-standard lexical retrieval
    baseline. Implemented directly to avoid an extra dependency."""

    requires_training = True

    def __init__(self, *, k1: float = 1.5, b: float = 0.75) -> None:
        self._k1 = k1
        self._b = b
        self._fitted = False
        self._doc_freq: Counter[str] = Counter()
        self._avgdl: float = 0.0
        self._n_docs: int = 0

    @property
    def name(self) -> str:
        return "baseline-bm25"

    def fit(self, pairs: Sequence[Pair]) -> RankingModel:
        # Build document statistics over the candidate CV corpus.
        cv_seen: set[str] = set()
        n_docs = 0
        total_len = 0
        for p in pairs:
            cid = p.candidate.candidate_id
            if cid in cv_seen:
                continue
            cv_seen.add(cid)
            toks = _tokenise(p.candidate.cv_text)
            total_len += len(toks)
            n_docs += 1
            for term in set(toks):  # set → document frequency, not term freq
                self._doc_freq[term] += 1
        self._n_docs = max(n_docs, 1)
        self._avgdl = total_len / self._n_docs if self._n_docs else 1.0
        self._fitted = True
        return self

    def score(self, jd: JobDescription, candidates: Sequence[CandidateRecord]) -> np.ndarray:
        if not self._fitted:
            raise RuntimeError("BM25Ranker.score called before fit().")
        query = _tokenise(f"{jd.title} {jd.description}")
        scores = np.zeros(len(candidates), dtype=np.float32)
        for i, c in enumerate(candidates):
            doc_toks = _tokenise(c.cv_text)
            scores[i] = self._bm25(query, doc_toks)
        return scores

    def _bm25(self, query: list[str], doc: list[str]) -> float:
        if not doc:
            return 0.0
        tf = Counter(doc)
        dl = len(doc)
        s = 0.0
        for term in query:
            df = self._doc_freq.get(term, 0)
            if df == 0:
                continue
            idf = math.log(1 + (self._n_docs - df + 0.5) / (df + 0.5))
            f = tf.get(term, 0)
            denom = f + self._k1 * (1 - self._b + self._b * dl / max(self._avgdl, 1e-6))
            s += idf * (f * (self._k1 + 1)) / max(denom, 1e-6)
        return s


# ── helpers ───────────────────────────────────────────────────────────


def _tokenise(text: str) -> list[str]:
    """Lowercase, alphanumeric whitespace tokeniser — sufficient for BM25."""
    if not text:
        return []
    return [t for t in (s.strip().lower() for s in _SPLIT_RE.split(text)) if t]


def _cosine(query: np.ndarray, docs: np.ndarray) -> np.ndarray:
    """Cosine similarity between one query vector and a batch of doc vectors."""
    q = query.astype(np.float32, copy=False)
    d = docs.astype(np.float32, copy=False)
    qn = np.linalg.norm(q) + 1e-12
    dn = np.linalg.norm(d, axis=1) + 1e-12
    return (d @ q) / (dn * qn)


_SPLIT_RE = re.compile(r"[^A-Za-z0-9+]+")
