"""End-to-end audit log persistence + API surface.

Marked `integration` — relies on the live Postgres + Redis CI containers.
Locally these are skipped via `pytest -m "not integration"`.

Verifies:
  1. Recruitment `POST /analyze` writes one row to `audit_logs` with
     module='recruitment', action='analyze', risk_tier set, soft FK
     pointing back to the recruitment session.
  2. `GET /api/v1/audits` returns the row paginated.
  3. `GET /api/v1/audits/{id}` returns the row by id.
  4. `GET /api/v1/audits/summary` aggregates by module + risk_tier.
  5. Cross-user isolation: user B cannot read user A's audits.
  6. Module filter (`?module=pricing`) returns zero rows when only
     recruitment decisions exist.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


async def _register_and_token(client, email: str) -> str:
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "supersecret123", "full_name": "Test User"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["tokens"]["access_token"]


def _analyze_payload() -> dict:
    return {
        "job_description": {
            "title": "Senior ML Engineer",
            "description": (
                "Design and ship production ML systems with explainability."
            ),
            "required_skills": ["python", "ml"],
            "preferred_skills": ["pytorch"],
            "experience_level": "senior",
        },
        "candidates": [
            {"candidate_id": f"cand-{i:03d}", "cv_text": "Experienced."} for i in range(6)
        ],
        "anonymize_names": True,
        "protected_attributes": ["gender"],
        "top_k": 3,
        "ensemble_sbert_weight": 0.6,
    }


async def test_analyze_writes_audit_log_row(client, unique_email):
    token = await _register_and_token(client, unique_email)
    headers = {"Authorization": f"Bearer {token}"}

    # ── analyze: must trigger the audit recording ──────────────────
    resp = await client.post(
        "/api/v1/recruitment/analyze", json=_analyze_payload(), headers=headers
    )
    assert resp.status_code == 200, resp.text
    session_id = resp.json()["session_id"]

    # ── list audits: must include the recruitment row ──────────────
    resp = await client.get("/api/v1/audits", headers=headers)
    assert resp.status_code == 200, resp.text
    page = resp.json()
    assert page["total"] >= 1
    rec_rows = [
        r for r in page["items"] if r["module"] == "recruitment" and r["action"] == "analyze"
    ]
    assert rec_rows, "expected at least one recruitment/analyze audit row"
    row = rec_rows[0]
    assert row["reference_id"] == session_id
    assert row["reference_type"] == "recruitment_session"
    assert row["risk_tier"] in {"low", "medium", "high", "critical"}
    assert row["model_version"].startswith("recruitment-")
    # request/response summaries populated
    assert row["request_summary"]["top_k"] == 3
    assert "top_candidate_score" in row["response_summary"]
    # fairness summary surfaced
    assert row["fairness_summary"]["overall_risk_level"] == row["risk_tier"]


async def test_get_audit_log_by_id(client, unique_email):
    token = await _register_and_token(client, unique_email)
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.post(
        "/api/v1/recruitment/analyze", json=_analyze_payload(), headers=headers
    )
    assert resp.status_code == 200
    resp = await client.get("/api/v1/audits", headers=headers)
    audit_id = resp.json()["items"][0]["id"]

    resp = await client.get(f"/api/v1/audits/{audit_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == audit_id


async def test_audit_summary_groups_by_module_and_risk(client, unique_email):
    token = await _register_and_token(client, unique_email)
    headers = {"Authorization": f"Bearer {token}"}

    # Two analyze calls → two recruitment rows.
    for _ in range(2):
        resp = await client.post(
            "/api/v1/recruitment/analyze", json=_analyze_payload(), headers=headers
        )
        assert resp.status_code == 200

    resp = await client.get("/api/v1/audits/summary", headers=headers)
    assert resp.status_code == 200
    summary = resp.json()
    assert summary["total_decisions"] >= 2

    by_module = {row["module"]: row["count"] for row in summary["by_module"]}
    assert by_module.get("recruitment", 0) >= 2

    by_risk = {row["risk_tier"]: row["count"] for row in summary["by_risk_tier"]}
    # Recruitment service hard-codes LOW today; either way risk_tier must surface.
    assert sum(by_risk.values()) >= 2


async def test_module_filter_excludes_other_modules(client, unique_email):
    token = await _register_and_token(client, unique_email)
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.post(
        "/api/v1/recruitment/analyze", json=_analyze_payload(), headers=headers
    )
    assert resp.status_code == 200

    # Filter by a module that hasn't been wired yet (pricing) → empty
    # page even though the user does have recruitment audit rows.
    resp = await client.get("/api/v1/audits?module=pricing", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


async def test_audit_log_is_user_scoped(client, unique_email):
    # User A creates a decision.
    a_token = await _register_and_token(client, f"a-{unique_email}")
    resp = await client.post(
        "/api/v1/recruitment/analyze",
        json=_analyze_payload(),
        headers={"Authorization": f"Bearer {a_token}"},
    )
    assert resp.status_code == 200
    resp = await client.get(
        "/api/v1/audits",
        headers={"Authorization": f"Bearer {a_token}"},
    )
    a_audit_id = resp.json()["items"][0]["id"]

    # User B must see zero audit rows + get 404 on user A's audit id.
    b_token = await _register_and_token(client, f"b-{unique_email}")
    resp = await client.get(
        "/api/v1/audits",
        headers={"Authorization": f"Bearer {b_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["total"] == 0

    resp = await client.get(
        f"/api/v1/audits/{a_audit_id}",
        headers={"Authorization": f"Bearer {b_token}"},
    )
    assert resp.status_code == 404


async def test_audit_log_get_404_on_unknown_id(client, unique_email):
    token = await _register_and_token(client, unique_email)
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.get(
        "/api/v1/audits/00000000-0000-0000-0000-000000000000",
        headers=headers,
    )
    assert resp.status_code == 404


# ── Cross-module wiring (TASK-029) ─────────────────────────────────
# Each of the 4 remaining modules records an audit row through the
# same `AuditService.record(...)` call site inside its `_persist`
# helper. These tests prove the wiring writes a row with the right
# module + action + reference_type for at least the primary decision
# path; the response_summary slices are module-specific and tested
# implicitly by the row count + module filter behaviour.


def _pricing_optimize_payload() -> dict:
    return {
        "product_id": "sku-001",
        "current_price": 100.0,
        "unit_cost": 60.0,
        "objective": "revenue",
        "historical_demand": [120.0, 118.0, 122.0, 121.0],
    }


def _sustainability_score_payload() -> dict:
    return {
        "company_name": "Acme SME",
        "industry": "manufacturing",
        "annual_revenue": 5_000_000,
        "headcount": 80,
        "environmental_indicators": {"energy_efficiency": 0.7},
        "social_indicators": {"diversity": 0.6},
        "governance_indicators": {"board_independence": 0.8},
    }


def _forecast_payload() -> dict:
    # Use 14-day horizon to satisfy the >=7 Pydantic constraint.
    return {
        "series_name": "monthly_profit",
        "history": [
            {"ds": f"2026-04-{d:02d}", "y": 1000.0 + d * 12.0} for d in range(1, 21)
        ],
        "forecast_horizon_days": 14,
    }


def _chatbot_message_payload() -> dict:
    return {
        "content": "What's our forecast for the next quarter?",
        "include_modules": ["forecasting"],
    }


async def test_pricing_optimize_writes_audit_row(client, unique_email):
    token = await _register_and_token(client, unique_email)
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.post(
        "/api/v1/pricing/optimize",
        json=_pricing_optimize_payload(),
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    analysis_id = resp.json()["analysis_id"]

    resp = await client.get("/api/v1/audits?module=pricing", headers=headers)
    assert resp.status_code == 200
    page = resp.json()
    assert page["total"] >= 1
    rows = [r for r in page["items"] if r["action"] == "optimize"]
    assert rows, "expected at least one pricing/optimize audit row"
    row = rows[0]
    assert row["module"] == "pricing"
    assert row["reference_id"] == analysis_id
    assert row["reference_type"] == "pricing_analysis"
    assert row["model_version"].startswith("pricing-")
    # response_summary carries the recommended price.
    assert row["response_summary"]["recommended_price"] is not None


async def test_sustainability_score_writes_audit_row(client, unique_email):
    token = await _register_and_token(client, unique_email)
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.post(
        "/api/v1/sustainability/score",
        json=_sustainability_score_payload(),
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assessment_id = resp.json()["assessment_id"]

    resp = await client.get("/api/v1/audits?module=sustainability", headers=headers)
    assert resp.status_code == 200
    page = resp.json()
    rows = [r for r in page["items"] if r["action"] == "score"]
    assert rows, "expected at least one sustainability/score audit row"
    row = rows[0]
    assert row["module"] == "sustainability"
    assert row["reference_id"] == assessment_id
    assert row["reference_type"] == "sustainability_assessment"
    # risk_tier should be populated for /score.
    assert row["risk_tier"] in {"low", "medium", "high", "critical"}
    # response_summary carries the composite score.
    assert row["response_summary"]["composite_score"] is not None


async def test_forecasting_writes_audit_row(client, unique_email):
    token = await _register_and_token(client, unique_email)
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.post(
        "/api/v1/forecasting/forecast",
        json=_forecast_payload(),
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    forecast_id = resp.json()["forecast_id"]

    resp = await client.get("/api/v1/audits?module=forecasting", headers=headers)
    assert resp.status_code == 200
    page = resp.json()
    rows = [r for r in page["items"] if r["action"] == "forecast"]
    assert rows, "expected at least one forecasting/forecast audit row"
    row = rows[0]
    assert row["module"] == "forecasting"
    assert row["reference_id"] == forecast_id
    assert row["reference_type"] == "forecast_analysis"
    # response_summary carries the scenario end values.
    assert row["response_summary"]["base_end_value"] is not None


async def test_chatbot_message_writes_audit_row(client, unique_email):
    token = await _register_and_token(client, unique_email)
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.post(
        "/api/v1/chatbot/message",
        json=_chatbot_message_payload(),
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    message_id = resp.json()["message_id"]

    resp = await client.get("/api/v1/audits?module=chatbot", headers=headers)
    assert resp.status_code == 200
    page = resp.json()
    rows = [r for r in page["items"] if r["action"] == "message"]
    assert rows, "expected at least one chatbot/message audit row"
    row = rows[0]
    assert row["module"] == "chatbot"
    assert row["reference_id"] == message_id
    assert row["reference_type"] == "chatbot_message"
    assert row["response_summary"]["tokens_used"] > 0


async def test_recruitment_audit_records_per_attribute_fairness(client, unique_email):
    """TASK-031 — recruitment's `fairness_summary` must carry the
    per-attribute breakdown the new `/audits/fairness` endpoint reads."""
    token = await _register_and_token(client, unique_email)
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.post(
        "/api/v1/recruitment/analyze", json=_analyze_payload(), headers=headers
    )
    assert resp.status_code == 200

    resp = await client.get("/api/v1/audits?module=recruitment", headers=headers)
    assert resp.status_code == 200
    row = resp.json()["items"][0]
    fs = row["fairness_summary"]
    assert fs is not None
    assert "attributes" in fs
    assert isinstance(fs["attributes"], list)
    assert fs["attributes"], "expected at least one attribute rollup"
    attr = fs["attributes"][0]
    assert "name" in attr
    assert "passed" in attr
    assert "metrics" in attr
    # 'all_metrics_pass' is the new key — the old 'metrics_pass' is gone.
    assert "all_metrics_pass" in fs


async def test_audit_fairness_endpoint_aggregates_by_attribute(client, unique_email):
    """TASK-031 — `/api/v1/audits/fairness` returns per-attribute
    pass-rate buckets aggregated across all the user's audit rows."""
    token = await _register_and_token(client, unique_email)
    headers = {"Authorization": f"Bearer {token}"}

    # Two recruitment analyses → 2 audit rows, both with one gender bucket.
    payload = _analyze_payload()
    await client.post("/api/v1/recruitment/analyze", json=payload, headers=headers)
    await client.post("/api/v1/recruitment/analyze", json=payload, headers=headers)

    resp = await client.get("/api/v1/audits/fairness", headers=headers)
    assert resp.status_code == 200, resp.text
    agg = resp.json()

    assert agg["total_audited_decisions"] >= 2
    gender_buckets = [b for b in agg["by_attribute"] if b["attribute"] == "gender"]
    assert gender_buckets, "expected a gender bucket"
    bucket = gender_buckets[0]
    assert bucket["decision_count"] >= 2
    assert 0.0 <= bucket["pass_rate"] <= 1.0
    # The mock fairness summary always reports passed=True, so 2 calls →
    # pass_count == decision_count and pass_rate == 1.0.
    assert bucket["pass_rate"] == 1.0


