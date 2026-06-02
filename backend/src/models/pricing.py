"""
BizVision AI — Smart Pricing Persistence Models

Pricing exposes four analysis endpoints (`/optimize`, `/simulate`,
`/elasticity`, `/scenarios`) that share request/response shape *family*
but not signature: they all key on `(user_id, product_id)` and return a
small JSON-shaped result. Rather than four parallel tables we use one
discriminator-keyed table — `PricingAnalysis` — with:

  • first-class columns for the headline values we want to filter/sort on
    (`product_id`, `analysis_type`, `recommended_price`, `expected_revenue_uplift`)
  • JSONB payloads for the request + response (faithful to the API
    schema, no translation layer)

This keeps queries like *"latest optimisation per product"* cheap without
fragmenting the schema four ways. The discriminator also makes the path
to future per-type analytics (one materialised view per type) clean.

A separate `RecruitmentSession` model already exists in
`backend/src/models/recruitment.py`; the choice of *one polymorphic table*
here vs *one table per use* there is deliberate: recruitment has a *single*
analysis type with rich relational child data (candidates, fairness
records); pricing has *four* analysis types, each thin and self-contained.
ADR-022's uniform interface principle applies at the *schema* layer, not
the storage layer — match each module's shape.
"""

from __future__ import annotations

import enum
import uuid
from typing import Any

from sqlalchemy import Enum as SAEnum
from sqlalchemy import Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin, UUIDMixin


class PricingAnalysisType(str, enum.Enum):
    OPTIMIZE = "optimize"
    MONTE_CARLO = "monte_carlo"
    ELASTICITY = "elasticity"
    SCENARIO_COMPARISON = "scenario_comparison"


class PricingAnalysis(UUIDMixin, TimestampMixin, Base):
    """One row per `/pricing/{optimize|simulate|elasticity|scenarios}` call."""

    __tablename__ = "pricing_analyses"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    # ── discriminator + key ────────────────────────────────────────
    analysis_type: Mapped[PricingAnalysisType] = mapped_column(
        SAEnum(PricingAnalysisType, name="pricing_analysis_type"),
        nullable=False,
        index=True,
    )
    product_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)

    # ── faithful API payloads ──────────────────────────────────────
    # These mirror the Pydantic request/response shapes one-to-one. Keeping
    # them as JSONB means there is no translation layer between the service
    # and the DB — and pg can index inside them with `jsonb_path_ops` when
    # specific query patterns emerge.
    request_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    response_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)

    # ── headline values (queryable without JSON parsing) ───────────
    # Nullable because not every analysis type emits them. Filling them
    # at write time avoids server-side jsonb_extract every query.
    recommended_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    expected_revenue_uplift: Mapped[float | None] = mapped_column(Float, nullable=True)

    # ── model provenance ───────────────────────────────────────────
    model_version: Mapped[str] = mapped_column(String(100), nullable=False)
    processing_time_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # ── cross-module signal id (Shared Context Bus) ────────────────
    context_signal_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Number of trials/points — useful for filtering Monte Carlo runs by
    # statistical confidence without unpacking `request_payload`.
    num_trials_or_points: Mapped[int | None] = mapped_column(Integer, nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<PricingAnalysis {self.id} "
            f"type={self.analysis_type.value} product={self.product_id!r}>"
        )
