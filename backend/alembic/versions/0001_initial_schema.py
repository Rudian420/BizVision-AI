"""Initial schema: users, refresh_tokens, recruitment sessions + persistence,
pgvector candidate index.

Revision ID: 0001_initial
Revises:
Create Date: 2026-05-28

Notes:
- Enables the `vector` extension (idempotent). The `infrastructure/postgres/init.sql`
  also creates it on container start; the duplicate here makes the migration
  self-contained when applied against a fresh DB.
- Tables created by this migration are also represented in `Base.metadata`, so
  `Base.metadata.create_all(checkfirst=True)` on app startup remains a no-op
  after this migration has run. We keep `create_all` for the test path which
  may target SQLite where Alembic migrations are skipped.
- HNSW index on `candidate_vectors.embedding` uses `vector_cosine_ops` so
  cosine distance (`<=>`) is the indexed metric — matches the SBERT
  encoder's L2-normalised output (cosine = 1 - distance).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── pgvector extension (idempotent) ─────────────────────────────
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    # ── user_role enum ─────────────────────────────────────────────
    user_role = postgresql.ENUM(
        "admin", "analyst", "viewer", name="user_role", create_type=False
    )
    user_role.create(op.get_bind(), checkfirst=True)

    # ── users ───────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=200), nullable=True),
        sa.Column("company_name", sa.String(length=200), nullable=True),
        sa.Column("role", user_role, nullable=False, server_default="analyst"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
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
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_id", "users", ["id"])

    # ── refresh_tokens ──────────────────────────────────────────────
    op.create_table(
        "refresh_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked", sa.Boolean(), nullable=False, server_default=sa.false()),
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
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])
    op.create_index(
        "ix_refresh_tokens_token_hash", "refresh_tokens", ["token_hash"], unique=True
    )
    op.create_index("ix_refresh_tokens_id", "refresh_tokens", ["id"])

    # ── recruitment_sessions ────────────────────────────────────────
    op.create_table(
        "recruitment_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("job_title", sa.String(length=200), nullable=False),
        sa.Column("job_description", sa.Text(), nullable=False),
        sa.Column(
            "job_details", postgresql.JSONB(), nullable=False, server_default="{}"
        ),
        sa.Column("total_candidates", sa.Integer(), nullable=False),
        sa.Column("top_k", sa.Integer(), nullable=False),
        sa.Column(
            "anonymize_names", sa.Boolean(), nullable=False, server_default=sa.true()
        ),
        sa.Column(
            "protected_attributes",
            postgresql.JSONB(),
            nullable=False,
            server_default="[]",
        ),
        sa.Column("processing_time_ms", sa.Float(), nullable=False),
        sa.Column("model_version", sa.String(length=100), nullable=False),
        sa.Column("sbert_model", sa.String(length=200), nullable=False),
        sa.Column(
            "ensemble_weights", postgresql.JSONB(), nullable=False, server_default="{}"
        ),
        sa.Column("context_signal_id", sa.String(length=64), nullable=True),
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
        "ix_recruitment_sessions_user_id", "recruitment_sessions", ["user_id"]
    )
    op.create_index("ix_recruitment_sessions_id", "recruitment_sessions", ["id"])

    # ── candidate_scores ────────────────────────────────────────────
    op.create_table(
        "candidate_scores",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("recruitment_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("candidate_id", sa.String(length=128), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=True),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("composite_score", sa.Float(), nullable=False),
        sa.Column("semantic_score", sa.Float(), nullable=False),
        sa.Column("structured_score", sa.Float(), nullable=False),
        sa.Column("confidence_level", sa.Float(), nullable=False),
        sa.Column("years_experience", sa.Float(), nullable=True),
        sa.Column("education_level", sa.String(length=32), nullable=True),
        sa.Column(
            "matched_skills", postgresql.JSONB(), nullable=False, server_default="[]"
        ),
        sa.Column(
            "missing_skills", postgresql.JSONB(), nullable=False, server_default="[]"
        ),
        sa.Column(
            "top_shap_features",
            postgresql.JSONB(),
            nullable=False,
            server_default="[]",
        ),
        sa.Column("ai_rationale", sa.Text(), nullable=False, server_default=""),
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
    op.create_index("ix_candidate_scores_session_id", "candidate_scores", ["session_id"])
    op.create_index("ix_candidate_scores_candidate_id", "candidate_scores", ["candidate_id"])
    op.create_index("ix_candidate_scores_id", "candidate_scores", ["id"])

    # ── fairness_audit_records ──────────────────────────────────────
    op.create_table(
        "fairness_audit_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("recruitment_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("protected_attribute", sa.String(length=64), nullable=False),
        sa.Column("overall_risk_level", sa.String(length=16), nullable=False),
        sa.Column("n_samples_audited", sa.Integer(), nullable=False),
        sa.Column("threshold_topk", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("demographic_parity_difference", sa.Float(), nullable=False),
        sa.Column("disparate_impact", sa.Float(), nullable=False),
        sa.Column("equalized_odds_difference", sa.Float(), nullable=True),
        sa.Column("metrics", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("per_group", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column(
            "bias_heatmap_data", postgresql.JSONB(), nullable=False, server_default="{}"
        ),
        sa.Column(
            "mitigation_strategies",
            postgresql.JSONB(),
            nullable=False,
            server_default="[]",
        ),
        sa.Column("interpretation", sa.Text(), nullable=False, server_default=""),
        sa.Column("model_card_url", sa.String(length=500), nullable=True),
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
        "ix_fairness_audit_records_session_id",
        "fairness_audit_records",
        ["session_id"],
    )

    # ── candidate_vectors (pgvector + HNSW) ─────────────────────────
    op.create_table(
        "candidate_vectors",
        sa.Column("candidate_id", sa.String(length=128), primary_key=True),
        sa.Column("encoder_name", sa.String(length=200), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    # `embedding` is added via raw SQL because the pgvector column type is
    # not native to SQLAlchemy core; dimensionality must match SBERT_DIM.
    op.execute("ALTER TABLE candidate_vectors ADD COLUMN embedding vector(768) NOT NULL;")
    op.execute(
        "CREATE INDEX candidate_vectors_hnsw_idx "
        "ON candidate_vectors USING hnsw (embedding vector_cosine_ops);"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS candidate_vectors_hnsw_idx;")
    op.drop_table("candidate_vectors")
    op.drop_index(
        "ix_fairness_audit_records_session_id", table_name="fairness_audit_records"
    )
    op.drop_table("fairness_audit_records")
    op.drop_index("ix_candidate_scores_id", table_name="candidate_scores")
    op.drop_index("ix_candidate_scores_candidate_id", table_name="candidate_scores")
    op.drop_index("ix_candidate_scores_session_id", table_name="candidate_scores")
    op.drop_table("candidate_scores")
    op.drop_index("ix_recruitment_sessions_id", table_name="recruitment_sessions")
    op.drop_index("ix_recruitment_sessions_user_id", table_name="recruitment_sessions")
    op.drop_table("recruitment_sessions")
    op.drop_index("ix_refresh_tokens_id", table_name="refresh_tokens")
    op.drop_index("ix_refresh_tokens_token_hash", table_name="refresh_tokens")
    op.drop_index("ix_refresh_tokens_user_id", table_name="refresh_tokens")
    op.drop_table("refresh_tokens")
    op.drop_index("ix_users_id", table_name="users")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
    op.execute("DROP TYPE IF EXISTS user_role;")
    # The `vector` extension is left in place — other apps may depend on it.
