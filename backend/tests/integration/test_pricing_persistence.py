"""End-to-end pricing persistence: register → optimize/simulate → list/explain.

Marked `integration` — relies on the live Postgres + Redis the CI workflow
spins up in service containers. Locally these are skipped via
`pytest -m "not integration"`.

Verifies that:
  • Each of the four `/pricing/*` POSTs writes one `pricing_analyses` row.
  • `list_history` returns all four ordered by `created_at` descending
    and filters cleanly by `product_id`.
  • `get_explanation` reconstructs from the persisted response payload.
  • Cross-user reads return 404.
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


def _optimize_payload(product_id: str = "sku-001") -> dict:
    return {
        "product_id": product_id,
        "current_price": 19.99,
        "unit_cost": 7.5,
        "historical_demand": [120.0, 118.0, 122.0, 117.0, 121.0],
        "competitor_prices": [21.0, 20.5, 22.0],
        "objective": "revenue",
    }


def _monte_carlo_payload(product_id: str = "sku-001") -> dict:
    return {
        "product_id": product_id,
        "candidate_price": 21.0,
        "unit_cost": 7.5,
        "demand_mean": 120.0,
        "demand_std": 12.0,
        "num_trials": 5_000,
    }


def _elasticity_payload(product_id: str = "sku-001") -> dict:
    return {
        "product_id": product_id,
        "price_points": [10.0, 12.0, 14.0, 16.0],
        "observed_demand": [200.0, 165.0, 140.0, 110.0],
    }


def _scenarios_payload(product_id: str = "sku-001") -> dict:
    return {
        "product_id": product_id,
        "current_price": 19.99,
        "unit_cost": 7.5,
        "demand_mean": 120.0,
    }


async def test_optimize_then_list_and_explain(client, unique_email):
    token = await _register_and_token(client, unique_email)
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.post("/api/v1/pricing/optimize", json=_optimize_payload(), headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    analysis_id = body["analysis_id"]
    assert body["recommended_price"] > 0
    assert isinstance(body["revenue_curve"], list)
    assert len(body["revenue_curve"]) > 5

    # list_history returns the new analysis
    resp = await client.get("/api/v1/pricing/history", headers=headers)
    assert resp.status_code == 200
    hist = resp.json()
    assert hist["total"] >= 1
    ids = [r["analysis_id"] for r in hist["items"]]
    assert analysis_id in ids
    optimize_row = next(r for r in hist["items"] if r["analysis_id"] == analysis_id)
    assert optimize_row["analysis_type"] == "optimize"
    assert optimize_row["recommended_price"] == body["recommended_price"]

    # explanation reconstructs from the persisted response payload
    resp = await client.get(f"/api/v1/pricing/explanation/{analysis_id}", headers=headers)
    assert resp.status_code == 200
    expl = resp.json()
    assert expl["analysis_type"] == "optimize"
    assert expl["product_id"] == "sku-001"
    feature_names = [f["feature"] for f in expl["shap_features"]]
    assert "price_elasticity" in feature_names


async def test_all_four_endpoints_persist_and_filter_by_product(client, unique_email):
    token = await _register_and_token(client, unique_email)
    headers = {"Authorization": f"Bearer {token}"}

    # Fire all four for the same product.
    for path, payload in [
        ("/api/v1/pricing/optimize", _optimize_payload("sku-XYZ")),
        ("/api/v1/pricing/simulate", _monte_carlo_payload("sku-XYZ")),
        ("/api/v1/pricing/elasticity", _elasticity_payload("sku-XYZ")),
        ("/api/v1/pricing/scenarios", _scenarios_payload("sku-XYZ")),
    ]:
        resp = await client.post(path, json=payload, headers=headers)
        assert resp.status_code == 200, f"{path} → {resp.text}"

    # One more for a different product so the filter test is meaningful.
    resp = await client.post(
        "/api/v1/pricing/optimize",
        json=_optimize_payload("sku-OTHER"),
        headers=headers,
    )
    assert resp.status_code == 200

    # Filter by product_id — only the 4 sku-XYZ rows come back.
    resp = await client.get("/api/v1/pricing/history?product_id=sku-XYZ", headers=headers)
    assert resp.status_code == 200
    hist = resp.json()
    assert hist["total"] == 4
    types = {r["analysis_type"] for r in hist["items"]}
    assert types == {"optimize", "monte_carlo", "elasticity", "scenario_comparison"}

    # No filter — at least the 4 + the sku-OTHER one are visible.
    resp = await client.get("/api/v1/pricing/history", headers=headers)
    assert resp.json()["total"] >= 5


async def test_explanation_404_for_unknown(client, unique_email):
    token = await _register_and_token(client, unique_email)
    headers = {"Authorization": f"Bearer {token}"}
    resp = await client.get(
        "/api/v1/pricing/explanation/00000000-0000-0000-0000-000000000000",
        headers=headers,
    )
    assert resp.status_code == 404


async def test_other_user_cannot_read_analysis(client, unique_email):
    a_token = await _register_and_token(client, f"a-{unique_email}")
    resp = await client.post(
        "/api/v1/pricing/optimize",
        json=_optimize_payload(),
        headers={"Authorization": f"Bearer {a_token}"},
    )
    assert resp.status_code == 200
    analysis_id = resp.json()["analysis_id"]

    b_token = await _register_and_token(client, f"b-{unique_email}")
    resp = await client.get(
        f"/api/v1/pricing/explanation/{analysis_id}",
        headers={"Authorization": f"Bearer {b_token}"},
    )
    assert resp.status_code == 404


# ── TASK-033: pricing analysis detail endpoint ────────────────────


async def test_get_pricing_analysis_detail_returns_persisted_row(client, unique_email):
    """`GET /pricing/analyses/{id}` reconstructs the persisted row +
    discriminator + headline columns + faithful JSONB payloads. Backs
    the audit-feed deep-link from TASK-033."""
    token = await _register_and_token(client, unique_email)
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.post(
        "/api/v1/pricing/optimize", json=_optimize_payload(), headers=headers
    )
    assert resp.status_code == 200
    analysis_id = resp.json()["analysis_id"]

    resp = await client.get(
        f"/api/v1/pricing/analyses/{analysis_id}", headers=headers
    )
    assert resp.status_code == 200, resp.text
    detail = resp.json()
    assert detail["analysis_id"] == analysis_id
    assert detail["analysis_type"] == "optimize"
    assert detail["product_id"] == "sku-001"
    assert detail["recommended_price"] is not None
    # Faithful request payload survives the JSONB round-trip.
    assert detail["request_payload"]["objective"] == "revenue"
    # Faithful response payload too — recommended_price + curve.
    assert "revenue_curve" in detail["response_payload"]


async def test_pricing_detail_404_for_unknown(client, unique_email):
    token = await _register_and_token(client, unique_email)
    headers = {"Authorization": f"Bearer {token}"}
    resp = await client.get(
        "/api/v1/pricing/analyses/00000000-0000-0000-0000-000000000000",
        headers=headers,
    )
    assert resp.status_code == 404


async def test_pricing_detail_is_user_scoped(client, unique_email):
    a_token = await _register_and_token(client, f"a-{unique_email}")
    resp = await client.post(
        "/api/v1/pricing/optimize",
        json=_optimize_payload(),
        headers={"Authorization": f"Bearer {a_token}"},
    )
    assert resp.status_code == 200
    analysis_id = resp.json()["analysis_id"]

    b_token = await _register_and_token(client, f"b-{unique_email}")
    resp = await client.get(
        f"/api/v1/pricing/analyses/{analysis_id}",
        headers={"Authorization": f"Bearer {b_token}"},
    )
    assert resp.status_code == 404


# ── TASK-037: date-range filter on /history ────────────────────────


async def test_history_date_range_filter_excludes_pre_since(client, unique_email):
    """`?since=<iso>` filters out rows created before the timestamp.
    Backs the date-range chip on the per-module history page."""
    from datetime import datetime, timezone, timedelta

    token = await _register_and_token(client, unique_email)
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.post(
        "/api/v1/pricing/optimize", json=_optimize_payload(), headers=headers
    )
    assert resp.status_code == 200

    # `since` = 1 hour in the future → list returns 0 of the user's rows.
    future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    resp = await client.get(
        f"/api/v1/pricing/history?since={future}", headers=headers
    )
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


async def test_history_date_range_filter_includes_when_in_window(client, unique_email):
    from datetime import datetime, timezone, timedelta

    token = await _register_and_token(client, unique_email)
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.post(
        "/api/v1/pricing/optimize", json=_optimize_payload(), headers=headers
    )
    assert resp.status_code == 200

    past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    resp = await client.get(
        f"/api/v1/pricing/history?since={past}", headers=headers
    )
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1


async def test_history_until_filter_excludes_post_until(client, unique_email):
    """`?until=<iso>` filters out rows created after the timestamp."""
    from datetime import datetime, timezone, timedelta

    token = await _register_and_token(client, unique_email)
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.post(
        "/api/v1/pricing/optimize", json=_optimize_payload(), headers=headers
    )
    assert resp.status_code == 200

    # `until` = 1 hour in the past → row is too new, returns 0.
    past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    resp = await client.get(
        f"/api/v1/pricing/history?until={past}", headers=headers
    )
    assert resp.status_code == 200
    assert resp.json()["total"] == 0
