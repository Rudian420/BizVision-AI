"""
Offline unit tests for chatbot retrieval metrics.

Pure numpy + pytest — every metric verified against a hand-worked
example from its mathematical definition.
"""

from __future__ import annotations

import numpy as np
import pytest

from ml.chatbot.evaluation.metrics import (
    mean_reciprocal_rank,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
    routing_accuracy,
)


# ── recall_at_k ────────────────────────────────────────────────────


def test_recall_at_k_perfect():
    """All relevant docs in top-k → recall = 1."""
    assert recall_at_k(["a", "b", "c"], ["a", "b"], k=3) == 1.0


def test_recall_at_k_handworked():
    """1 of 3 relevant in top-5 → 1/3."""
    assert recall_at_k(["a", "b", "c", "d", "e"], ["c", "x", "y"], k=5) == pytest.approx(1.0 / 3.0)


def test_recall_at_k_zero_when_no_overlap():
    assert recall_at_k(["a", "b", "c"], ["d", "e"], k=3) == 0.0


def test_recall_at_k_truncates_at_k():
    """Only first k retrieved count — `c` after position 2 doesn't help."""
    assert recall_at_k(["a", "b", "c"], ["c"], k=2) == 0.0
    assert recall_at_k(["a", "b", "c"], ["c"], k=3) == 1.0


def test_recall_at_k_empty_relevant_is_zero():
    assert recall_at_k(["a", "b"], [], k=3) == 0.0


# ── precision_at_k ─────────────────────────────────────────────────


def test_precision_at_k_handworked():
    """2 of 3 retrieved are relevant → 2/3."""
    assert precision_at_k(["a", "b", "c"], ["a", "b", "z"], k=3) == pytest.approx(2.0 / 3.0)


def test_precision_at_k_zero():
    assert precision_at_k(["a", "b"], ["c", "d"], k=2) == 0.0


def test_precision_at_k_truncates_at_retrieved_length():
    """Only 2 retrieved but k=5 → divides by 2 not 5."""
    assert precision_at_k(["a", "b"], ["a", "b"], k=5) == 1.0


# ── reciprocal_rank / MRR ──────────────────────────────────────────


def test_reciprocal_rank_handworked():
    """First relevant at rank 3 → 1/3."""
    assert reciprocal_rank(["x", "y", "a", "z"], ["a", "b"]) == pytest.approx(1.0 / 3.0)


def test_reciprocal_rank_no_relevant_is_zero():
    assert reciprocal_rank(["x", "y"], ["a"]) == 0.0


def test_reciprocal_rank_at_position_1():
    assert reciprocal_rank(["a"], ["a"]) == 1.0


def test_mrr_average_handworked():
    """RR = 1, 1/2 → MRR = 0.75."""
    out = mean_reciprocal_rank(
        [["a", "x"], ["x", "a"]], [["a"], ["a"]]
    )
    assert out == pytest.approx(0.75)


def test_mrr_length_mismatch_raises():
    with pytest.raises(ValueError, match="length mismatch"):
        mean_reciprocal_rank([["a"]], [["a"], ["b"]])


# ── ndcg_at_k ──────────────────────────────────────────────────────


def test_ndcg_at_k_perfect_ranking_is_one():
    """All relevant at top → DCG = iDCG → NDCG = 1."""
    assert ndcg_at_k(["a", "b", "c"], ["a", "b"], k=3) == pytest.approx(1.0)


def test_ndcg_at_k_one_relevant_at_rank_2_handworked():
    """y_true binary: rank 2 contributes 1/log2(3); ideal = 1/log2(2) = 1.
    NDCG = (1/log2(3)) / 1."""
    val = ndcg_at_k(["x", "a", "y"], ["a"], k=3)
    expected = (1.0 / np.log2(3)) / 1.0
    assert val == pytest.approx(expected)


def test_ndcg_at_k_empty_relevant_is_zero():
    assert ndcg_at_k(["a", "b"], [], k=3) == 0.0


# ── routing_accuracy ────────────────────────────────────────────────


def test_routing_accuracy_handworked():
    """3 of 4 correct → 0.75."""
    pred = ["pricing", "recruitment", "general", "forecasting"]
    true = ["pricing", "recruitment", "general", "sustainability"]
    assert routing_accuracy(pred, true) == 0.75


def test_routing_accuracy_perfect():
    pred = ["a", "b", "c"]
    assert routing_accuracy(pred, pred) == 1.0


def test_routing_accuracy_length_mismatch_raises():
    with pytest.raises(ValueError, match="length mismatch"):
        routing_accuracy(["a"], ["a", "b"])