async def test_audit_fairness_endpoint_is_user_scoped(client, unique_email):
    """User B's fairness aggregate must not include user A's audits."""
    a_token = await _register_and_token(client, f"a-{unique_email}")
    await client.post(
        "/api/v1/recruitment/analyze",
        json=_analyze_payload(),
        headers={"Authorization": f"Bearer {a_token}"},
    )
    b_token = await _register_and_token(client, f"b-{unique_email}")
    resp = await client.get(
        "/api/v1/audits/fairness",
        headers={"Authorization": f"Bearer {b_token}"},
    )
    assert resp.status_code == 200
    agg = resp.json()
    assert agg["total_audited_decisions"] == 0
    assert agg["by_attribute"] == []


async def test_audit_fairness_endpoint_handles_zero_decisions(client, unique_email):
    """A freshly-registered user must get a stable empty-shape response,
    not a 404 — the dashboard renders this as the empty state."""
    token = await _register_and_token(client, unique_email)
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.get("/api/v1/audits/fairness", headers=headers)
    assert resp.status_code == 200
    agg = resp.json()
    assert agg["total_audited_decisions"] == 0
    assert agg["by_attribute"] == []
    assert agg["by_attribute_metric"] == []
    assert agg["window_start"] is None


async def test_audit_fairness_endpoint_returns_intersectional_cells(client, unique_email):
    """TASK-043 / FE-017 — `/api/v1/audits/fairness` returns a
    `by_attribute_metric` list that pivots each audit row's
    `fairness_summary.attributes[*].metrics[*]` onto an
    `(attribute, metric_name)` key. Each cell carries a `pass_rate`,
    `avg_value`, and (when present) a `threshold`.

    The recruitment mock auditor writes one metric per attribute
    (`demographic_parity` today), so 2 analyses → 1 cell per
    attribute with `decision_count >= 2`.
    """
    token = await _register_and_token(client, unique_email)
    headers = {"Authorization": f"Bearer {token}"}

    payload = _analyze_payload()
    await client.post("/api/v1/recruitment/analyze", json=payload, headers=headers)
    await client.post("/api/v1/recruitment/analyze", json=payload, headers=headers)

    resp = await client.get("/api/v1/audits/fairness", headers=headers)
    assert resp.status_code == 200, resp.text
    agg = resp.json()

    cells = agg["by_attribute_metric"]
    assert cells, "expected at least one (attribute, metric) cell"

    # Every cell should be well-formed.
    for cell in cells:
        assert {"attribute", "metric_name", "decision_count", "pass_count",
                "pass_rate", "avg_value", "threshold"} <= set(cell)
        assert cell["decision_count"] >= 2  # two analyses
        assert 0.0 <= cell["pass_rate"] <= 1.0
        assert cell["pass_count"] <= cell["decision_count"]

    # At least one gender cell carrying `demographic_parity`.
    gender_dp = [
        c for c in cells
        if c["attribute"] == "gender" and c["metric_name"] == "demographic_parity"
    ]
    assert gender_dp, "expected a (gender, demographic_parity) cell"

    # Cells are sorted by (attribute, metric_name).
    keys = [(c["attribute"], c["metric_name"]) for c in cells]
    assert keys == sorted(keys)


