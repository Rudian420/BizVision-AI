"""Offline construction tests for the AuditLog ORM model.

These don't touch a database — they verify the dataclass-like shape +
the enum coercion path the service uses. Integration coverage lives in
`tests/integration/test_audit_persistence.py`.
"""

from __future__ import annotations

import uuid

import pytest

from src.models.audit import AuditLog, AuditModule


def test_audit_module_enum_values():
    """The 5 module names are architecturally fixed (ADR-031)."""
    assert {m.value for m in AuditModule} == {
        "recruitment",
        "pricing",
        "forecasting",
        "sustainability",
        "chatbot",
    }


def test_audit_module_string_coercion():
    """`AuditModule('pricing')` must equal `AuditModule.PRICING` — the
    service's `record()` accepts either form."""
    assert AuditModule("pricing") is AuditModule.PRICING
    assert AuditModule("chatbot") is AuditModule.CHATBOT


def test_audit_module_unknown_string_rejected():
    """Anything outside the 5 names raises — guards against typos."""
    with pytest.raises(ValueError):
        AuditModule("typo-module")


def test_audit_log_minimal_construction():
    """Required columns + a few JSONB fields populated."""
    row = AuditLog(
        user_id=uuid.uuid4(),
        module=AuditModule.RECRUITMENT,
        action="analyze",
        request_summary={"job_title": "Senior ML Engineer", "top_k": 5},
        response_summary={"top_candidate_score": 0.81},
        model_version="recruitment-mock-0.1",
        latency_ms=42.0,
    )
    assert row.module is AuditModule.RECRUITMENT
    assert row.action == "analyze"
    assert row.request_summary["top_k"] == 5
    assert row.latency_ms == 42.0


def test_audit_log_optional_columns_default_to_none():
    """`explanation_summary` / `fairness_summary` / `risk_tier` /
    `reference_id` / `reference_type` are all optional."""
    row = AuditLog(
        user_id=uuid.uuid4(),
        module=AuditModule.PRICING,
        action="optimize",
        model_version="pricing-mock-0.1",
        latency_ms=10.0,
    )
    assert row.explanation_summary is None
    assert row.fairness_summary is None
    assert row.risk_tier is None
    assert row.reference_id is None
    assert row.reference_type is None


def test_audit_log_reference_carries_soft_fk_pair():
    """`reference_id` + `reference_type` together identify the owning row."""
    sess_id = uuid.uuid4()
    row = AuditLog(
        user_id=uuid.uuid4(),
        module=AuditModule.RECRUITMENT,
        action="analyze",
        reference_id=sess_id,
        reference_type="recruitment_session",
        model_version="recruitment-mock-0.1",
        latency_ms=1.0,
    )
    assert row.reference_id == sess_id
    assert row.reference_type == "recruitment_session"


# ── Fairness aggregation schema (TASK-031, FAIR-003) ─────────────


def test_fairness_attribute_rollup_clamps_pass_rate():
    """`pass_rate` must be in [0, 1] — Pydantic enforces it."""
    from src.api.v1.schemas.audit import FairnessAttributeRollup

    row = FairnessAttributeRollup(
        attribute="gender",
        decision_count=10,
        pass_count=8,
        fail_count=2,
        pass_rate=0.8,
    )
    assert row.pass_rate == 0.8


def test_fairness_attribute_rollup_rejects_out_of_range_rate():
    import pytest as _pytest

    from pydantic import ValidationError

    from src.api.v1.schemas.audit import FairnessAttributeRollup

    with _pytest.raises(ValidationError):
        FairnessAttributeRollup(
            attribute="gender",
            decision_count=10,
            pass_count=8,
            fail_count=2,
            pass_rate=1.5,
        )


def test_fairness_aggregate_defaults_to_empty():
    """An empty result must serialise to the same shape so the
    frontend can render a stable empty state."""
    from src.api.v1.schemas.audit import FairnessAggregate

    row = FairnessAggregate(user_id=uuid.uuid4())
    assert row.total_audited_decisions == 0
    assert row.by_attribute == []
    assert row.by_attribute_metric == []  # TASK-043 / FE-017
    assert row.window_start is None


def test_fairness_cell_validates_bounded_pass_rate():
    """`pass_rate` is `[0, 1]` clamped at the schema level; a violating
    payload should reject."""
    from pydantic import ValidationError

    from src.api.v1.schemas.audit import FairnessCell

    # Happy path
    cell = FairnessCell(
        attribute="gender",
        metric_name="demographic_parity",
        decision_count=4,
        pass_count=3,
        pass_rate=0.75,
        avg_value=0.04,
        threshold=0.1,
    )
    assert cell.pass_rate == 0.75
    assert cell.avg_value == 0.04
    assert cell.threshold == 0.1

    # avg_value and threshold are nullable (no numeric metric value
    # was recorded)
    nullable = FairnessCell(
        attribute="age_group",
        metric_name="equal_opportunity",
        decision_count=2,
        pass_count=2,
        pass_rate=1.0,
        avg_value=None,
        threshold=None,
    )
    assert nullable.avg_value is None
    assert nullable.threshold is None

    # Out-of-range pass_rate rejected
    with pytest.raises(ValidationError):
        FairnessCell(
            attribute="gender",
            metric_name="demographic_parity",
            decision_count=1,
            pass_count=1,
            pass_rate=1.5,
            avg_value=None,
            threshold=None,
        )
