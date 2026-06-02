"""
Fairness auditing for ranking decisions (RC-002).

We implement three layers, each addressing a different research question:

  1. **Group fairness** — demographic parity, equalized odds, selection-rate
     parity. Uses Fairlearn for the canonical implementations.
  2. **Intersectional fairness** — same metrics, but over the Cartesian
     product of two protected attributes (e.g. gender × age_group).
     Closes a literature gap noted in RC-002.
  3. **SHAP-attributed bias** — see `explainability.shap_adapter` —
     decomposes the parity gap into per-feature contributions.

All three feed the `FairnessReport` returned to the API layer.

Selection threshold: a ranking model produces a continuous score; we
binarise it at the top-K position (the recruiter shortlist size) because
that's the decision actually affecting the candidate.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import numpy as np


@dataclass(frozen=True)
class GroupMetric:
    """Selection-rate / TPR / FPR for one demographic group."""

    group: str
    n: int
    selection_rate: float
    true_positive_rate: float | None = None
    false_positive_rate: float | None = None


@dataclass
class FairnessReport:
    """Audit output for a single ranking decision.

    The DPD and EOD numbers are the headline metrics; the
    `per_group` map exposes the underlying rates for transparency,
    and `bias_decomposition` (if provided) supplies the novel per-feature
    attribution from RC-002.
    """

    protected_attribute: str
    timestamp: datetime
    n_samples: int
    threshold_topk: int

    demographic_parity_difference: float
    equalized_odds_difference: float | None
    disparate_impact: float

    per_group: list[GroupMetric] = field(default_factory=list)
    overall_risk: str = "low"  # "low" | "medium" | "high" | "critical"
    interpretation: str = ""

    # Optional: filled by SHAPRecruitmentExplainer.bias_decomposition.
    bias_decomposition: Any | None = None


# Thresholds tuned to common HR fairness guidelines (4/5-ths rule = 0.8 DI).
_RISK_DPD = ((0.05, "low"), (0.10, "medium"), (0.20, "high"))
_CRITICAL = "critical"


def _risk_for(dpd: float) -> str:
    for thresh, label in _RISK_DPD:
        if dpd <= thresh:
            return label
    return _CRITICAL


def audit_ranking(
    scores: np.ndarray,
    *,
    y_true: np.ndarray | None,
    protected: np.ndarray,
    attribute_name: str,
    top_k: int,
) -> FairnessReport:
    """Audit one ranking against one protected attribute.

    `scores`     — model output, higher = more relevant.
    `y_true`     — ground-truth hire labels (optional; needed for EOD).
    `protected`  — 1-D string array of group labels aligned to `scores`.
    `attribute_name` — e.g. "gender".
    `top_k`      — shortlist size; candidates ranked < k are "selected".
    """
    n = scores.size
    if n == 0:
        raise ValueError("audit_ranking received an empty batch")

    selected = _topk_mask(scores, top_k)
    groups = np.unique(protected)

    per_group: list[GroupMetric] = []
    selection_rates: dict[str, float] = {}
    tprs: dict[str, float] = {}
    fprs: dict[str, float] = {}

    for g in groups:
        mask = protected == g
        n_g = int(mask.sum())
        sel_g = float(selected[mask].mean())
        tpr: float | None = None
        fpr: float | None = None
        if y_true is not None:
            yt = y_true[mask].astype(bool)
            sel = selected[mask].astype(bool)
            if yt.any():
                tpr = float(sel[yt].mean())
                tprs[g] = tpr
            if (~yt).any():
                fpr = float(sel[~yt].mean())
                fprs[g] = fpr
        selection_rates[g] = sel_g
        per_group.append(
            GroupMetric(
                group=str(g),
                n=n_g,
                selection_rate=sel_g,
                true_positive_rate=tpr,
                false_positive_rate=fpr,
            )
        )

    dpd = max(selection_rates.values()) - min(selection_rates.values())
    di_min = min(selection_rates.values())
    di_max = max(selection_rates.values())
    di = (di_min / di_max) if di_max > 0 else 1.0

    eod = None
    if tprs and fprs:
        eod = max(
            max(tprs.values()) - min(tprs.values()),
            max(fprs.values()) - min(fprs.values()),
        )

    risk = _risk_for(dpd)
    interp = (
        f"Selection-rate gap of {dpd:.3f} across {len(groups)} groups on "
        f"`{attribute_name}` at top-{top_k}. "
        f"Disparate impact ratio = {di:.2f} ({'passes' if di >= 0.8 else 'fails'} 4/5-ths rule)."
    )

    return FairnessReport(
        protected_attribute=attribute_name,
        timestamp=datetime.now(timezone.utc),
        n_samples=n,
        threshold_topk=top_k,
        demographic_parity_difference=float(dpd),
        equalized_odds_difference=float(eod) if eod is not None else None,
        disparate_impact=float(di),
        per_group=per_group,
        overall_risk=risk,
        interpretation=interp,
    )


def intersectional_audit(
    scores: np.ndarray,
    *,
    y_true: np.ndarray | None,
    attributes: dict[str, np.ndarray],
    top_k: int,
) -> dict[str, FairnessReport]:
    """Run an audit per attribute *and* one over the Cartesian product.

    Returns a mapping name → report, where the cross product is keyed
    "attr_a×attr_b" (and so on). Cardinality of the cross is capped at
    16 to avoid degenerate groups; raises ValueError otherwise."""
    reports: dict[str, FairnessReport] = {}
    for name, vals in attributes.items():
        reports[name] = audit_ranking(
            scores,
            y_true=y_true,
            protected=vals,
            attribute_name=name,
            top_k=top_k,
        )

    if len(attributes) >= 2:
        names = list(attributes.keys())
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                a, b = names[i], names[j]
                combo = np.array(
                    [f"{x}×{y}" for x, y in zip(attributes[a], attributes[b], strict=False)]
                )
                n_groups = len(np.unique(combo))
                if n_groups > 16:
                    raise ValueError(
                        f"Intersectional cardinality {n_groups} too high "
                        f"for stable estimation — bucket attributes first."
                    )
                reports[f"{a}×{b}"] = audit_ranking(
                    scores,
                    y_true=y_true,
                    protected=combo,
                    attribute_name=f"{a}×{b}",
                    top_k=top_k,
                )
    return reports


# ── helpers ───────────────────────────────────────────────────────────


def _topk_mask(scores: np.ndarray, k: int) -> np.ndarray:
    """Boolean mask: True where score is in the top-k by descending order."""
    if k >= scores.size:
        return np.ones_like(scores, dtype=bool)
    cutoff = np.partition(scores, -k)[-k]
    return scores >= cutoff
