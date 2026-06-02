"""
ESG scoring metrics — pure numpy, no sklearn dependency.

Same philosophy as `ml.recruitment.evaluation.metrics`,
`ml.pricing.evaluation.metrics`, and `ml.forecasting.evaluation.metrics`:
every metric implemented from its mathematical definition so the test
suite can verify each against a hand-worked example. Thesis-grade
reporting demands that the metric *used* in EXP-ESG-001..003 / AS-004
is the metric *documented* — no surprise behaviour from a future
library bump.

Conventions:
  • `y_true`  — observed binary labels in {0, 1}, shape (n,) or (n, K).
  • `y_pred`  — predicted binary labels, same shape.
  • `y_proba` — predicted probabilities in [0, 1], same shape as `y_true`.
  • All percentage outputs are *fractions* (0.12 = 12%).
"""

from __future__ import annotations

import numpy as np


def _confusion(y_true: np.ndarray, y_pred: np.ndarray) -> tuple[int, int, int, int]:
    """Return (TP, FP, FN, TN)."""
    tp = int(np.sum((y_true == 1) & (y_pred == 1)))
    fp = int(np.sum((y_true == 0) & (y_pred == 1)))
    fn = int(np.sum((y_true == 1) & (y_pred == 0)))
    tn = int(np.sum((y_true == 0) & (y_pred == 0)))
    return tp, fp, fn, tn


def precision(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """TP / (TP + FP). Returns 0 when no positive predictions."""
    y_true = np.asarray(y_true).astype(np.int64)
    y_pred = np.asarray(y_pred).astype(np.int64)
    tp, fp, _, _ = _confusion(y_true, y_pred)
    return tp / (tp + fp) if (tp + fp) > 0 else 0.0


def recall(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """TP / (TP + FN). Returns 0 when no positive labels."""
    y_true = np.asarray(y_true).astype(np.int64)
    y_pred = np.asarray(y_pred).astype(np.int64)
    tp, _, fn, _ = _confusion(y_true, y_pred)
    return tp / (tp + fn) if (tp + fn) > 0 else 0.0


def f1_score(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """2·P·R / (P + R). Returns 0 when both are 0."""
    p = precision(y_true, y_pred)
    r = recall(y_true, y_pred)
    if p + r == 0:
        return 0.0
    return 2.0 * p * r / (p + r)


def accuracy(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """(TP + TN) / N. Defined for any (y_true, y_pred) of the same shape."""
    y_true = np.asarray(y_true).astype(np.int64)
    y_pred = np.asarray(y_pred).astype(np.int64)
    if y_true.size == 0:
        return 0.0
    return float(np.mean(y_true == y_pred))


def macro_f1(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Mean of per-label F1 over a multi-label `(n, K)` matrix.

    Unweighted average — every pillar (E, S, G) is equally important
    regardless of label rate. This is the metric AS-004 reports.
    """
    y_true = np.asarray(y_true).astype(np.int64)
    y_pred = np.asarray(y_pred).astype(np.int64)
    if y_true.ndim == 1:
        return f1_score(y_true, y_pred)
    if y_true.shape[1] == 0:
        return 0.0
    return float(np.mean([f1_score(y_true[:, k], y_pred[:, k]) for k in range(y_true.shape[1])]))


def brier_score(y_true: np.ndarray, y_proba: np.ndarray) -> float:
    """Mean squared error between predicted probability and true label.

    Proper scoring rule (Brier 1950) — lower is better. Applied
    pillar-wise then averaged for the multi-label case. Distinct from
    accuracy/F1 because it penalises *miscalibrated* probabilities even
    when the thresholded prediction is correct.
    """
    y_true = np.asarray(y_true).astype(np.float64)
    y_proba = np.asarray(y_proba).astype(np.float64)
    if y_true.size == 0:
        return 0.0
    return float(np.mean((y_proba - y_true) ** 2))


def expected_calibration_error(
    y_true: np.ndarray, y_proba: np.ndarray, n_bins: int = 10
) -> float:
    """ECE — Naeini, Cooper & Hauskrecht (2015).

    Bin predictions by probability, compare mean predicted-prob to
    empirical positive rate per bin, weight each gap by bin size.
    Lower is better; 0 = perfectly calibrated.

    Flattens both inputs so the multi-label call site can pass `(n, K)`
    matrices without further reshaping.
    """
    y_true = np.asarray(y_true).astype(np.float64).ravel()
    y_proba = np.clip(np.asarray(y_proba).astype(np.float64).ravel(), 0.0, 1.0)
    if y_true.size == 0:
        return 0.0
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    total_gap = 0.0
    n = y_true.size
    for k in range(n_bins):
        lo = edges[k]
        hi = edges[k + 1]
        # Inclusive on the right for the last bin so prob = 1 is binned.
        if k == n_bins - 1:
            mask = (y_proba >= lo) & (y_proba <= hi)
        else:
            mask = (y_proba >= lo) & (y_proba < hi)
        if not mask.any():
            continue
        bin_conf = float(np.mean(y_proba[mask]))
        bin_acc = float(np.mean(y_true[mask]))
        total_gap += (np.sum(mask) / n) * abs(bin_conf - bin_acc)
    return float(total_gap)


def hamming_loss(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Fraction of (sample, label) entries that disagree.

    For multi-label classification this is more informative than
    subset-accuracy (which requires *all* labels right): it captures
    partial correctness when some pillars are right and others wrong.
    """
    y_true = np.asarray(y_true).astype(np.int64)
    y_pred = np.asarray(y_pred).astype(np.int64)
    if y_true.size == 0:
        return 0.0
    return float(np.mean(y_true != y_pred))
