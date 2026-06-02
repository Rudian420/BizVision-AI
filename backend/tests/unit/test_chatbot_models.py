"""Offline construction tests for the chatbot ORM models.

No DB connection — verifies the rich relational shape (conversation
parent + ordered message children + independent executive-report row).
Mirrors the recruitment-side construction tests; deliberately different
from the polymorphic-discriminator tests used by pricing / ESG /
forecasting (ADR-027 documents the split)."""

from __future__ import annotations

import uuid

from src.models.chatbot import (
    ChatbotConversation,
    ChatbotExecutiveReport,
    ChatbotMessage,
    ChatbotMessageRole,
)


def test_chatbot_message_role_values_match_api_string():
    assert ChatbotMessageRole.USER.value == "user"
    assert ChatbotMessageRole.ASSISTANT.value == "assistant"
    assert ChatbotMessageRole.SYSTEM.value == "system"


def test_conversation_construction_with_defaults():
    user_id = uuid.uuid4()
    conv = ChatbotConversation(
        user_id=user_id,
        title="What pricing strategy should I use for Q3?",
        modules_in_scope=["pricing", "forecasting"],
        message_count=2,
        total_tokens_used=128,
        model_version="chatbot-mock-0.1",
    )
    assert conv.user_id == user_id
    assert conv.title.startswith("What pricing strategy")
    assert conv.modules_in_scope == ["pricing", "forecasting"]
    assert conv.message_count == 2
    assert conv.total_tokens_used == 128


def test_message_construction_user_role():
    conv_id = uuid.uuid4()
    msg = ChatbotMessage(
        conversation_id=conv_id,
        role=ChatbotMessageRole.USER,
        position=0,
        content="What should I focus on this quarter?",
        include_modules=["pricing"],
        reasoning_trace=[],
        sources=[],
        tokens_used=0,
    )
    assert msg.role is ChatbotMessageRole.USER
    assert msg.position == 0
    assert msg.tokens_used == 0
    assert msg.reasoning_trace == []
    assert msg.sources == []


def test_message_construction_assistant_role_with_sources():
    conv_id = uuid.uuid4()
    msg = ChatbotMessage(
        conversation_id=conv_id,
        role=ChatbotMessageRole.ASSISTANT,
        position=1,
        content="Prioritise a modest price increase on inelastic SKUs.",
        include_modules=["pricing"],
        reasoning_trace=[
            "Pulled recent pricing + forecasting signals",
            "Checked ESG risk level",
            "Synthesised recommendation",
        ],
        sources=[
            {
                "module": "pricing",
                "reference_id": str(uuid.uuid4()),
                "summary": "Latest pricing analysis referenced.",
            }
        ],
        tokens_used=128,
    )
    assert msg.role is ChatbotMessageRole.ASSISTANT
    assert msg.position == 1
    assert len(msg.reasoning_trace) == 3
    assert msg.sources[0]["module"] == "pricing"
    assert msg.tokens_used == 128


def test_executive_report_construction():
    report = ChatbotExecutiveReport(
        user_id=uuid.uuid4(),
        title="Executive Intelligence Report",
        period_label="Q3 2026",
        modules_included=["recruitment", "pricing", "forecasting", "sustainability"],
        response_payload={
            "report_id": str(uuid.uuid4()),
            "sections": [{"heading": "Pricing Strategy", "body": "...", "highlights": []}],
            "strategic_recommendations": ["Raise price on inelastic SKUs by ~8%"],
            "key_risks": ["Demand elasticity uncertainty"],
        },
        model_version="chatbot-mock-0.1",
    )
    assert report.title == "Executive Intelligence Report"
    assert report.period_label == "Q3 2026"
    assert "pricing" in report.modules_included
    assert len(report.response_payload["sections"]) == 1