async def test_summary_aggregates_across_all_5_modules(client, unique_email):
    """Cross-module aggregation — one decision per module → summary
    histograms cover all 5."""
    token = await _register_and_token(client, unique_email)
    headers = {"Authorization": f"Bearer {token}"}

    # recruitment
    await client.post(
        "/api/v1/recruitment/analyze",
        json=_analyze_payload(),
        headers=headers,
    )
    # pricing
    await client.post(
        "/api/v1/pricing/optimize",
        json=_pricing_optimize_payload(),
        headers=headers,
    )
    # forecasting
    await client.post(
        "/api/v1/forecasting/forecast",
        json=_forecast_payload(),
        headers=headers,
    )
    # sustainability
    await client.post(
        "/api/v1/sustainability/score",
        json=_sustainability_score_payload(),
        headers=headers,
    )
    # chatbot
    await client.post(
        "/api/v1/chatbot/message",
        json=_chatbot_message_payload(),
        headers=headers,
    )

    resp = await client.get("/api/v1/audits/summary", headers=headers)
    assert resp.status_code == 200
    summary = resp.json()
    assert summary["total_decisions"] >= 5

    by_module = {row["module"]: row["count"] for row in summary["by_module"]}
    # Every module must have at least one decision in the histogram.
    assert by_module.get("recruitment", 0) >= 1
    assert by_module.get("pricing", 0) >= 1
    assert by_module.get("forecasting", 0) >= 1
    assert by_module.get("sustainability", 0) >= 1
    assert by_module.get("chatbot", 0) >= 1
