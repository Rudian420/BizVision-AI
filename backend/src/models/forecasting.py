"""
BizVision AI — Profit Forecasting Persistence Models

Forecasting exposes four *stateful* analysis endpoints — `/forecast`,
`/sensitivity`, `/what-if`, `/cross-module` — each thin, each keyed on a
single `forecast_id`. Same shape posture as Smart Pricing (TASK-009) and
ESG Sustainability (TASK-012), so we reuse that pattern: one polymorphic,
discriminator-keyed table with JSONB payloads.

   forecast_analyses
     · id, user_id, analysis_type, series_name
     · request_payload  (JSONB)  ← exact API request (history truncated
                                   for size — see service `_persist`)
     · response_payload (JSONB)  ← exact API response
     · headline columns:
         horizon_days         (Integer)
         base_end_value       (Float, nullable)
         bull_end_value       (Float, nullable)
         bear_end_value       (Float, nullable)
         mape                 (Float, nullable)  — backtest MAPE

The `sensitivity` and `what-if` endpoints reference a previously generated
forecast only conceptually (they take their own history payload). We do
**not** require a parent `forecast_id` because all three of `/sensitivity`,
`/what-if`, and `/cross-module` are stateless w.r.t. the prior `/forecast`
call — they accept an inline history series. The user-supplied history is
persisted into `request_payload` so the audit trail is complete.

A separate `RecruitmentSession` model uses the rich relational pattern
because recruitment has *one* analysis type with rich child rows
(candidates, fairness records). Each module's storage matches its shape;
ADR-022's uniform-interface principle applies at the *schema* layer.
"""

from __future__ import annotations

import enum
import uuid
from typing import Any

from sqlalchemy import Enum as SAEnum
from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin, UUIDMixin


class ForecastAnalysisType(str, enum.Enum):
    FORECAST = "forecast"
    SENSITIVITY = "sensitivity"
    WHAT_IF = "what_if"
    CROSS_MODULE = "cross_module"


class ForecastAnalysis(UUIDMixin, TimestampMixin, Base):
    """One row per `/forecasting/{forecast|sensitivity|what-if|cross-module}` call."""

    __tablename__ = "forecast_analyses"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    # ── discriminator + key ────────────────────────────────────────
    analysis_type: Mapped[ForecastAnalysisType] = mapped_column(
        SAEnum(ForecastAnalysisType, name="forecast_analysis_type"),
        nullable=False,
        index=True,
    )
    series_name: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)

    # ── faithful API payloads ──────────────────────────────────────
    request_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    response_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)

    # ── headline values (queryable without JSON parsing) ───────────
    horizon_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    base_end_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    bull_end_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    bear_end_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    mape: Mapped[float | None] = mapped_column(Float, nullable=True)

    # ── model provenance ───────────────────────────────────────────
    model_version: Mapped[str] = mapped_column(String(100), nullable=False)
    processing_time_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    context_signal_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Free-form interpretation snippet — duplicated from
    # `response_payload` narrative for cheap LIKE-search later.
    interpretation: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<ForecastAnalysis {self.id} "
            f"type={self.analysis_type.value} series={self.series_name!r}>"
        )
