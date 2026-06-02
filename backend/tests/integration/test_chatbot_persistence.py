"""End-to-end chatbot persistence: register → /message → list/get → executive-report.

Marked `integration` — relies on the live Postgres + Redis the CI workflow
spins up in service containers. Locally these are skipped via
`pytest -m "not integration"`.

Verifies that:
  • `POST /chatbot/message` creates a conversation + 2 messages
    (user + assistant) on first call; subsequent calls referencing the
    same `conversation_id` append two more.
  • `GET /chatbot/conversations` lists the caller's threads, paged.
  • `GET /chatbot/conversations/{id}` returns the full turn sequence
    in `position` order.
  • `POST /chatbot/executive-report` persists one
    `chatbot_executive_reports` row per call.
  • Cross-user reads return 404.

Mirrors the pricing / ESG / forecasting coverage; this one exercises
the rich relational pattern (ADR-027) rather than the polymorphic
discriminator pattern.
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


def _message_payload(
    content: str = "What pricing strategy should I use for Q3?",
    conversation_id: str | None = None,
    modules: list[str] | None = None,
) -> dict:
    payload: dict = {
        "content": content,
        "include_modules": modules or ["pricing", "forecasting"],
    }
    if conversation_id is not None:
        payload["conversation_id"] = conversation_id
    return payload


async def test_first_message_creates_conversation_and_two_turns(client, unique_email):
    token = await _register_and_token(client, unique_email)
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.post(
        "/api/v1/chatbot/message", json=_message_payload(), headers=headers
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    conv_id = body["conversation_id"]
    assert body["message_id"]
    assert body["tokens_used"] > 0
    assert any(s["module"] == "pricing" for s in body["sources"])

    # /conversations/{id} returns both turns in position order.
    resp = await client.get(
        f"/api/v1/chatbot/conversations/{conv_id}", headers=headers
    )
    assert resp.status_code == 200
    detail = resp.json()
    roles = [t["role"] for t in detail["turns"]]
    assert roles == ["user", "assistant"]
    assert detail["turns"][0]["content"].startswith("What pricing strategy")


async def test_second_message_with_conversation_id_appends_turns(client, unique_email):
    token = await _register_and_token(client, unique_email)
    headers = {"Authorization": f"Bearer {token}"}

    first = await client.post(
        "/api/v1/chatbot/message",
        json=_message_payload("First question?"),
        headers=headers,
    )
    assert first.status_code == 200
    conv_id = first.json()["conversation_id"]

    second = await client.post(
        "/api/v1/chatbot/message",
        json=_message_payload(
            "Second question?", conversation_id=conv_id, modules=["sustainability"]
        ),
        headers=headers,
    )
    assert second.status_code == 200
    assert second.json()["conversation_id"] == conv_id

    detail = await client.get(
        f"/api/v1/chatbot/conversations/{conv_id}", headers=headers
    )
    assert detail.status_code == 200
    turns = detail.json()["turns"]
    assert len(turns) == 4
    assert [t["role"] for t in turns] == [
        "user",
        "assistant",
        "user",
        "assistant",
    ]


async def test_list_conversations_returns_caller_threads_only(client, unique_email):
    a_token = await _register_and_token(client, f"a-{unique_email}")
    a_headers = {"Authorization": f"Bearer {a_token}"}
    await client.post(
        "/api/v1/chatbot/message",
        json=_message_payload("A's first thread"),
        headers=a_headers,
    )
    await client.post(
        "/api/v1/chatbot/message",
        json=_message_payload("A's second thread"),
        headers=a_headers,
    )

    b_token = await _register_and_token(client, f"b-{unique_email}")
    b_headers = {"Authorization": f"Bearer {b_token}"}
    resp = await client.get("/api/v1/chatbot/conversations", headers=b_headers)
    assert resp.status_code == 200
    assert resp.json()["total"] == 0

    resp = await client.get("/api/v1/chatbot/conversations", headers=a_headers)
    assert resp.json()["total"] == 2
    titles = [c["title"] for c in resp.json()["items"]]
    assert any("A's first thread" in t or "A's second thread" in t for t in titles)


async def test_other_user_cannot_read_conversation(client, unique_email):
    a_token = await _register_and_token(client, f"a-{unique_email}")
    a_headers = {"Authorization": f"Bearer {a_token}"}
    resp = await client.post(
        "/api/v1/chatbot/message", json=_message_payload(), headers=a_headers
    )
    assert resp.status_code == 200
    conv_id = resp.json()["conversation_id"]

    b_token = await _register_and_token(client, f"b-{unique_email}")
    b_headers = {"Authorization": f"Bearer {b_token}"}
    resp = await client.get(
        f"/api/v1/chatbot/conversations/{conv_id}", headers=b_headers
    )
    assert resp.status_code == 404


async def test_get_conversation_404_for_unknown(client, unique_email):
    token = await _register_and_token(client, unique_email)
    headers = {"Authorization": f"Bearer {token}"}
    resp = await client.get(
        f"/api/v1/chatbot/conversations/{uuid.uuid4()}", headers=headers
    )
    assert resp.status_code == 404


async def test_send_message_404_when_conversation_id_unknown(client, unique_email):
    token = await _register_and_token(client, unique_email)
    headers = {"Authorization": f"Bearer {token}"}
    resp = await client.post(
        "/api/v1/chatbot/message",
        json=_message_payload(
            "Continuing nonexistent thread", conversation_id=str(uuid.uuid4())
        ),
        headers=headers,
    )
    assert resp.status_code == 404


async def test_executive_report_persists_per_call(client, unique_email):
    token = await _register_and_token(client, unique_email)
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "title": "Q3 Executive Intelligence Report",
        "include_modules": ["recruitment", "pricing", "forecasting", "sustainability"],
        "period_label": "Q3 2026",
    }
    resp = await client.post(
        "/api/v1/chatbot/executive-report", json=payload, headers=headers
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["title"] == "Q3 Executive Intelligence Report"
    assert len(body["sections"]) == 4
    assert len(body["strategic_recommendations"]) >= 1

    # A second call produces a separate report row (independent of conversations).
    resp = await client.post(
        "/api/v1/chatbot/executive-report", json=payload, headers=headers
    )
    assert resp.status_code == 200
    assert resp.json()["report_id"] != body["report_id"]


async def test_modules_in_scope_accumulates_across_turns(client, unique_email):
    """`conversation.modules_in_scope` is the union of all turn `include_modules`."""
    token = await _register_and_token(client, unique_email)
    headers = {"Authorization": f"Bearer {token}"}

    first = await client.post(
        "/api/v1/chatbot/message",
        json=_message_payload("First — pricing only", modules=["pricing"]),
        headers=headers,
    )
    assert first.status_code == 200
    conv_id = first.json()["conversation_id"]

    await client.post(
        "/api/v1/chatbot/message",
        json=_message_payload(
            "Second — pivot to sustainability",
            conversation_id=conv_id,
            modules=["sustainability"],
        ),
        headers=headers,
    )

    resp = await client.get("/api/v1/chatbot/conversations", headers=headers)
    assert resp.status_code == 200
    item = next(c for c in resp.json()["items"] if c["conversation_id"] == conv_id)
    assert set(item["modules_in_scope"]) == {"pricing", "sustainability"}
    assert item["message_count"] == 4


# ── TASK-034: chatbot message + executive-report detail endpoints ─


async def test_get_chatbot_message_resolves_to_conversation(client, unique_email):
    """`GET /chatbot/messages/{id}` returns the message + its parent
    conversation_id so the audit-feed deep-link can navigate the user
    to the right conversation surface."""
    token = await _register_and_token(client, unique_email)
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.post(
        "/api/v1/chatbot/message", json=_message_payload(), headers=headers
    )
    assert resp.status_code == 200
    body = resp.json()
    message_id = body["message_id"]
    conversation_id = body["conversation_id"]

    resp = await client.get(
        f"/api/v1/chatbot/messages/{message_id}", headers=headers
    )
    assert resp.status_code == 200, resp.text
    detail = resp.json()
    assert detail["message_id"] == message_id
    assert detail["conversation_id"] == conversation_id
    assert detail["role"] == "assistant"
    assert detail["position"] == 1  # user turn was position 0
    assert "conversation_title" in detail


async def test_chatbot_message_detail_404_for_unknown(client, unique_email):
    token = await _register_and_token(client, unique_email)
    headers = {"Authorization": f"Bearer {token}"}
    resp = await client.get(
        "/api/v1/chatbot/messages/00000000-0000-0000-0000-000000000000",
        headers=headers,
    )
    assert resp.status_code == 404


async def test_chatbot_message_detail_is_user_scoped(client, unique_email):
    """User B must get 404 on user A's message id — cross-user
    isolation is enforced via the conversation's user_id."""
    a_token = await _register_and_token(client, f"a-{unique_email}")
    resp = await client.post(
        "/api/v1/chatbot/message",
        json=_message_payload(),
        headers={"Authorization": f"Bearer {a_token}"},
    )
    assert resp.status_code == 200
    message_id = resp.json()["message_id"]

    b_token = await _register_and_token(client, f"b-{unique_email}")
    resp = await client.get(
        f"/api/v1/chatbot/messages/{message_id}",
        headers={"Authorization": f"Bearer {b_token}"},
    )
    assert resp.status_code == 404


