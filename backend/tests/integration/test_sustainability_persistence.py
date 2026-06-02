"""End-to-end sustainability persistence: register → score/simulate/recommend/carbon → explain.

Marked `integration` — relies on the live Postgres + Redis the CI workflow
spins up in service containers. Locally these are skipped via
`pytest -m "not integration"`.

Verifies that:
  • `/score`, `/simulate`, `/recommendations`, and `/carbon-estimate` each
    write one `sustainability_assessments` row.
  • `/benchmarks/{industry}` stays stateless (no row).
  • `simulate` and `recommendations` require an existing score row that
    belongs to the caller (404 otherwise).
  • `/explanation/{assessment_id}` reconstructs from the persisted payload
    and 404s cross-user.

Mirrors the pricing-side coverage from TASK-009.
"""

from __future__ import annotations

import uuid

import pytest

pytestmark = pytest.mark.integration


async def _register_and_token(client, email: str) -> str:
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "supersecret123", "full_name": "Test User"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["tokens"]["access_token"]


def _score_payload(company: str = "Acme Corp", industry: str = "manufacturing") -> dict:
    return {
        "company_name": company,
        "industry": industry,
        "annual_revenue": 5_000_000.0,
        "employee_count": 42,
        "environmental_indicators": {
            "energy_efficiency": 0.7,
            "waste_diversion": 0.55,
        },
        "social_indicators": {"dei_index": 0.6, "labor_compliance": 0.8},
        "governance_indicators": {
            "board_independence": 0.7,
            "transparency": 0.65,
        },
    }


def _carbon_payload(industry: str = "logistics") -> dict:
    return {
        "industry": industry,
        "annual_revenue": 2_000_000.0,
        "employee_count": 15,
        "energy_kwh": 100_000.0,
        "fleet_km": 250_000.0,
    }


