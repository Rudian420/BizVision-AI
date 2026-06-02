"""
Industry-level group fairness audit for ESG scoring.

ESG benchmarking has an inherent fairness problem: industries differ
in their baseline ESG potential (a tech firm's carbon intensity is a
small fraction of a logistics firm's, regardless of effort). A naive
classifier trained on cross-industry labels will systematically
under-score high-intensity industries — disparate impact that the
package must measure even though both pillars (the classifier and the
label-generation process) are "doing what they should."

This module implements two industry-conditional fairness measures
from the AIF360 / Fairlearn vocabulary:

  • **Disparate Impact (DI)** — the ratio of positive-prediction rate
    in the minority group to the majority group. DI ∈ [0, ∞);
    1.0 = no disparity; the legal "four-fifths rule" flags
    DI < 0.80 as actionable disparate impact (EEOC 1978).

  • **Demographic Parity Difference (DPD)** — the absolute
    difference between max and min positive-prediction rate across
    groups. DPD ∈ [0, 1]; 0 = perfect parity.

Both are computed *per pillar* (E / S / G) so the audit surfaces which
pillar's classifier is most disparate. The audit also reports per-group
positive rates and sample sizes so a thesis-reviewer can see the
underlying distribution.

This is the sustainability analogue of `ml.recruitment.fairness.auditor`
(intersectional protected-attribute audit). The protected attribute
here is `industry` rather than gender / age — same statistical machinery,
different context.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from ml.sustainability.data.schema import CompanyProfile
from ml.sustainability.features.structured import PILLAR_NAMES
from ml.sustainability.models.base import ESGScorer


@dataclass(frozen=True)
class GroupFairnessMetric:
    """Per-pillar fairness summary across protected groups (industries)."""

    pillar: str
    per_group_rate: dict[str, float]
    per_group_n: dict[str, int]
    reference_group: str
    disparate_impact: float
    demographic_parity_difference: float
    four_fifths_violated: bool


@dataclass(frozen=True)
class FairnessAuditResult:
    """Full audit across all three pillars."""

    threshold: float
    per_pillar: tuple[GroupFairnessMetric, ...]

    @property
    def any_violation(self) -> bool:
        return any(m.four_fifths_violated for m in self.per_pillar)


def disparate_impact(
    rate_min: float, rate_max: float, *, epsilon: float = 1e-9
) -> float:
    """Ratio of minority-group positive rate to majority-group rate.

    By convention DI is computed with the *higher-rate* group as the
    reference, so DI ∈ [0, 1] — the lower the value, the more biased
    against the minority group.
    """
    if rate_max <= epsilon:
        return 1.0  # both rates are ~0; no disparate impact possible.
    return rate_min / rate_max


def four_fifths_rule_violation(di: float, threshold: float = 0.80) -> bool:
    """EEOC 1978: DI < 0.80 is actionable disparate impact."""
    return di < threshold


def _positive_rate(probs: np.ndarray, threshold: float) -> float:
    if probs.size == 0:
        return 0.0
    return float(np.mean(probs >= threshold))


def audit_industry_fairness(
    model: ESGScorer,
    profiles: Sequence[CompanyProfile],
    *,
    threshold: float = 0.5,
) -> FairnessAuditResult:
    """Run the per-pillar industry fairness audit.

    Steps:
      1. score every profile (pull the 3-element probability vector)
      2. group by industry
      3. per pillar, compute positive rate per industry
      4. report DI (min / max) + DPD (max - min) + 4/5-rule flag

    Returns one `GroupFairnessMetric` per pillar plus the global
    `any_violation` flag.
    """
    if not profiles:
        return FairnessAuditResult(threshold=threshold, per_pillar=())

    # Step 1: collect probabilities + industry per company.
    by_industry: dict[str, list[np.ndarray]] = {}
    for profile in profiles:
        probs = model.score_proba(profile)
        by_industry.setdefault(profile.industry, []).append(probs)

    per_pillar: list[GroupFairnessMetric] = []
    for k, pillar_name in enumerate(PILLAR_NAMES):
        rates: dict[str, float] = {}
        sizes: dict[str, int] = {}
        for ind, rows in by_industry.items():
            arr = np.array([r[k] for r in rows], dtype=np.float64)
            rates[ind] = _positive_rate(arr, threshold)
            sizes[ind] = len(rows)
        if not rates:
            continue

        values = np.array(list(rates.values()), dtype=np.float64)
        rate_max = float(values.max())
        rate_min = float(values.min())
        ref_group = max(rates, key=rates.get)
        di = disparate_impact(rate_min, rate_max)
        dpd = float(rate_max - rate_min)
        per_pillar.append(
            GroupFairnessMetric(
                pillar=pillar_name,
                per_group_rate={k_: float(v) for k_, v in rates.items()},
                per_group_n={k_: int(v) for k_, v in sizes.items()},
                reference_group=ref_group,
                disparate_impact=di,
                demographic_parity_difference=dpd,
                four_fifths_violated=four_fifths_rule_violation(di),
            )
        )

    return FairnessAuditResult(threshold=threshold, per_pillar=tuple(per_pillar))
