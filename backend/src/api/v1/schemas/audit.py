"""
BizVision AI — Cross-Module Audit Log Schemas

Pydantic schemas for the `/api/v1/audits` API. The audit log is
append-only — the API surface is read-only (list + get + summary).
Recording happens through `AuditService.record(...)` called by the
module services (see ADR-031), never via HTTP from the client.
"""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from src.api.v1.schemas.common import PaginatedResponse


class AuditModuleName(str, enum.Enum):
    RECRUITMENT = "recruitment"
    PRICING = "pricing"
    FORECASTING = "forecasting"
    SUSTAINABILITY = "sustainability"
    CHATBOT = "chatbot"


class AuditLogRead(BaseModel):
    """One audit row as exposed by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    module: AuditModuleName
    action: str

    reference_id: UUID | None = None
    reference_type: str | None = None

    request_summary: dict[str, Any] = Field(default_factory=dict)
    response_summary: dict[str, Any] = Field(default_factory=dict)
    explanation_summary: dict[str, Any] | None = None
    fairness_summary: dict[str, Any] | None = None

    risk_tier: str | None = None
    model_version: str
    latency_ms: float

    created_at: datetime


class AuditLogPage(PaginatedResponse[AuditLogRead]):
    """Paged audit-log envelope."""


class AuditModuleCount(BaseModel):
    """One bar in the per-module decision histogram."""

    module: AuditModuleName
    count: int = Field(0, ge=0)


class AuditRiskCount(BaseModel):
    """One slice of the risk-tier histogram (low/medium/high/critical)."""

    risk_tier: str
    count: int = Field(0, ge=0)


class AuditSummary(BaseModel):
    """Aggregated view used by the Phase-4 fairness/XAI dashboards."""

    user_id: UUID
    window_start: datetime | None = Field(
        None,
        description=(
            "Lower bound applied to `created_at` when summarising. "
            "Null means 'all time'."
        ),
    )
    total_decisions: int = Field(0, ge=0)
    by_module: list[AuditModuleCount] = Field(default_factory=list)
    by_risk_tier: list[AuditRiskCount] = Field(default_factory=list)
    latest_decision_at: datetime | None = None


class FairnessAttributeRollup(BaseModel):
    """One protected-attribute bucket in the fairness aggregation.

    Counts are the number of *decisions* (audit rows) in which this
    attribute was audited, not the number of individuals; per ADR-031
    each audit row is one ML decision. `pass_rate` is `pass_count /
    decision_count` clamped to [0, 1].
    """

    attribute: str = Field(..., description="Protected attribute name (e.g. 'gender')")
    decision_count: int = Field(0, ge=0)
    pass_count: int = Field(0, ge=0)
    fail_count: int = Field(0, ge=0)
    pass_rate: float = Field(0.0, ge=0.0, le=1.0)


class FairnessCell(BaseModel):
    """One cell in the intersectional fairness grid — the pivot of
    `fairness_summary.attributes[*].metrics[*]` onto an
    `(attribute, metric_name)` key (FE-017, TASK-043).

    `avg_value` is the mean of the raw metric value across all decisions
    in the cell (e.g. mean `demographic_parity_difference` for
    (gender, demographic_parity) in this user's audit window).
    `threshold` is the metric's pass threshold; it is constant across
    runs of the same metric, so the first non-null observation is
    cached. `pass_rate` is `pass_count / decision_count`.
    """

    attribute: str = Field(..., description="Protected attribute (e.g. 'gender')")
    metric_name: str = Field(
        ..., description="Fairness metric (e.g. 'demographic_parity')"
    )
    decision_count: int = Field(0, ge=0)
    pass_count: int = Field(0, ge=0)
    pass_rate: float = Field(0.0, ge=0.0, le=1.0)
    avg_value: float | None = Field(
        None,
        description=(
            "Mean of the raw metric value across decisions in this "
            "cell. `null` when no decision carried a numeric value."
        ),
    )
    threshold: float | None = Field(
        None,
        description=(
            "Pass threshold for the metric (cached from the first "
            "observation). `null` when no decision carried a "
            "threshold."
        ),
    )


class FairnessAggregate(BaseModel):
    """Per-protected-attribute pass-rate aggregation across audit rows
    with a non-null `fairness_summary`. Powers the Phase-4 dashboard's
    per-attribute fairness card (FAIR-003, TASK-031) and the
    intersectional fairness grid (FE-017, TASK-043).
    """

    user_id: UUID
    window_start: datetime | None = None
    total_audited_decisions: int = Field(
        0,
        ge=0,
        description=(
            "Total decisions in the window whose `fairness_summary` "
            "carries a per-attribute breakdown."
        ),
    )
    by_attribute: list[FairnessAttributeRollup] = Field(default_factory=list)
    by_attribute_metric: list[FairnessCell] = Field(
        default_factory=list,
        description=(
            "Cells of the (attribute × metric) intersectional grid. "
            "Empty when no audit row carries structured `metrics` "
            "arrays inside its `fairness_summary.attributes[]`."
        ),
    )
