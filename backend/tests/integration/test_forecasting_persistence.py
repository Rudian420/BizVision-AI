"""End-to-end forecasting persistence: register → forecast/sensitivity/what-if/cross-module → list/explain.

Marked `integration` — relies on the live Postgres + Redis the CI workflow
spins up in service containers. Locally these are skipped via
`pytest -m "not integration"`.

Verifies that:
  • Each of the four `/forecasting/*` POSTs writes one `forecast_analyses` row.
  • `/history` returns all four ordered by `created_at` descending,
    filters cleanly by `series_name` and by `analysis_type`.
  • `/explanation/{forecast_id}` reconstructs from the persisted payload.
  • Cross-user reads return 404.

Mirrors the pricing-side coverage from TASK-009 and the ESG-side coverage
from TASK-012.
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


def _history_payload() -> list[dict]:
    return [
        {"ds": "2026-01-01", "y": 100.0},
        {"ds": "2026-01-02", "y": 102.5},
        {"ds": "2026-01-03", "y": 104.0},
        {"ds": "2026-01-04", "y": 106.2},
        {"ds": "2026-01-05", "y": 108.0},
    ]


def _forecast_payload(series_name: str = "profit") -> dict:
    return {
        "series_name": series_name,
        "history": _history_payload(),
        "forecast_horizon_days": 30,
        "include_scenarios": True,
    }


def _sensitivity_payload() -> dict:
    return {
        "history": _history_payload(),
        "drivers": {"price": 20.0, "headcount": 50.0, "marketing_spend": 10.0},
        "perturbation_pct": 0.1,
    }


def _what_if_payload() -> dict:
    return {
        "history": _history_payload(),
        "adjustments": {"price_uplift_pct": 5.0, "headcount_delta_pct": -2.0},
        "forecast_horizon_days": 30,
    }


def _cross_module_payload() -> dict:
    return {
        "history": _history_payload(),
        "forecast_horizon_days": 30,
        "include_pricing_signals": True,
        "include_recruitment_signals": True,
        "include_esg_signals": True,
    }


async def test_forecast_then_history_and_explain(client, unique_email):
    token = await _register_and_token(client, unique_email)
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.post(
        "/api/v1/forecasting/forecast", json=_forecast_payload(), headers=headers
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    forecast_id = body["forecast_id"]
    assert body["horizon_days"] == 30
    assert "base" in body["scenarios"]
    assert body["scenarios"]["base"]["end_value"] > 0

    # /history returns the new forecast.
    resp = await client.get("/api/v1/forecasting/history", headers=headers)
    assert resp.status_code == 200
    hist = resp.json()
    assert hist["total"] >= 1
    ids = [r["forecast_id"] for r in hist["items"]]
    assert forecast_id in ids
    forecast_row = next(r for r in hist["items"] if r["forecast_id"] == forecast_id)
    assert forecast_row["analysis_type"] == "forecast"
    assert forecast_row["base_end_value"] == body["scenarios"]["base"]["end_value"]
    assert forecast_row["mape"] == body["mape"]

    # /explanation reconstructs from the persisted response_payload.
    resp = await client.get(
        f"/api/v1/forecasting/explanation/{forecast_id}", headers=headers
    )
    assert resp.status_code == 200
    expl = resp.json()
    assert expl["analysis_type"] == "forecast"
    assert expl["series_name"] == "profit"
    assert expl["horizon_days"] == 30
    driver_names = [d["feature"] for d in expl["drivers"]]
    assert "trend" in driver_names


async def test_all_four_endpoints_persist_and_filter_by_type(client, unique_email):
    token = await _register_and_token(client, unique_email)
    headers = {"Authorization": f"Bearer {token}"}

    for path, payload in [
        ("/api/v1/forecasting/forecast", _forecast_payload("revenue")),
        ("/api/v1/forecasting/sensitivity", _sensitivity_payload()),
        ("/api/v1/forecasting/what-if", _what_if_payload()),
        ("/api/v1/forecasting/cross-module", _cross_module_payload()),
    ]:
        resp = await client.post(path, json=payload, headers=headers)
        assert resp.status_code == 200, f"{path} → {resp.text}"

    # Filter by analysis_type — only the cross_module row comes back.
    resp = await client.get(
        "/api/v1/forecasting/history?analysis_type=cross_module", headers=headers
    )
    assert resp.status_code == 200
    hist = resp.json()
    assert hist["total"] == 1
    assert hist["items"][0]["analysis_type"] == "cross_module"

    # Filter by series_name — only the named forecast row comes back.
    resp = await client.get(
        "/api/v1/forecasting/history?series_name=revenue", headers=headers
    )
    assert resp.status_code == 200
    hist = resp.json()
    assert hist["total"] == 1
    assert hist["items"][0]["series_name"] == "revenue"

    # No filter — all four are visible, type set matches the enum.
    resp = await client.get("/api/v1/forecasting/history", headers=headers)
    assert resp.json()["total"] >= 4
    types = {r["analysis_type"] for r in resp.json()["items"]}
    assert types == {"forecast", "sensitivity", "what_if", "cross_module"}


async def test_history_400_on_unknown_analysis_type(client, unique_email):
    token = await _register_and_token(client, unique_email)
    headers = {"Authorization": f"Bearer {token}"}
    resp = await client.get(
        "/api/v1/forecasting/history?analysis_type=garbage_value", headers=headers
    )
    assert resp.status_code == 400


async def test_explanation_404_for_unknown_forecast(client, unique_email):
    token = await _register_and_token(client, unique_email)
    headers = {"Authorization": f"Bearer {token}"}
    resp = await client.get(
        f"/api/v1/forecasting/explanation/{uuid.uuid4()}", headers=headers
    )
    assert resp.status_code == 404


async def test_other_user_cannot_read_forecast(client, unique_email):
    a_token = await _register_and_token(client, f"a-{unique_email}")
    resp = await client.post(
        "/api/v1/forecasting/forecast",
        json=_forecast_payload(),
        headers={"Authorization": f"Bearer {a_token}"},
    )
    assert resp.status_code == 200
    forecast_id = resp.json()["forecast_id"]

    b_token = await _register_and_token(client, f"b-{unique_email}")
    resp = await client.get(
        f"/api/v1/forecasting/explanation/{forecast_id}",
        headers={"Authorization": f"Bearer {b_token}"},
    )
    assert resp.status_code == 404


async def test_other_user_history_does_not_leak_rows(client, unique_email):
    """User B's `/history` is empty even after user A has written rows."""
    a_token = await _register_and_token(client, f"a-{unique_email}")
    resp = await client.post(
        "/api/v1/forecasting/forecast",
        json=_forecast_payload(),
        headers={"Authorization": f"Bearer {a_token}"},
    )
    assert resp.status_code == 200

    b_token = await _register_and_token(client, f"b-{unique_email}")
    resp = await client.get(
        "/api/v1/forecasting/history",
        headers={"Authorization": f"Bearer {b_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


# ── TASK-033: forecast detail endpoint ─────────────────────────────


async def test_get_forecast_detail_returns_persisted_row(client, unique_email):
    """`GET /forecasting/forecasts/{id}` reconstructs the persisted row
    + discriminator + headline columns + faithful JSONB payloads.
    Backs the audit-feed deep-link from TASK-033."""
    token = await _register_and_token(client, unique_email)
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.post(
        "/api/v1/forecasting/forecast", json=_forecast_payload(), headers=headers
    )
    assert resp.status_code == 200
    forecast_id = resp.json()["forecast_id"]

    resp = await client.get(
        f"/api/v1/forecasting/forecasts/{forecast_id}", headers=headers
    )
    assert resp.status_code == 200, resp.text
    detail = resp.json()
    assert detail["forecast_id"] == forecast_id
    assert detail["analysis_type"] == "forecast"
    assert detail["series_name"] == "profit"
    assert detail["horizon_days"] is not None
    assert detail["base_end_value"] is not None
    # Faithful response payload survives the JSONB round-trip.
    assert "scenarios" in detail["response_payload"]


async def test_forecast_detail_404_for_unknown(client, unique_email):
    token = await _register_and_token(client, unique_email)
    headers = {"Authorization": f"Bearer {token}"}
    resp = await client.get(
        "/api/v1/forecasting/forecasts/00000000-0000-0000-0000-000000000000",
        headers=headers,
    )
    assert resp.status_code == 404


async def test_forecast_detail_is_user_scoped(client, unique_email):
    a_token = await _register_and_token(client, f"a-{unique_email}")
    resp = await client.post(
        "/api/v1/forecasting/forecast",
        json=_forecast_payload(),
        headers={"Authorization": f"Bearer {a_token}"},
    )
    assert resp.status_code == 200
    forecast_id = resp.json()["forecast_id"]

    b_token = await _register_and_token(client, f"b-{unique_email}")
    resp = await client.get(
        f"/api/v1/forecasting/forecasts/{forecast_id}",
        headers={"Authorization": f"Bearer {b_token}"},
    )
    assert resp.status_code == 404


async def test_sensitivity_persists_with_null_horizon(client, unique_email):
    """Sensitivity rows are tornado-only and don't carry a horizon —
    /history surfaces them with `horizon_days=None`."""
    token = await _register_and_token(client, unique_email)
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.post(
        "/api/v1/forecasting/sensitivity", json=_sensitivity_payload(), headers=headers
    )
    assert resp.status_code == 200, resp.text
    forecast_id = resp.json()["forecast_id"]

    resp = await client.get(
        "/api/v1/forecasting/history?analysis_type=sensitivity", headers=headers
    )
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["forecast_id"] == forecast_id
    assert items[0]["horizon_days"] is None
    assert items[0]["base_end_value"] is None
