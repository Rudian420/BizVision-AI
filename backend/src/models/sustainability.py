"""
BizVision AI — Green Business Sustainability Persistence Models

ESG exposes four *stateful* analysis endpoints — `/score`, `/simulate`,
`/recommendations`, `/carbon-estimate` — plus one *stateless* reference
endpoint (`/benchmarks/{industry}`) that does not produce a row. Same
shape as Smart Pricing (TASK-009), so we reuse that pattern: one
polymorphic, discriminator-keyed table with JSONB payloads.

   sustainability_assessments
     · id, user_id, assessment_type, company_name, industry
     · request_payload  (JSONB)  ← exact API request
     · response_payload (JSONB)  ← exact API response
     · headline columns:
         composite_score      (Float, nullable)  — `/score` only
         risk_level           (String, nullable) — `/score`, `/simulate`
         total_tco2e          (Float, nullable)  — `/carbon-estimate` only

The `recommendations` and `simulate` endpoints both reference an existing
assessment row via the `assessment_id` echoed by `/score`. Persisting
them as **new** rows (rather than child rows of the score) keeps the
schema flat — auditing every API call separately is the same posture
TASK-009 took for pricing. We can always GROUP BY `assessment_id` later
if a thread-style view is wanted.

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
from sqlalchemy import Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin, UUIDMixin


class SustainabilityAssessmentType(str, enum.Enum):
    SCORE = "score"
    SIMULATION = "simulation"
    RECOMMENDATIONS = "recommendations"
    CARBON_ESTIMATE = "carbon_estimate"


class SustainabilityAssessment(UUIDMixin, TimestampMixin, Base):
    """One row per `/sustainability/{score|simulate|recommendations|carbon-estimate}`."""

    __tablename__ = "sustainability_assessments"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    # ── discriminator + key ────────────────────────────────────────
    assessment_type: Mapped[SustainabilityAssessmentType] = mapped_column(
        SAEnum(SustainabilityAssessmentType, name="sustainability_assessment_type"),
        nullable=False,
        index=True,
    )
    company_name: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)
    industry: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)

    # ── faithful API payloads ──────────────────────────────────────
    request_payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, nullable=False
    )
    response_payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, nullable=False
    )

    # ── headline values (queryable without JSON parsing) ───────────
    # Nullable because not every assessment type emits them.
    composite_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    risk_level: Mapped[str | None] = mapped_column(String(16), nullable=True)
    total_tco2e: Mapped[float | None] = mapped_column(Float, nullable=True)

    # ── model provenance ───────────────────────────────────────────
    model_version: Mapped[str] = mapped_column(String(100), nullable=False)
    processing_time_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    context_signal_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Free-form interpretation snippet — duplicated from
    # `response_payload["interpretation"]` for cheap LIKE-search later.
    interpretation: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<SustainabilityAssessment {self.id} "
            f"type={self.assessment_type.value} industry={self.industry!r}>"
        )
