"""
BizVision AI — Recruitment Persistence Models

Stores recruitment analyses end-to-end so that the API can:

  • Retrieve a session and its ranking (`GET /recruitment/sessions/{id}`)
  • Return persisted SHAP attributions per candidate
  • Return the fairness audit alongside the ranking
  • Power the recruiter copilot and audit log

Schema:

    recruitment_sessions
      └── candidate_scores         (one-to-many; ordered by rank)
      └── fairness_audit_records   (one-to-many; one per protected attribute)

    candidate_vectors              (pgvector — embedding cache for online retrieval)

All large/variable payloads (matched skills list, SHAP feature attributions,
per-group fairness breakdown) live in JSONB columns rather than separate
tables — Postgres jsonb is indexable and the shape mirrors the API schemas
directly, avoiding a translation layer between the service and the DB.

The pgvector column on `candidate_vectors` requires the `vector` extension;
the Alembic migration creates it (idempotent `CREATE EXTENSION IF NOT EXISTS`).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin, UUIDMixin

# pgvector ships its own SQLAlchemy column type. Lazily importable so the
# rest of the models layer keeps loading in environments where pgvector
# isn't installed yet (e.g. CI lint runs without the ML stack).
try:
    from pgvector.sqlalchemy import Vector

    _HAS_PGVECTOR = True
except ImportError:  # pragma: no cover - optional dep
    Vector = None  # type: ignore[assignment, misc]
    _HAS_PGVECTOR = False


# Embedding dimensionality for `all-mpnet-base-v2`. If we ever swap to a
# different SBERT model, the dimension changes here AND a new migration must
# be written — pgvector's `vector(N)` is fixed-length per column.
SBERT_DIM = 768


# ── 1. Recruitment session ──────────────────────────────────────────


class RecruitmentSession(UUIDMixin, TimestampMixin, Base):
    """One row per `POST /recruitment/analyze` invocation."""

    __tablename__ = "recruitment_sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    # Job snapshot — denormalised so a session is interpretable even if the JD
    # source of truth is later edited / deleted.
    job_title: Mapped[str] = mapped_column(String(200), nullable=False)
    job_description: Mapped[str] = mapped_column(Text, nullable=False)
    job_details: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)

    # Run characteristics.
    total_candidates: Mapped[int] = mapped_column(Integer, nullable=False)
    top_k: Mapped[int] = mapped_column(Integer, nullable=False)
    anonymize_names: Mapped[bool] = mapped_column(default=True, nullable=False)
    protected_attributes: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    processing_time_ms: Mapped[float] = mapped_column(Float, nullable=False)

    # Model provenance — see ADR-022 (uniform RankingModel interface) and
    # ADR-023 (linear-blend ensemble).
    model_version: Mapped[str] = mapped_column(String(100), nullable=False)
    sbert_model: Mapped[str] = mapped_column(String(200), nullable=False)
    ensemble_weights: Mapped[dict[str, float]] = mapped_column(JSONB, default=dict, nullable=False)

    # Cross-module signal id emitted to the Shared Context Bus on completion.
    context_signal_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Relationships — eager-load candidates with the session; fairness rows
    # are small, eager-load them too.
    candidates: Mapped[list[CandidateScore]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="CandidateScore.rank",
    )
    fairness_audits: Mapped[list[FairnessAuditRecord]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<RecruitmentSession {self.id} " f"job={self.job_title!r} n={self.total_candidates}>"
        )


# ── 2. Per-candidate score ──────────────────────────────────────────


class CandidateScore(UUIDMixin, TimestampMixin, Base):
    """One row per ranked candidate inside a session.

    Stores the composite score plus the SBERT + structured sub-scores so the
    explainability adapter can re-render the narrative without re-running the
    ensemble (ADR-023).
    """

    __tablename__ = "candidate_scores"

    session_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("recruitment_sessions.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    # Stable external identifier (not the row UUID) — what the API echoes.
    candidate_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    display_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)

    composite_score: Mapped[float] = mapped_column(Float, nullable=False)
    semantic_score: Mapped[float] = mapped_column(Float, nullable=False)
    structured_score: Mapped[float] = mapped_column(Float, nullable=False)
    confidence_level: Mapped[float] = mapped_column(Float, nullable=False)

    # Structured features that drove the score — kept for the audit trail
    # even when the source CV is later purged for privacy compliance.
    years_experience: Mapped[float | None] = mapped_column(Float, nullable=True)
    education_level: Mapped[str | None] = mapped_column(String(32), nullable=True)
    matched_skills: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    missing_skills: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)

    # Explainability payload — list of SHAPFeatureAttribution dicts, exactly
    # the shape the recruitment schema serialises.
    top_shap_features: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, default=list, nullable=False
    )
    # TASK-050 — symmetric LIME column added in migration 0007. Same
    # serialised shape as `top_shap_features` (both use the upstream
    # `SHAPFeatureAttribution` Pydantic model). The SHAP-vs-LIME
    # semantics live in the explainer + the panel — the wire payload
    # is structurally identical so a single JSONB column suffices.
    top_lime_features: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, default=list, nullable=False, server_default="[]"
    )
    ai_rationale: Mapped[str] = mapped_column(Text, nullable=False, default="")

    session: Mapped[RecruitmentSession] = relationship(back_populates="candidates")


# ── 3. Fairness audit record ─────────────────────────────────────────


class FairnessAuditRecord(UUIDMixin, TimestampMixin, Base):
    """One row per protected attribute audited for a session.

    Intersectional audits (gender × age_group) are stored as a separate row
    with `protected_attribute = 'gender×age_group'` — mirroring the
    `intersectional_audit` output shape from `ml.recruitment.fairness.auditor`.
    """

    __tablename__ = "fairness_audit_records"

    session_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("recruitment_sessions.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    protected_attribute: Mapped[str] = mapped_column(String(64), nullable=False)
    overall_risk_level: Mapped[str] = mapped_column(String(16), nullable=False)
    n_samples_audited: Mapped[int] = mapped_column(Integer, nullable=False)
    threshold_topk: Mapped[int] = mapped_column(Integer, nullable=False, default=5)

    demographic_parity_difference: Mapped[float] = mapped_column(Float, nullable=False)
    disparate_impact: Mapped[float] = mapped_column(Float, nullable=False)
    equalized_odds_difference: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Per-group breakdown + mitigation suggestions + raw metric list —
    # shape matches the `FairnessAuditResponse` schema directly.
    metrics: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list, nullable=False)
    per_group: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list, nullable=False)
    bias_heatmap_data: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    mitigation_strategies: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, default=list, nullable=False
    )
    interpretation: Mapped[str] = mapped_column(Text, nullable=False, default="")
    model_card_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    session: Mapped[RecruitmentSession] = relationship(back_populates="fairness_audits")


# ── 4. Candidate vector index (pgvector) ─────────────────────────────


class CandidateVector(Base):
    """SBERT embedding per candidate — production semantic-search path.

    Independent of session rows: a candidate has one vector regardless of how
    many JDs they're scored against. Vector dimensionality is locked to
    `SBERT_DIM` (768 for `all-mpnet-base-v2`). The HNSW index for cosine
    distance is created in the Alembic migration.

    The pgvector column is only declared when the optional pgvector library
    is present — see `_HAS_PGVECTOR`. In environments without pgvector the
    column falls back to a JSON list, which is functionally correct for the
    JSONL fallback path used in unit tests.
    """

    __tablename__ = "candidate_vectors"

    candidate_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    encoder_name: Mapped[str] = mapped_column(String(200), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    if _HAS_PGVECTOR and Vector is not None:
        embedding: Mapped[list[float]] = mapped_column(Vector(SBERT_DIM), nullable=False)
    else:  # pragma: no cover - exercised only when pgvector is missing
        embedding: Mapped[list[float]] = mapped_column(JSON, nullable=False)