async def test_get_executive_report_detail_returns_persisted_row(client, unique_email):
    """`GET /chatbot/executive-reports/{id}` reconstructs the persisted
    row with the response_payload + modules_included + model_version."""
    token = await _register_and_token(client, unique_email)
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.post(
        "/api/v1/chatbot/executive-report",
        json={
            "title": "Q3 Strategic Snapshot",
            "include_modules": ["pricing", "forecasting"],
            "period_label": "Q3",
        },
        headers=headers,
    )
    assert resp.status_code == 200
    report_id = resp.json()["report_id"]

    resp = await client.get(
        f"/api/v1/chatbot/executive-reports/{report_id}", headers=headers
    )
    assert resp.status_code == 200, resp.text
    detail = resp.json()
    assert detail["report_id"] == report_id
    assert detail["title"] == "Q3 Strategic Snapshot"
    assert detail["period_label"] == "Q3"
    assert detail["modules_included"] == ["pricing", "forecasting"]
    assert "sections" in detail["response_payload"]


async def test_executive_report_detail_404_for_unknown(client, unique_email):
    token = await _register_and_token(client, unique_email)
    headers = {"Authorization": f"Bearer {token}"}
    resp = await client.get(
        "/api/v1/chatbot/executive-reports/00000000-0000-0000-0000-000000000000",
        headers=headers,
    )
    assert resp.status_code == 404


async def test_executive_report_detail_is_user_scoped(client, unique_email):
    a_token = await _register_and_token(client, f"a-{unique_email}")
    resp = await client.post(
        "/api/v1/chatbot/executive-report",
        json={"title": "A's report", "include_modules": ["pricing"], "period_label": "Q3"},
        headers={"Authorization": f"Bearer {a_token}"},
    )
    assert resp.status_code == 200
    report_id = resp.json()["report_id"]

    b_token = await _register_and_token(client, f"b-{unique_email}")
    resp = await client.get(
        f"/api/v1/chatbot/executive-reports/{report_id}",
        headers={"Authorization": f"Bearer {b_token}"},
    )
    assert resp.status_code == 404
