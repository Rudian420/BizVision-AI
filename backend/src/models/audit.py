"""
BizVision AI — Cross-Module Audit Log Persistence Model

One immutable row per ML decision across the 5 modules — captures who
called what, when, the high-signal request/response slice, the
top-K SHAP attributions if any, and the fairness pass/fail summary if
any. The 5 module-specific tables (recruitment_sessions / pricing_
analyses / forecast_analyses / sustainability_assessments /
chatbot_*) keep the *full* payloads; this table is a thin,
cross-module index that powers:

  • A unified `/audits` API surface (used by Phase-4 fairness +
    XAI dashboards) without joining 5 different shapes.
  • Cheap aggregation queries — risk-tier histograms, per-module
    decision counts, latency p50/p95 — over a single index.
  • Regulatory auditability: an SME using BizVision under
    Bangladesh-context fairness obligations has one place to point
    a compliance reviewer at.

Shape choices:

  • `reference_id` + `reference_type` form a soft foreign key into the
    owning module's table (e.g. recruitment_sessions.id). We don't
    enforce the FK constraint at the schema level because the audit
    log outlives the owning row — a session deletion should *not*
    cascade-purge its audit trail.
  • `request_summary` / `response_summary` are JSONB **slices**, not
    the full payloads. The owning table has the full record; this
    table holds the cheaply-aggregatable headline values.
  • `risk_tier` is a discrete string column (not a Postgres enum) so
    each module can populate it from its own taxonomy without an
    ALTER TYPE round-trip when one module evolves.
  • No `updated_at` — audit logs are append-only by contract.
  • `module` IS a Postgres enum because the 5 module names are
    architecturally fixed (one per `Phase 1` module).

See ADR-031 (audit log pattern + multi-module hook).
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Float
from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, UUIDMixin


class AuditModule(str, enum.Enum):
    RECRUITMENT = "recruitment"
    PRICING = "pricing"
    FORECASTING = "forecasting"
    SUSTAINABILITY = "sustainability"
    CHATBOT = "chatbot"


class AuditLog(UUIDMixin, Base):
    """One row per ML decision — append-only, cross-module index."""

    __tablename__ = "audit_logs"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    module: Mapped[AuditModule] = mapped_column(
        SAEnum(AuditModule, name="audit_module"),
        nullable=False,
        index=True,
    )
    # Free-form action name — 'analyze', 'optimize', 'score',
    # 'carbon_estimate', 'message', etc. Each module owns its taxonomy.
    action: Mapped[str] = mapped_column(String(40), nullable=False, index=True)

    # Soft FK to the owning row (no DB-level constraint — see docstring).
    reference_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), nullable=True, index=True
    )
    reference_type: Mapped[str | None] = mapped_column(String(60), nullable=True)

    # High-signal JSON slices (NOT the full payload — that lives in the
    # owning table).
    request_summary: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, nullable=False
    )
    response_summary: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, nullable=False
    )
    explanation_summary: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, nullable=True
    )
    fairness_summary: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, nullable=True
    )

    risk_tier: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True)

    model_version: Mapped[str] = mapped_column(String(100), nullable=False)
    latency_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # Append-only — no `updated_at`. Default is server-side so
    # asynchronous recorders all agree on a consistent timestamp.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<AuditLog {self.id} module={self.module.value} "
            f"action={self.action!r} risk={self.risk_tier!r}>"
        )
