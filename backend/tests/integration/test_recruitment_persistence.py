"""End-to-end persistence: register → analyze → list/explain/fairness.

Marked `integration` — relies on the live Postgres + Redis the CI workflow
spins up in service containers. Locally these are skipped via
`pytest -m "not integration"`.

Verifies that the full pipeline `POST /recruitment/analyze`
   → row in `recruitment_sessions`
   → rows in `candidate_scores` (full ranking, not just top-k)
   → rows in `fairness_audit_records` (one per protected attribute)
is wired correctly, and that the explanation + fairness GETs reconstruct
the API response from those rows.
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
                "Design and ship production ML systems with explainability "
                "and fairness in mind. Strong Python + MLOps required."
            ),
            "required_skills": ["python", "ml", "mlops"],
            "preferred_skills": ["pytorch", "kubernetes"],
            "experience_level": "senior",
        },
        "candidates": [
            {"candidate_id": f"cand-{i:03d}", "cv_text": "Experienced engineer."} for i in range(8)
        ],
        "anonymize_names": True,
        "protected_attributes": ["gender"],
        "top_k": 5,
        "ensemble_sbert_weight": 0.6,
    }


async def test_analyze_then_list_and_explain(client, unique_email):
    token = await _register_and_token(client, unique_email)
    headers = {"Authorization": f"Bearer {token}"}

    # ── analyze: must persist + return a session id ────────────────
    resp = await client.post(
        "/api/v1/recruitment/analyze", json=_analyze_payload(), headers=headers
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    session_id = body["session_id"]
    assert body["total_candidates"] == 8
    assert len(body["ranked_candidates"]) == 5
    top_candidate_id = body["ranked_candidates"][0]["candidate_id"]

    # ── list_sessions: must see the new session ────────────────────
    resp = await client.get("/api/v1/recruitment/sessions", headers=headers)
    assert resp.status_code == 200
    sessions = resp.json()
    assert sessions["total"] >= 1
    ids = [s["session_id"] for s in sessions["items"]]
    assert session_id in ids

    # ── get_shap_explanation: must reconstruct from DB ─────────────
    resp = await client.get(
        f"/api/v1/recruitment/explanation/{session_id}",
        params={"candidate_id": top_candidate_id},
        headers=headers,
    )
    assert resp.status_code == 200
    exp = resp.json()
    assert exp["candidate_id"] == top_candidate_id
    assert exp["shap_features"], "expected at least one SHAP feature persisted"

    # ── get_fairness_audit: must reconstruct from DB ───────────────
    resp = await client.get(f"/api/v1/recruitment/fairness/{session_id}", headers=headers)
    assert resp.status_code == 200
    audit = resp.json()
    assert "gender" in audit["protected_attributes"]


async def test_explanation_404_for_unknown_session(client, unique_email):
    token = await _register_and_token(client, unique_email)
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.get(
        "/api/v1/recruitment/explanation/00000000-0000-0000-0000-000000000000",
        params={"candidate_id": "cand-001"},
        headers=headers,
    )
    assert resp.status_code == 404


async def test_other_user_cannot_read_session(client, unique_email):
    # User A creates a session.
    a_token = await _register_and_token(client, f"a-{unique_email}")
    resp = await client.post(
        "/api/v1/recruitment/analyze",
        json=_analyze_payload(),
        headers={"Authorization": f"Bearer {a_token}"},
    )
    assert resp.status_code == 200
    session_id = resp.json()["session_id"]

    # User B (different email) must get 404 on the same session.
    b_token = await _register_and_token(client, f"b-{unique_email}")
    resp = await client.get(
        f"/api/v1/recruitment/fairness/{session_id}",
        headers={"Authorization": f"Bearer {b_token}"},
    )
    assert resp.status_code == 404


# ── TASK-032: session detail endpoint ─────────────────────────────


async def test_get_session_detail_returns_ranked_candidates(client, unique_email):
    """`GET /recruitment/sessions/{id}` reconstructs the persisted
    session + the full ranked-candidates list from the DB. Backs the
    audit-feed deep-link from TASK-032."""
    token = await _register_and_token(client, unique_email)
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.post(
        "/api/v1/recruitment/analyze", json=_analyze_payload(), headers=headers
    )
    assert resp.status_code == 200
    session_id = resp.json()["session_id"]

    resp = await client.get(
        f"/api/v1/recruitment/sessions/{session_id}", headers=headers
    )
    assert resp.status_code == 200, resp.text
    detail = resp.json()
    assert detail["session_id"] == session_id
    assert detail["job_title"] == "Senior ML Engineer"
    assert detail["total_candidates"] == 8
    # All 8 candidates are persisted (not just top-k) — the detail
    # endpoint surfaces them all in rank order.
    assert len(detail["ranked_candidates"]) == 8
    ranks = [c["rank"] for c in detail["ranked_candidates"]]
    assert ranks == sorted(ranks)
    assert ranks[0] == 1
    # SHAP attributions survive the round-trip from the persisted JSONB.
    top = detail["ranked_candidates"][0]
    assert top["top_shap_features"], "expected SHAP features on the #1 candidate"
    # TASK-050: LIME survives the round-trip too. The mock branch
    # writes 3 rule-style attributions per candidate (TASK-048's
    # `_mock_lime_attrs`) — those must echo back through
    # `get_session_detail` after the migration. Every candidate in
    # the persisted ranking gets the same 3-rule treatment, so the
    # invariant holds across the whole list.
    assert top["top_lime_features"], "expected LIME features on the #1 candidate"
    assert len(top["top_lime_features"]) == 3
    # Rule-style names contain a threshold expression (distinct from
    # SHAP's bare feature names).
    assert all(">" in f["feature_name"] for f in top["top_lime_features"])
    # All candidates (not just #1) have LIME persisted.
    assert all(
        len(c["top_lime_features"]) == 3 for c in detail["ranked_candidates"]
    )


async def test_get_session_detail_404_for_unknown_session(client, unique_email):
    token = await _register_and_token(client, unique_email)
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.get(
        "/api/v1/recruitment/sessions/00000000-0000-0000-0000-000000000000",
        headers=headers,
    )
    assert resp.status_code == 404


async def test_get_session_detail_is_user_scoped(client, unique_email):
    """User B must get 404 on user A's session detail — same posture
    as the existing fairness/explanation 404 isolation."""
    a_token = await _register_and_token(client, f"a-{unique_email}")
    resp = await client.post(
        "/api/v1/recruitment/analyze",
        json=_analyze_payload(),
        headers={"Authorization": f"Bearer {a_token}"},
    )
    assert resp.status_code == 200
    session_id = resp.json()["session_id"]

    b_token = await _register_and_token(client, f"b-{unique_email}")
    resp = await client.get(
        f"/api/v1/recruitment/sessions/{session_id}",
        headers={"Authorization": f"Bearer {b_token}"},
    )
    assert resp.status_code == 404
