"""
Offline unit tests for sustainability metrics.

Pure numpy + pytest — runnable without sklearn. Every metric is
verified against a hand-worked example from its mathematical
definition; surprise behaviour from a future library bump would break
the suite immediately.
"""

from __future__ import annotations

import numpy as np
import pytest

from ml.sustainability.evaluation.metrics import (
    accuracy,
    brier_score,
    expected_calibration_error,
    f1_score,
    hamming_loss,
    macro_f1,
    precision,
    recall,
)


# ── precision / recall / F1 ────────────────────────────────────────


def test_precision_handworked():
    """TP=2, FP=1 → P = 2/3."""
    y_true = np.array([1, 1, 0, 0])
    y_pred = np.array([1, 1, 1, 0])
    assert precision(y_true, y_pred) == pytest.approx(2.0 / 3.0)


def test_recall_handworked():
    """TP=2, FN=1 → R = 2/3."""
    y_true = np.array([1, 1, 1, 0])
    y_pred = np.array([1, 1, 0, 0])
    assert recall(y_true, y_pred) == pytest.approx(2.0 / 3.0)


def test_f1_handworked():
    """P = R = 2/3 → F1 = 2·P·R/(P+R) = 2/3."""
    y_true = np.array([1, 1, 1, 0])
    y_pred = np.array([1, 1, 0, 1])
    assert f1_score(y_true, y_pred) == pytest.approx(2.0 / 3.0)


def test_precision_no_positive_predictions_is_zero():
    assert precision(np.array([1, 1, 0]), np.array([0, 0, 0])) == 0.0


def test_recall_no_positive_labels_is_zero():
    assert recall(np.array([0, 0, 0]), np.array([1, 1, 0])) == 0.0


def test_f1_perfect_is_one():
    y = np.array([1, 0, 1, 1, 0])
    assert f1_score(y, y) == pytest.approx(1.0)


def test_f1_both_zero_is_zero():
    assert f1_score(np.array([0, 0]), np.array([0, 0])) == 0.0


# ── accuracy ───────────────────────────────────────────────────────


def test_accuracy_handworked():
    """3 of 4 right → 0.75."""
    y_true = np.array([1, 0, 1, 0])
    y_pred = np.array([1, 0, 0, 0])
    assert accuracy(y_true, y_pred) == pytest.approx(0.75)


# ── macro_f1 ───────────────────────────────────────────────────────


def test_macro_f1_handworked_2_labels():
    """Label 0: y_true=[1,0,1], y_pred=[1,0,1] → F1=1.
       Label 1: y_true=[0,1,1], y_pred=[1,1,0] → P=1/2, R=1/2 → F1=1/2.
       Macro = (1 + 1/2) / 2 = 0.75."""
    y_true = np.array([[1, 0], [0, 1], [1, 1]])
    y_pred = np.array([[1, 1], [0, 1], [1, 0]])
    assert macro_f1(y_true, y_pred) == pytest.approx(0.75)


def test_macro_f1_falls_back_to_f1_on_1d():
    """A 1-D input should be treated like a single label."""
    y = np.array([1, 0, 1])
    assert macro_f1(y, y) == pytest.approx(1.0)


# ── hamming_loss ───────────────────────────────────────────────────


def test_hamming_loss_handworked():
    """2 of 6 entries disagree → 1/3."""
    y_true = np.array([[1, 0, 1], [0, 1, 1]])
    y_pred = np.array([[0, 0, 1], [0, 0, 1]])
    # diffs at (0,0) and (1,1) → 2 disagreements out of 6
    assert hamming_loss(y_true, y_pred) == pytest.approx(2.0 / 6.0)


# ── brier_score ────────────────────────────────────────────────────


def test_brier_score_perfect_is_zero():
    y_true = np.array([0, 1, 1])
    y_proba = y_true.astype(float)
    assert brier_score(y_true, y_proba) == 0.0


def test_brier_score_handworked():
    """y_true=1, y_proba=0.7 → (0.7-1)^2 = 0.09."""
    y_true = np.array([1])
    y_proba = np.array([0.7])
    assert brier_score(y_true, y_proba) == pytest.approx(0.09)


def test_brier_score_penalises_overconfident_wrong():
    """Confident wrong (0.99 when label=0) → 0.99^2 = 0.9801."""
    y_true = np.array([0])
    y_proba = np.array([0.99])
    assert brier_score(y_true, y_proba) == pytest.approx(0.9801)


# ── expected_calibration_error ─────────────────────────────────────


def test_ece_perfect_calibration_is_zero():
    """y_true = y_proba ∈ {0, 1} → bins coincide with empirical rate."""
    y = np.array([0, 1, 0, 1, 1])
    assert expected_calibration_error(y, y.astype(float), n_bins=2) == 0.0


def test_ece_constant_proba_handworked():
    """y_true = [0, 1], y_proba = [0.5, 0.5], single bin → bin_conf=0.5,
    bin_acc=0.5 → gap = 0."""
    assert expected_calibration_error(
        np.array([0, 1]), np.array([0.5, 0.5]), n_bins=1
    ) == 0.0


def test_ece_overconfidence_gap():
    """All probs = 0.9, but only half are positive → bin conf 0.9,
    bin acc 0.5, gap 0.4 weighted by 1.0 → ECE = 0.4."""
    y_true = np.array([1, 0, 1, 0])
    y_proba = np.array([0.9, 0.9, 0.9, 0.9])
    assert expected_calibration_error(y_true, y_proba, n_bins=1) == pytest.approx(0.4)
