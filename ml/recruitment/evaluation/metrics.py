"""
Ranking + classification metrics — pure numpy, no sklearn dependency.

Every metric is implemented from its mathematical definition rather than
re-exported from a library: it costs ~150 LOC but guarantees that the
metric used in the thesis is the metric documented (no surprise behaviour
from a future library version) and that the test suite can verify each
implementation against a hand-worked example.

Conventions:
  • `y_true`  — ground-truth relevance scores (binary or graded ∈ ℕ).
  • `y_score` — model scores (higher = more relevant; no calibration assumed).
  • `k`       — top-k cutoff.

All functions accept 1-D arrays; multi-query evaluation (`compute_ranking_metrics`)
groups pairs by query, computes per-query metrics, and averages.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

# ── Single-query ranking metrics ─────────────────────────────────────


def precision_at_k(y_true: np.ndarray, y_score: np.ndarray, k: int) -> float:
    """Precision@k — fraction of the top-k that are relevant (y_true > 0)."""
    if k <= 0 or y_score.size == 0:
        return 0.0
    k = min(k, y_score.size)
    order = np.argsort(-y_score, kind="stable")[:k]
    return float((y_true[order] > 0).mean())


def recall_at_k(y_true: np.ndarray, y_score: np.ndarray, k: int) -> float:
    """Recall@k — fraction of all relevant items captured in the top-k."""
    n_relevant = int((y_true > 0).sum())
    if n_relevant == 0 or y_score.size == 0:
        return 0.0
    k = min(k, y_score.size)
    order = np.argsort(-y_score, kind="stable")[:k]
    return float((y_true[order] > 0).sum()) / n_relevant


def average_precision_at_k(y_true: np.ndarray, y_score: np.ndarray, k: int) -> float:
    """AP@k — area under the precision-recall curve restricted to top-k."""
    n_relevant = int((y_true > 0).sum())
    if n_relevant == 0 or y_score.size == 0:
        return 0.0
    k = min(k, y_score.size)
    order = np.argsort(-y_score, kind="stable")[:k]
    relevant = (y_true[order] > 0).astype(np.float64)
    cumhits = np.cumsum(relevant)
    precisions = cumhits / (np.arange(k) + 1)
    return float((precisions * relevant).sum() / min(n_relevant, k))


def ndcg_at_k(y_true: np.ndarray, y_score: np.ndarray, k: int) -> float:
    """Normalised DCG@k. Uses the gain formulation ``gain = 2^rel - 1``
    (Järvelin & Kekäläinen, 2002) so graded relevance contributes
    non-linearly. Returns 0 for all-zero queries."""
    if k <= 0 or y_score.size == 0:
        return 0.0
    k = min(k, y_score.size)
    order = np.argsort(-y_score, kind="stable")[:k]
    gains = np.power(2.0, y_true[order].astype(np.float64)) - 1.0
    discounts = 1.0 / np.log2(np.arange(k) + 2)
    dcg = float((gains * discounts).sum())

    ideal_order = np.argsort(-y_true, kind="stable")[:k]
    ideal_gains = np.power(2.0, y_true[ideal_order].astype(np.float64)) - 1.0
    idcg = float((ideal_gains * discounts).sum())
    return dcg / idcg if idcg > 0 else 0.0


def mean_reciprocal_rank(y_true: np.ndarray, y_score: np.ndarray) -> float:
    """1 / rank of the first relevant item, or 0 if none ranked."""
    if y_score.size == 0:
        return 0.0
    order = np.argsort(-y_score, kind="stable")
    for rank, idx in enumerate(order, start=1):
        if y_true[idx] > 0:
            return 1.0 / rank
    return 0.0


# ── Classification metric ────────────────────────────────────────────


def roc_auc(y_true: np.ndarray, y_score: np.ndarray) -> float:
    """Binary ROC-AUC via the Mann-Whitney U identity.

    AUC = P(score_pos > score_neg). Handles ties by giving them rank-mean
    (sklearn's default behaviour). O(n log n)."""
    y_true = np.asarray(y_true)
    y_score = np.asarray(y_score)
    if y_score.size == 0:
        return 0.0
    pos = y_true > 0
    n_pos = int(pos.sum())
    n_neg = y_true.size - n_pos
    if n_pos == 0 or n_neg == 0:
        return 0.5  # undefined → assume chance

    # Average rank handles ties.
    order = np.argsort(y_score, kind="stable")
    ranks = np.empty(y_score.size, dtype=np.float64)
    ranks[order] = np.arange(1, y_score.size + 1)
    # Average rank for ties — group by score and assign mean rank.
    sorted_scores = y_score[order]
    i = 0
    while i < sorted_scores.size:
        j = i
        while j + 1 < sorted_scores.size and sorted_scores[j + 1] == sorted_scores[i]:
            j += 1
        if j > i:
            mean_rank = (ranks[order[i]] + ranks[order[j]]) / 2.0
            for kk in range(i, j + 1):
                ranks[order[kk]] = mean_rank
        i = j + 1

    sum_pos_ranks = float(ranks[pos].sum())
    return (sum_pos_ranks - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg)


# ── Correlation ──────────────────────────────────────────────────────


def spearman_correlation(a: np.ndarray, b: np.ndarray) -> float:
    """Spearman ρ between two same-length vectors (Pearson on ranks)."""
    if a.size != b.size or a.size < 2:
        return 0.0
    ar = _rankdata(a)
    br = _rankdata(b)
    am, bm = ar.mean(), br.mean()
    num = float(((ar - am) * (br - bm)).sum())
    den = float(np.sqrt(((ar - am) ** 2).sum() * ((br - bm) ** 2).sum()))
    return num / den if den > 0 else 0.0


def _rankdata(a: np.ndarray) -> np.ndarray:
    """Tied-rank assignment (average), mirroring scipy.stats.rankdata."""
    order = np.argsort(a, kind="stable")
    ranks = np.empty(a.size, dtype=np.float64)
    ranks[order] = np.arange(1, a.size + 1)
    # Average ranks for ties.
    sorted_a = a[order]
    i = 0
    while i < sorted_a.size:
        j = i
        while j + 1 < sorted_a.size and sorted_a[j + 1] == sorted_a[i]:
            j += 1
        if j > i:
            mean_rank = (ranks[order[i]] + ranks[order[j]]) / 2.0
            for kk in range(i, j + 1):
                ranks[order[kk]] = mean_rank
        i = j + 1
    return ranks


# ── Multi-query helper ───────────────────────────────────────────────


def compute_ranking_metrics(
    grouped_truth: Sequence[np.ndarray],
    grouped_scores: Sequence[np.ndarray],
    *,
    ks: Sequence[int] = (1, 3, 5, 10),
) -> dict[str, float]:
    """Average ranking metrics across queries. Each group is one query.

    Returns a flat dict like:
        { 'ndcg@5': 0.74, 'precision@5': 0.62, 'recall@5': 0.55,
          'map@5': 0.49, 'mrr': 0.66, 'auc': 0.81 }
    """
    out: dict[str, list[float]] = {}
    flat_truth: list[np.ndarray] = []
    flat_scores: list[np.ndarray] = []

    for yt, ys in zip(grouped_truth, grouped_scores, strict=False):
        for k in ks:
            out.setdefault(f"ndcg@{k}", []).append(ndcg_at_k(yt, ys, k))
            out.setdefault(f"precision@{k}", []).append(precision_at_k(yt, ys, k))
            out.setdefault(f"recall@{k}", []).append(recall_at_k(yt, ys, k))
            out.setdefault(f"map@{k}", []).append(average_precision_at_k(yt, ys, k))
        out.setdefault("mrr", []).append(mean_reciprocal_rank(yt, ys))
        flat_truth.append(yt)
        flat_scores.append(ys)

    flat_t = np.concatenate(flat_truth) if flat_truth else np.array([])
    flat_s = np.concatenate(flat_scores) if flat_scores else np.array([])
    out["auc"] = [roc_auc(flat_t, flat_s)]

    return {k: float(np.mean(v)) for k, v in out.items()}
