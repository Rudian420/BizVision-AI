"""Chatbot conversations — rich relational pattern.

Revision ID: 0005_chatbot_conversations
Revises: 0004_forecast_analysis
Create Date: 2026-05-30

Adds three new tables for TASK-014 (chatbot persistence):

  • `chatbot_conversations` — parent thread row, one per session.
  • `chatbot_messages` — ordered child rows (one per user/assistant turn);
       unique constraint on (conversation_id, position) makes the
       sequence deterministic under racing writes.
  • `chatbot_executive_reports` — independent of conversations; one row
       per `/chatbot/executive-report` call.

ADR-027 documents why chatbot uses the *rich relational* shape (same as
recruitment) rather than the polymorphic discriminator shape used by
pricing / ESG / forecasting.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0005_chatbot_conversations"
down_revision: str | None = "0004_forecast_analysis"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── enum for message roles ────────────────────────────────────
    message_role = postgresql.ENUM(
        "user",
        "assistant",
        "system",
        name="chatbot_message_role",
        create_type=False,
    )
    message_role.create(op.get_bind(), checkfirst=True)

    # ── conversations ─────────────────────────────────────────────
    op.create_table(
        "chatbot_conversations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "title",
            sa.String(length=200),
            nullable=False,
            server_default="New conversation",
        ),
        sa.Column(
            "modules_in_scope",
            postgresql.JSONB(),
            nullable=False,
            server_default="[]",
        ),
        sa.Column("message_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "total_tokens_used", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column("model_version", sa.String(length=100), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_chatbot_conversations_user_id", "chatbot_conversations", ["user_id"]
    )
    op.create_index(
        "ix_chatbot_conversations_id", "chatbot_conversations", ["id"]
    )
    # "Latest conversations for this user" — the conversations list page.
    op.create_index(
        "ix_chatbot_conversations_user_updated",
        "chatbot_conversations",
        ["user_id", "updated_at"],
    )

    # ── messages ──────────────────────────────────────────────────
    op.create_table(
        "chatbot_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "conversation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("chatbot_conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", message_role, nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "include_modules", postgresql.JSONB(), nullable=False, server_default="[]"
        ),
        sa.Column(
            "reasoning_trace", postgresql.JSONB(), nullable=False, server_default="[]"
        ),
        sa.Column(
            "sources", postgresql.JSONB(), nullable=False, server_default="[]"
        ),
        sa.Column("tokens_used", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "conversation_id", "position", name="uq_chatbot_messages_conv_position"
        ),
    )
    op.create_index(
        "ix_chatbot_messages_conversation_id",
        "chatbot_messages",
        ["conversation_id"],
    )
    op.create_index("ix_chatbot_messages_role", "chatbot_messages", ["role"])
    op.create_index("ix_chatbot_messages_id", "chatbot_messages", ["id"])

    # ── executive reports ─────────────────────────────────────────
    op.create_table(
        "chatbot_executive_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("period_label", sa.String(length=100), nullable=False),
        sa.Column(
            "modules_included", postgresql.JSONB(), nullable=False, server_default="[]"
        ),
        sa.Column(
            "response_payload", postgresql.JSONB(), nullable=False, server_default="{}"
        ),
        sa.Column("model_version", sa.String(length=100), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_chatbot_executive_reports_user_id",
        "chatbot_executive_reports",
        ["user_id"],
    )
    op.create_index(
        "ix_chatbot_executive_reports_id", "chatbot_executive_reports", ["id"]
    )
    op.create_index(
        "ix_chatbot_executive_reports_user_created",
        "chatbot_executive_reports",
        ["user_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_chatbot_executive_reports_user_created",
        table_name="chatbot_executive_reports",
    )
    op.drop_index(
        "ix_chatbot_executive_reports_id", table_name="chatbot_executive_reports"
    )
    op.drop_index(
        "ix_chatbot_executive_reports_user_id",
        table_name="chatbot_executive_reports",
    )
    op.drop_table("chatbot_executive_reports")

    op.drop_index("ix_chatbot_messages_id", table_name="chatbot_messages")
    op.drop_index("ix_chatbot_messages_role", table_name="chatbot_messages")
    op.drop_index(
        "ix_chatbot_messages_conversation_id", table_name="chatbot_messages"
    )
    op.drop_table("chatbot_messages")

    op.drop_index(
        "ix_chatbot_conversations_user_updated", table_name="chatbot_conversations"
    )
    op.drop_index(
        "ix_chatbot_conversations_id", table_name="chatbot_conversations"
    )
    op.drop_index(
        "ix_chatbot_conversations_user_id", table_name="chatbot_conversations"
    )
    op.drop_table("chatbot_conversations")

    op.execute("DROP TYPE IF EXISTS chatbot_message_role;")
