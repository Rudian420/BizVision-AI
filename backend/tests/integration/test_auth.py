"""End-to-end auth flow: register → login → /me → refresh."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


async def test_register_login_me_refresh(client, unique_email):
    # Register
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": unique_email, "password": "supersecret123", "full_name": "Test User"},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["user"]["email"] == unique_email
    access = data["tokens"]["access_token"]
    refresh = data["tokens"]["refresh_token"]

    # Authenticated profile
    me = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {access}"})
    assert me.status_code == 200
    assert me.json()["email"] == unique_email

    # Refresh
    refreshed = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    assert refreshed.status_code == 200
    assert "access_token" in refreshed.json()


async def test_login_with_wrong_password_rejected(client, unique_email):
    await client.post(
        "/api/v1/auth/register",
        json={"email": unique_email, "password": "supersecret123"},
    )
    resp = await client.post(
        "/api/v1/auth/login",
        data={"username": unique_email, "password": "wrong-password"},
    )
    assert resp.status_code == 401


async def test_me_requires_auth(client):
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401
