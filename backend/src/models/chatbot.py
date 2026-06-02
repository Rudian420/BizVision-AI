"""
BizVision AI — Financial Advisory Chatbot Persistence Models

Unlike pricing / ESG / forecasting — which each shape one
discriminator-keyed table around four-or-five thin self-contained
analysis types — the chatbot is a **stateful, multi-turn**
conversation. A single conversation is a parent row with an ordered
sequence of messages (user + assistant), each carrying its own
reasoning trace + tool/source citations.

Schema:

    chatbot_conversations
      └── chatbot_messages       (one-to-many; ordered by `position`)

    chatbot_executive_reports    (independent — one row per
                                  /chatbot/executive-report invocation)

This is the **rich relational pattern** also used by recruitment
(`RecruitmentSession` + `CandidateScore` + `FairnessAuditRecord`),
deliberately distinct from the polymorphic discriminator pattern used
by pricing / ESG / forecasting. See ADR-027 for the rationale: chat has
*one* primary shape (multi-turn dialog) with *deep* child rows, the
inverse of pricing's *many* shapes with *shallow* per-call payloads.

Key columns:

  • `chatbot_conversations.title` — derived from the first user message;
    seeded as `"New conversation"` and updated on first send.
  • `chatbot_conversations.modules_in_scope` — JSONB array; the set
    of module contexts the user asked the AI to fold in across the
    whole conversation (union of per-message `include_modules`).
  • `chatbot_messages.role` — `"user" | "assistant" | "system"`.
  • `chatbot_messages.position` — 0-indexed monotonic per conversation;
    the unique constraint `(conversation_id, position)` makes ordering
    deterministic even under racing writes.
  • `chatbot_messages.reasoning_trace` + `sources` — JSONB arrays
    mirroring the API schema one-to-one.

WebSocket awareness: the WS path persists *both* the inbound user
message and the final assistant message at `complete`-event time, so a
reconnecting client can hydrate from `/chatbot/conversations/{id}`
without missing turns. Streamed token chunks are NOT persisted (they
reconstruct the final `content`, which is the row of record).
"""

from __future__ import annotations

import enum
import uuid
from typing import Any

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin, UUIDMixin


class ChatbotMessageRole(str, enum.Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


# ── 1. Conversation ─────────────────────────────────────────────────


class ChatbotConversation(UUIDMixin, TimestampMixin, Base):
    """One row per chatbot conversation (multi-turn)."""

    __tablename__ = "chatbot_conversations"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False, default="New conversation")

    # Union of module contexts requested across the conversation so
    # `/conversations` listings can surface "this thread touches pricing
    # + forecasting" without scanning every message.
    modules_in_scope: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)

    # Running counters — bumped on every persisted turn. Cheap to
    # update at write time, expensive to recompute on every list page.
    message_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_tokens_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Model provenance for the conversation — locked at create-time.
    # If a flag flip changes the model mid-conversation, a new row is
    # created (a fresh conversation), preserving audit clarity.
    model_version: Mapped[str] = mapped_column(String(100), nullable=False)

    messages: Mapped[list[ChatbotMessage]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="ChatbotMessage.position",
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ChatbotConversation {self.id} title={self.title!r} n={self.message_count}>"


# ── 2. Message ──────────────────────────────────────────────────────


class ChatbotMessage(UUIDMixin, TimestampMixin, Base):
    """One row per turn (user OR assistant) inside a conversation."""

    __tablename__ = "chatbot_messages"
    __table_args__ = (
        UniqueConstraint(
            "conversation_id", "position", name="uq_chatbot_messages_conv_position"
        ),
    )

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("chatbot_conversations.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    role: Mapped[ChatbotMessageRole] = mapped_column(
        SAEnum(ChatbotMessageRole, name="chatbot_message_role"),
        nullable=False,
        index=True,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Per-message provenance.
    include_modules: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    reasoning_trace: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    sources: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list, nullable=False)
    tokens_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    conversation: Mapped[ChatbotConversation] = relationship(back_populates="messages")


# ── 3. Executive report (independent of conversations) ──────────────


class ChatbotExecutiveReport(UUIDMixin, TimestampMixin, Base):
    """One row per `/chatbot/executive-report` invocation.

    Reports are not threaded — each call is a self-contained snapshot
    of the modules-in-scope at the time. We could fold them into the
    conversation table behind a discriminator, but the response shape
    (`sections` + `strategic_recommendations` + `key_risks`) is
    materially different from a chat turn, and querying *"give me the
    most recent quarterly executive report"* on its own table is
    materially faster.
    """

    __tablename__ = "chatbot_executive_reports"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    period_label: Mapped[str] = mapped_column(String(100), nullable=False)
    modules_included: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)

    # Faithful API payload — same posture as pricing/ESG/forecasting.
    response_payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, nullable=False
    )

    model_version: Mapped[str] = mapped_column(String(100), nullable=False)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ChatbotExecutiveReport {self.id} title={self.title!r}>"