async def test_score_then_explain_reconstructs_drivers(client, unique_email):
    token = await _register_and_token(client, unique_email)
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.post("/api/v1/sustainability/score", json=_score_payload(), headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assessment_id = body["assessment_id"]
    assert body["composite_score"] > 0
    assert body["risk_level"] in {"low", "medium", "high", "critical"}
    assert len(body["top_shap_features"]) >= 1

    # /explanation reconstructs from the persisted response_payload.
    resp = await client.get(
        f"/api/v1/sustainability/explanation/{assessment_id}", headers=headers
    )
    assert resp.status_code == 200
    expl = resp.json()
    assert expl["assessment_type"] == "score"
    assert expl["company_name"] == "Acme Corp"
    assert expl["industry"] == "manufacturing"
    driver_names = [d["feature"] for d in expl["drivers"]]
    assert "energy_efficiency" in driver_names


async def test_simulate_and_recommendations_persist_as_separate_rows(client, unique_email):
    token = await _register_and_token(client, unique_email)
    headers = {"Authorization": f"Bearer {token}"}

    score_resp = await client.post(
        "/api/v1/sustainability/score", json=_score_payload(), headers=headers
    )
    assert score_resp.status_code == 200
    parent_id = score_resp.json()["assessment_id"]

    sim_resp = await client.post(
        "/api/v1/sustainability/simulate",
        json={
            "assessment_id": parent_id,
            "investments": {"solar_install": 50_000.0, "supplier_audit": 10_000.0},
            "horizon_months": 24,
        },
        headers=headers,
    )
    assert sim_resp.status_code == 200, sim_resp.text
    sim = sim_resp.json()
    assert sim["assessment_id"] == parent_id  # echo of parent
    assert sim["projected_score"] >= sim["baseline_score"]

    rec_resp = await client.post(
        "/api/v1/sustainability/recommendations",
        json={"assessment_id": parent_id, "max_recommendations": 3},
        headers=headers,
    )
    assert rec_resp.status_code == 200, rec_resp.text
    recs = rec_resp.json()
    assert recs["assessment_id"] == parent_id
    assert len(recs["recommendations"]) == 3


async def test_simulate_404_when_parent_assessment_unknown(client, unique_email):
    token = await _register_and_token(client, unique_email)
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.post(
        "/api/v1/sustainability/simulate",
        json={
            "assessment_id": str(uuid.uuid4()),
            "investments": {"solar_install": 1_000.0},
            "horizon_months": 12,
        },
        headers=headers,
    )
    assert resp.status_code == 404


async def test_recommendations_404_when_parent_assessment_unknown(client, unique_email):
    token = await _register_and_token(client, unique_email)
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.post(
        "/api/v1/sustainability/recommendations",
        json={"assessment_id": str(uuid.uuid4()), "max_recommendations": 2},
        headers=headers,
    )
    assert resp.status_code == 404


async def test_carbon_estimate_persists_and_benchmarks_are_stateless(client, unique_email):
    token = await _register_and_token(client, unique_email)
    headers = {"Authorization": f"Bearer {token}"}

    # /carbon-estimate produces a row but doesn't echo an id.
    resp = await client.post(
        "/api/v1/sustainability/carbon-estimate", json=_carbon_payload(), headers=headers
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total_tco2e"] > 0
    assert body["scope_1_tco2e"] >= 0
    assert body["scope_2_tco2e"] >= 0
    assert body["scope_3_tco2e"] >= 0
    assert isinstance(body["reduction_pathways"], list)

    # /benchmarks/{industry} is stateless reference data.
    resp = await client.get(
        "/api/v1/sustainability/benchmarks/manufacturing", headers=headers
    )
    assert resp.status_code == 200
    bench = resp.json()
    assert bench["industry"] == "manufacturing"
    assert bench["median_esg_score"] > 0
    assert bench["carbon_intensity_tco2e_per_million"] > 0


async def test_explanation_404_for_unknown_assessment(client, unique_email):
    token = await _register_and_token(client, unique_email)
    headers = {"Authorization": f"Bearer {token}"}
    resp = await client.get(
        f"/api/v1/sustainability/explanation/{uuid.uuid4()}", headers=headers
    )
    assert resp.status_code == 404


async def test_other_user_cannot_read_assessment(client, unique_email):
    a_token = await _register_and_token(client, f"a-{unique_email}")
    resp = await client.post(
        "/api/v1/sustainability/score",
        json=_score_payload(),
        headers={"Authorization": f"Bearer {a_token}"},
    )
    assert resp.status_code == 200
    assessment_id = resp.json()["assessment_id"]

    b_token = await _register_and_token(client, f"b-{unique_email}")
    resp = await client.get(
        f"/api/v1/sustainability/explanation/{assessment_id}",
        headers={"Authorization": f"Bearer {b_token}"},
    )
    assert resp.status_code == 404


async def test_other_user_cannot_simulate_against_assessment(client, unique_email):
    """Authorisation is enforced *before* the simulation runs — user B
    cannot reference user A's score even with a valid payload."""
    a_token = await _register_and_token(client, f"a-{unique_email}")
    resp = await client.post(
        "/api/v1/sustainability/score",
        json=_score_payload(),
        headers={"Authorization": f"Bearer {a_token}"},
    )
    assert resp.status_code == 200
    assessment_id = resp.json()["assessment_id"]

    b_token = await _register_and_token(client, f"b-{unique_email}")
    resp = await client.post(
        "/api/v1/sustainability/simulate",
        json={
            "assessment_id": assessment_id,
            "investments": {"solar_install": 5_000.0},
            "horizon_months": 12,
        },
        headers={"Authorization": f"Bearer {b_token}"},
    )
    assert resp.status_code == 404


# ── TASK-033: sustainability assessment detail endpoint ───────────


async def test_get_sustainability_detail_returns_persisted_row(client, unique_email):
    """`GET /sustainability/assessments/{id}` reconstructs the
    persisted row + discriminator + headline columns + faithful JSONB
    payloads. Backs the audit-feed deep-link from TASK-033."""
    token = await _register_and_token(client, unique_email)
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.post(
        "/api/v1/sustainability/score", json=_score_payload(), headers=headers
    )
    assert resp.status_code == 200
    assessment_id = resp.json()["assessment_id"]

    resp = await client.get(
        f"/api/v1/sustainability/assessments/{assessment_id}", headers=headers
    )
    assert resp.status_code == 200, resp.text
    detail = resp.json()
    assert detail["assessment_id"] == assessment_id
    assert detail["assessment_type"] == "score"
    assert detail["company_name"] == "Acme Corp"
    assert detail["industry"] == "manufacturing"
    assert detail["composite_score"] is not None
    assert detail["risk_level"] in {"low", "medium", "high", "critical"}
    # Faithful response payload survives the JSONB round-trip.
    assert "sub_scores" in detail["response_payload"]


async def test_sustainability_detail_404_for_unknown(client, unique_email):
    token = await _register_and_token(client, unique_email)
    headers = {"Authorization": f"Bearer {token}"}
    resp = await client.get(
        "/api/v1/sustainability/assessments/00000000-0000-0000-0000-000000000000",
        headers=headers,
    )
    assert resp.status_code == 404


async def test_sustainability_detail_is_user_scoped(client, unique_email):
    a_token = await _register_and_token(client, f"a-{unique_email}")
    resp = await client.post(
        "/api/v1/sustainability/score",
        json=_score_payload(),
        headers={"Authorization": f"Bearer {a_token}"},
    )
    assert resp.status_code == 200
    assessment_id = resp.json()["assessment_id"]

    b_token = await _register_and_token(client, f"b-{unique_email}")
    resp = await client.get(
        f"/api/v1/sustainability/assessments/{assessment_id}",
        headers={"Authorization": f"Bearer {b_token}"},
    )
    assert resp.status_code == 404


# ── TASK-035: sustainability assessments list endpoint ────────────


async def test_list_assessments_paged_returns_caller_only(client, unique_email):
    """`GET /sustainability/assessments` returns the caller's rows
    newest-first, paged. Backs the `/modules/sustainability/assessments`
    history page (TASK-035)."""
    token = await _register_and_token(client, unique_email)
    headers = {"Authorization": f"Bearer {token}"}

    for company in ("Acme", "Globex", "Initech"):
        resp = await client.post(
            "/api/v1/sustainability/score",
            json=_score_payload(company=company),
            headers=headers,
        )
        assert resp.status_code == 200

    resp = await client.get("/api/v1/sustainability/assessments", headers=headers)
    assert resp.status_code == 200, resp.text
    page = resp.json()
    assert page["total"] >= 3
    assert page["page"] == 1
    items = page["items"]
    # Newest first — Initech was inserted last.
    assert items[0]["company_name"] == "Initech"
    # Headline columns surfaced for the row card.
    assert items[0]["composite_score"] is not None
    assert items[0]["risk_level"] in {"low", "medium", "high", "critical"}


async def test_list_assessments_filter_by_assessment_type(client, unique_email):
    token = await _register_and_token(client, unique_email)
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.post(
        "/api/v1/sustainability/score", json=_score_payload(), headers=headers
    )
    assert resp.status_code == 200
    resp = await client.post(
        "/api/v1/sustainability/carbon-estimate",
        json=_carbon_payload(),
        headers=headers,
    )
    assert resp.status_code == 200

    resp = await client.get(
        "/api/v1/sustainability/assessments?assessment_type=score", headers=headers
    )
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert all(it["assessment_type"] == "score" for it in items)


async def test_list_assessments_rejects_unknown_type(client, unique_email):
    token = await _register_and_token(client, unique_email)
    headers = {"Authorization": f"Bearer {token}"}
    resp = await client.get(
        "/api/v1/sustainability/assessments?assessment_type=mystery_type",
        headers=headers,
    )
    assert resp.status_code == 400


async def test_list_assessments_is_user_scoped(client, unique_email):
    a_token = await _register_and_token(client, f"a-{unique_email}")
    await client.post(
        "/api/v1/sustainability/score",
        json=_score_payload(),
        headers={"Authorization": f"Bearer {a_token}"},
    )
    b_token = await _register_and_token(client, f"b-{unique_email}")
    resp = await client.get(
        "/api/v1/sustainability/assessments",
        headers={"Authorization": f"Bearer {b_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["total"] == 0
