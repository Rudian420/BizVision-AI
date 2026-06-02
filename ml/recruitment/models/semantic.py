"""
Semantic ranker — SBERT cosine similarity between JD and each CV embedding.

EXP-REC-002. Unsupervised: `fit` is a no-op (we just pre-warm the cache).
Models that *need* labels (XGBoost) live in `models.structured`.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

import numpy as np

from ml.recruitment.embeddings.sbert import SBERTEncoder
from ml.recruitment.models.base import RankingModel

if TYPE_CHECKING:
    from ml.recruitment.data.schema import CandidateRecord, JobDescription, Pair


class SBERTRanker(RankingModel):
    requires_training = False  # uses pre-trained encoder

    def __init__(self, encoder: SBERTEncoder | None = None) -> None:
        self._encoder = encoder if encoder is not None else SBERTEncoder()

    @property
    def name(self) -> str:
        return f"semantic-sbert::{self._encoder.name}"

    def fit(self, pairs: Sequence[Pair]) -> SBERTRanker:
        # Optional cache warm-up: encode all candidate CVs and JD descriptions
        # so subsequent `score` calls hit memory only.
        cv_texts: list[str] = []
        jd_texts: list[str] = []
        seen_cv: set[str] = set()
        seen_jd: set[str] = set()
        for p in pairs:
            if p.candidate.candidate_id not in seen_cv and p.candidate.cv_text:
                cv_texts.append(p.candidate.cv_text)
                seen_cv.add(p.candidate.candidate_id)
            if p.job.job_id not in seen_jd:
                jd_texts.append(f"{p.job.title}\n{p.job.description}")
                seen_jd.add(p.job.job_id)
        if cv_texts:
            self._encoder.encode(cv_texts)
        if jd_texts:
            self._encoder.encode(jd_texts)
        return self

    def score(self, jd: JobDescription, candidates: Sequence[CandidateRecord]) -> np.ndarray:
        if len(candidates) == 0:
            return np.empty(0, dtype=np.float32)
        jd_vec = self._encoder.encode([f"{jd.title}\n{jd.description}"])[0]
        cv_vecs = self._encoder.encode([c.cv_text or "" for c in candidates])
        # Embeddings normalised at encode-time → dot product = cosine.
        return (cv_vecs @ jd_vec).astype(np.float32, copy=False)
