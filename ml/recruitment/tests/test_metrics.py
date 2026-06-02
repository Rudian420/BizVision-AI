"""
Offline unit tests for the ranking metrics.

These verify each implementation against a hand-worked example or a
mathematical identity. Pure numpy + pytest — runnable without any of the
heavy ML libs, so they go green in CI on first install.
"""

from __future__ import annotations

import numpy as np
import pytest

from ml.recruitment.evaluation.metrics import (
    average_precision_at_k,
    compute_ranking_metrics,
    mean_reciprocal_rank,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
    roc_auc,
    spearman_correlation,
)

# ── precision / recall / MAP ────────────────────────────────────────


def test_precision_at_k_perfect_ranking():
    y_true = np.array([1, 1, 1, 0, 0])
    y_score = np.array([0.9, 0.8, 0.7, 0.2, 0.1])
    assert precision_at_k(y_true, y_score, 3) == pytest.approx(1.0)
    assert precision_at_k(y_true, y_score, 5) == pytest.approx(3 / 5)


def test_recall_at_k_full_recall():
    y_true = np.array([1, 1, 0, 1])
    y_score = np.array([0.9, 0.8, 0.1, 0.7])
    assert recall_at_k(y_true, y_score, 3) == pytest.approx(1.0)


def test_recall_at_k_zero_relevant():
    y_true = np.zeros(4)
    y_score = np.array([0.9, 0.8, 0.1, 0.7])
    assert recall_at_k(y_true, y_score, 3) == 0.0


def test_average_precision_at_k_handworked():
    # Ranked positions of relevant items: 1, 3 out of 5.
    # AP@5 = (1/1 + 2/3) / 2 = (1 + 0.6667) / 2 = 0.8333
    y_true = np.array([1, 0, 1, 0, 0])
    y_score = np.array([1.0, 0.8, 0.6, 0.4, 0.2])
    assert average_precision_at_k(y_true, y_score, 5) == pytest.approx(5 / 6)


# ── NDCG ─────────────────────────────────────────────────────────────


def test_ndcg_perfect_ranking_is_one():
    y_true = np.array([3, 2, 1, 0])
    y_score = np.array([0.9, 0.8, 0.7, 0.1])
    assert ndcg_at_k(y_true, y_score, 4) == pytest.approx(1.0)


def test_ndcg_reverse_ranking_is_below_one():
    y_true = np.array([3, 2, 1, 0])
    y_score = np.array([0.1, 0.2, 0.3, 0.9])  # worst case: 0 at top
    val = ndcg_at_k(y_true, y_score, 4)
    assert 0.0 < val < 0.6


def test_ndcg_handworked_binary():
    """Binary case, hand-worked to 6 dp from the formula."""
    y_true = np.array([1, 0, 1, 0])
    y_score = np.array([0.9, 0.8, 0.7, 0.1])
    # DCG = 1/log2(2) + 0/log2(3) + 1/log2(4) + 0/log2(5) = 1 + 0.5 = 1.5
    # IDCG = 1 + 1/log2(3) + 0 + 0 = 1 + 0.6309 = 1.6309
    expected = 1.5 / (1 + 1 / np.log2(3))
    assert ndcg_at_k(y_true, y_score, 4) == pytest.approx(expected, rel=1e-6)


def test_ndcg_with_k_smaller_than_n():
    y_true = np.array([3, 0, 2, 1, 0, 3])
    y_score = np.array([0.9, 0.1, 0.8, 0.5, 0.2, 0.7])
    assert 0 < ndcg_at_k(y_true, y_score, 3) <= 1


# ── MRR ──────────────────────────────────────────────────────────────


def test_mrr_first_position_is_one():
    assert mean_reciprocal_rank(
        np.array([1, 0, 0, 0]), np.array([0.9, 0.5, 0.3, 0.1])
    ) == pytest.approx(1.0)


def test_mrr_third_position_is_one_third():
    assert mean_reciprocal_rank(
        np.array([0, 0, 1, 0]), np.array([0.9, 0.5, 0.3, 0.1])
    ) == pytest.approx(1 / 3)


def test_mrr_no_relevant_is_zero():
    assert mean_reciprocal_rank(np.zeros(4), np.array([0.9, 0.5, 0.3, 0.1])) == 0.0


# ── AUC ──────────────────────────────────────────────────────────────


def test_auc_perfect_separation_is_one():
    y_true = np.array([0, 0, 1, 1])
    y_score = np.array([0.1, 0.2, 0.8, 0.9])
    assert roc_auc(y_true, y_score) == pytest.approx(1.0)


def test_auc_random_is_about_half():
    rng = np.random.default_rng(0)
    y_true = rng.integers(0, 2, size=4000)
    y_score = rng.random(size=4000)
    assert 0.45 <= roc_auc(y_true, y_score) <= 0.55


def test_auc_tied_scores_average_rank():
    # Identical scores → AUC must be 0.5 by symmetry.
    y_true = np.array([0, 1, 0, 1])
    y_score = np.array([0.5, 0.5, 0.5, 0.5])
    assert roc_auc(y_true, y_score) == pytest.approx(0.5)


def test_auc_all_negatives_returns_half():
    assert roc_auc(np.zeros(5), np.linspace(0, 1, 5)) == 0.5


# ── Spearman ─────────────────────────────────────────────────────────


def test_spearman_monotone_is_one():
    a = np.array([1.0, 2.0, 3.0, 4.0])
    b = np.array([10.0, 20.0, 30.0, 40.0])
    assert spearman_correlation(a, b) == pytest.approx(1.0)


def test_spearman_anti_monotone_is_minus_one():
    a = np.array([1.0, 2.0, 3.0, 4.0])
    b = a[::-1].copy()
    assert spearman_correlation(a, b) == pytest.approx(-1.0)


# ── Multi-query helper ───────────────────────────────────────────────


def test_compute_ranking_metrics_aggregates_across_queries():
    yt1 = np.array([1, 0, 1])
    ys1 = np.array([0.9, 0.1, 0.8])
    yt2 = np.array([0, 1, 0])
    ys2 = np.array([0.1, 0.8, 0.2])

    out = compute_ranking_metrics([yt1, yt2], [ys1, ys2], ks=(1, 3))
    assert 0.0 <= out["ndcg@1"] <= 1.0
    assert "auc" in out
    assert "mrr" in out
