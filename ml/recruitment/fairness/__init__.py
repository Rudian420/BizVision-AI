"""Fairness auditing + post-hoc mitigation for recruitment rankings."""

from ml.recruitment.fairness.auditor import (
    FairnessReport,
    GroupMetric,
    audit_ranking,
    intersectional_audit,
)
from ml.recruitment.fairness.mitigation import (
    apply_threshold_optimisation,
    reweigh_pairs,
)

__all__ = [
    "FairnessReport",
    "GroupMetric",
    "apply_threshold_optimisation",
    "audit_ranking",
    "intersectional_audit",
    "reweigh_pairs",
]
