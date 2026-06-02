"""Ranking models for Recruitment Intelligence.

The full taxonomy used in AS-001 (recruitment ablation):

    Baselines
        RandomRanker          — uniform random scores; sanity floor.
        TFIDFRanker           — TF-IDF cosine (EXP-REC-001).
        BM25Ranker            — Okapi BM25 (lexical retrieval gold-standard).
    Single-signal
        SBERTRanker           — semantic cosine on `all-mpnet-base-v2` (EXP-REC-002).
        XGBoostRanker         — boosted trees on structured features (EXP-REC-003).
    Ensemble
        EnsembleRanker        — weighted convex combination of SBERT + boosting
                                (EXP-REC-004 — target system).

All implement the `RankingModel` interface in `models.base`; that uniform
contract is what makes the benchmark harness, ablation runner, and copilot
generic over models.
"""

from ml.recruitment.models.base import RankingModel, ScoreDetail
from ml.recruitment.models.baselines import BM25Ranker, RandomRanker, TFIDFRanker
from ml.recruitment.models.ensemble import EnsembleRanker
from ml.recruitment.models.semantic import SBERTRanker
from ml.recruitment.models.structured import XGBoostRanker

__all__ = [
    "BM25Ranker",
    "EnsembleRanker",
    "RandomRanker",
    "RankingModel",
    "SBERTRanker",
    "ScoreDetail",
    "TFIDFRanker",
    "XGBoostRanker",
]
