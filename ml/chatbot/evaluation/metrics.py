"""
Retrieval metrics — pure numpy, no sklearn dependency.

Same philosophy as every other `ml.*.evaluation.metrics` module:
every metric implemented from its mathematical definition so the test
suite can verify each against a hand-worked example. Thesis-grade
reporting demands that the metric *used* in EXP-BOT-001..003 / AS-005
is the metric *documented* — no surprise behaviour from a future
library bump.

Conventions:
  • `retrieved`  — sequence of doc_ids returned by the retriever,
                   in rank order (most-relevant first).
  • `relevant`   — set of ground-truth relevant doc_ids.
  • All percentage outputs are *fractions* (0.12 = 12%).

These are the standard IR metrics from Manning, Raghavan & Schütze
(2008) — Recall@k, Precision@k, MRR, NDCG with binary relevance.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np


def recall_at_k(retrieved: Sequence[str], relevant: Sequence[str], k: int) -> float:
    """`|relevant ∩ retrieved[:k]| / |relevant|`.

    Returns 0 if `relevant` is empty (defined-as-no-targets, not a bug).
    """
    if not relevant:
        return 0.0
    if k <= 0:
        return 0.0
    top_k = set(retrieved[:k])
    rel_set = set(relevant)
    return len(top_k & rel_set) / len(rel_set)


def precision_at_k(retrieved: Sequence[str], relevant: Sequence[str], k: int) -> float:
    """`|relevant ∩ retrieved[:k]| / k`."""
    if k <= 0:
        return 0.0
    top_k = retrieved[:k]
    if not top_k:
        return 0.0
    rel_set = set(relevant)
    hits = sum(1 for doc in top_k if doc in rel_set)
    return hits / len(top_k)


def reciprocal_rank(retrieved: Sequence[str], relevant: Sequence[str]) -> float:
    """`1 / rank(first relevant)`. Returns 0 if no relevant doc retrieved."""
    rel_set = set(relevant)
    for i, doc in enumerate(retrieved, start=1):
        if doc in rel_set:
            return 1.0 / i
    return 0.0


def mean_reciprocal_rank(
    retrieved_per_query: Sequence[Sequence[str]],
    relevant_per_query: Sequence[Sequence[str]],
) -> float:
    """Mean of `reciprocal_rank` across queries."""
    if not retrieved_per_query:
        return 0.0
    if len(retrieved_per_query) != len(relevant_per_query):
        raise ValueError(
            f"length mismatch: {len(retrieved_per_query)} retrievals "
            f"vs {len(relevant_per_query)} relevance lists"
        )
    return float(
        np.mean(
            [
                reciprocal_rank(r, rel)
                for r, rel in zip(retrieved_per_query, relevant_per_query, strict=False)
            ]
        )
    )


def ndcg_at_k(
    retrieved: Sequence[str], relevant: Sequence[str], k: int
) -> float:
    """Normalized DCG with binary relevance.

    DCG@k = Σ_{i=1..k} rel(i) / log2(i + 1)
    iDCG@k = DCG@k for the best possible ranking.

    Returns 0 if `relevant` is empty.
    """
    if not relevant or k <= 0:
        return 0.0
    rel_set = set(relevant)
    top_k = retrieved[:k]
    gains = np.array([1.0 if doc in rel_set else 0.0 for doc in top_k])
    discounts = 1.0 / np.log2(np.arange(2, len(gains) + 2))
    dcg = float(np.sum(gains * discounts))

    # iDCG: best possible — `min(k, |relevant|)` ones at the top.
    n_ideal = min(k, len(rel_set))
    if n_ideal == 0:
        return 0.0
    ideal_gains = np.ones(n_ideal)
    ideal_discounts = 1.0 / np.log2(np.arange(2, n_ideal + 2))
    idcg = float(np.sum(ideal_gains * ideal_discounts))
    if idcg == 0:
        return 0.0
    return dcg / idcg


def routing_accuracy(
    predicted_modules: Sequence[str], expected_modules: Sequence[str]
) -> float:
    """Fraction of queries routed to the correct module."""
    if not predicted_modules:
        return 0.0
    if len(predicted_modules) != len(expected_modules):
        raise ValueError(
            f"length mismatch: {len(predicted_modules)} predictions vs "
            f"{len(expected_modules)} ground truths"
        )
    return float(
        np.mean(
            [
                int(p == e)
                for p, e in zip(predicted_modules, expected_modules, strict=False)
            ]
        )
    )
