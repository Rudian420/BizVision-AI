"""
Post-hoc fairness mitigation.

Two techniques wired here:

  • **Reweighing (Kamiran & Calders, 2012)** — assigns each training
    sample a weight so the joint distribution P(label, attribute) becomes
    the product of marginals P(label) · P(attribute). XGBoost natively
    accepts `sample_weight` so this is a one-line change at fit time.

  • **Threshold optimisation (Hardt et al., 2016)** — adjusts the
    per-group selection threshold to equalise TPR (Equalized Opportunity).
    Applied *after* training; preserves the model.

Both are conservative compared to in-processing techniques (adversarial
debiasing); we pair them here for transparency and easy ablation. The
adversarial path lives in `ml.shared.fairness.fairness_auditor` (Phase 4).
"""

from __future__ import annotations

import numpy as np


def reweigh_pairs(
    labels: np.ndarray,
    protected: np.ndarray,
) -> np.ndarray:
    """Kamiran & Calders reweighing.

    Returns one weight per training sample. Multiply through `sample_weight`
    at fit time.
    """
    if labels.shape != protected.shape:
        raise ValueError("labels and protected must have identical shapes")
    n = labels.size
    if n == 0:
        return np.empty(0, dtype=np.float64)

    # P(label) and P(attribute) marginals.
    label_vals, label_counts = np.unique(labels, return_counts=True)
    p_label = dict(zip(label_vals, label_counts / n, strict=False))

    attr_vals, attr_counts = np.unique(protected, return_counts=True)
    p_attr = dict(zip(attr_vals, attr_counts / n, strict=False))

    weights = np.ones(n, dtype=np.float64)
    for label in label_vals:
        for attr in attr_vals:
            mask = (labels == label) & (protected == attr)
            n_la = int(mask.sum())
            if n_la == 0:
                continue
            # Target P(label) · P(attr) ; actual P(label, attr)
            target = float(p_label[label] * p_attr[attr])
            actual = n_la / n
            weights[mask] = target / actual
    return weights


def apply_threshold_optimisation(
    scores: np.ndarray,
    *,
    protected: np.ndarray,
    y_true: np.ndarray,
    target_tpr: float | None = None,
) -> dict[str, float]:
    """Hardt et al. (2016) threshold optimisation for *equal opportunity*.

    Finds a per-group score threshold such that TPR is equalised across
    groups at (or just above) `target_tpr`. If `target_tpr` is None we
    use the minimum achievable TPR across groups so no group loses recall.

    Returns ``{group: threshold}``. Callers binarise scores by selecting
    candidates whose score ≥ threshold[their_group].
    """
    groups = np.unique(protected)
    # Determine the target — minimum TPR achievable at threshold = score_min.
    if target_tpr is None:
        target_tpr = 1.0
        for g in groups:
            mask = (protected == g) & (y_true > 0)
            if mask.sum() == 0:
                continue
            target_tpr = min(target_tpr, float(mask.sum()) / max(1, int((protected == g).sum())))

    thresholds: dict[str, float] = {}
    for g in groups:
        g_mask = protected == g
        g_scores = scores[g_mask]
        g_labels = y_true[g_mask]
        if g_labels.sum() == 0:
            thresholds[str(g)] = float(g_scores.max() + 1.0)  # never select
            continue

        pos_scores = np.sort(g_scores[g_labels > 0])[::-1]
        # k = ceil(target_tpr × n_pos): the cutoff that yields ≥ target_tpr.
        k = int(np.ceil(target_tpr * pos_scores.size))
        k = min(max(k, 1), pos_scores.size)
        thresholds[str(g)] = float(pos_scores[k - 1])
    return thresholds
