"""Group-fairness auditing for ESG scoring — industry as protected group."""

from ml.sustainability.fairness.auditor import (
    FairnessAuditResult,
    GroupFairnessMetric,
    audit_industry_fairness,
    disparate_impact,
    four_fifths_rule_violation,
)

__all__ = [
    "FairnessAuditResult",
    "GroupFairnessMetric",
    "audit_industry_fairness",
    "disparate_impact",
    "four_fifths_rule_violation",
]
