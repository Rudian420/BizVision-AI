"""Cross-module audit log — Phase-4 fairness/XAI dashboard primitive.

Revision ID: 0006_audit_logs
Revises: 0005_chatbot_conversations
Create Date: 2026-05-30

Adds the `audit_logs` table — one immutable row per ML decision across
all 5 modules (recruitment / pricing / forecasting / sustainability /
chatbot). Designed as a thin cross-module index that powers the
`/api/v1/audits` API and the Phase-4 fairness + XAI dashboards
without joining against five differently-shaped owning tables.

  • `module` is a Postgres enum (the 5 names are architecturally fixed).
  • `risk_tier` is a free-form string — each module's risk taxonomy
    evolves without an `ALTER TYPE` round-trip.
  • `reference_id` is a soft FK into the owning module table; no DB
    constraint, because the audit row must outlive the owning record.
  • Append-only — no `updated_at` column.

ADR-031 documents the pattern + the multi-module hook (one
`AuditService.record(...)` call per module service at end of /analyze
/score/optimize/forecast/message; recruitment is wired first as the
proof-of-pattern).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0006_audit_logs"
down_revision: str | None = "0005_chatbot_conversations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    audit_module = postgresql.ENUM(
        "recruitment",
        "pricing",
        "forecasting",
        "sustainability",
        "chatbot",
        name="audit_module",
        create_type=False,
    )
    audit_module.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("module", audit_module, nullable=False),
        sa.Column("action", sa.String(length=40), nullable=False),
        # Soft FK — see migration docstring.
        sa.Column("reference_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reference_type", sa.String(length=60), nullable=True),
        sa.Column(
            "request_summary", postgresql.JSONB(), nullable=False, server_default="{}"
        ),
        sa.Column(
            "response_summary", postgresql.JSONB(), nullable=False, server_default="{}"
        ),
        sa.Column("explanation_summary", postgresql.JSONB(), nullable=True),
        sa.Column("fairness_summary", postgresql.JSONB(), nullable=True),
        sa.Column("risk_tier", sa.String(length=16), nullable=True),
        sa.Column("model_version", sa.String(length=100), nullable=False),
        sa.Column("latency_ms", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_index("ix_audit_logs_id", "audit_logs", ["id"])
    op.create_index("ix_audit_logs_user_id", "audit_logs", ["user_id"])
    op.create_index("ix_audit_logs_module", "audit_logs", ["module"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_reference_id", "audit_logs", ["reference_id"])
    op.create_index("ix_audit_logs_risk_tier", "audit_logs", ["risk_tier"])
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])
    # Hot path for the dashboard: "decisions for this user, newest first".
    op.create_index(
        "ix_audit_logs_user_created",
        "audit_logs",
        ["user_id", sa.text("created_at DESC")],
    )
    # Hot path for module summary aggregates.
    op.create_index(
        "ix_audit_logs_user_module_created",
        "audit_logs",
        ["user_id", "module", sa.text("created_at DESC")],
    )


def downgrade() -> None:
    op.drop_index("ix_audit_logs_user_module_created", table_name="audit_logs")
    op.drop_index("ix_audit_logs_user_created", table_name="audit_logs")
    op.drop_index("ix_audit_logs_created_at", table_name="audit_logs")
    op.drop_index("ix_audit_logs_risk_tier", table_name="audit_logs")
    op.drop_index("ix_audit_logs_reference_id", table_name="audit_logs")
    op.drop_index("ix_audit_logs_action", table_name="audit_logs")
    op.drop_index("ix_audit_logs_module", table_name="audit_logs")
    op.drop_index("ix_audit_logs_user_id", table_name="audit_logs")
    op.drop_index("ix_audit_logs_id", table_name="audit_logs")
    op.drop_table("audit_logs")
    op.execute("DROP TYPE IF EXISTS audit_module;")
