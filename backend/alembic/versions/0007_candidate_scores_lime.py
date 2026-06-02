"""Add `top_lime_features` JSONB column to `candidate_scores`.

Revision ID: 0007_candidate_scores_lime
Revises: 0006_audit_logs
Create Date: 2026-06-03

TASK-050 — closes the persisted-LIME gap left open by TASK-049.

Wave-3a (TASK-049) wired the real `LIMERecruitmentExplainer` through
`RecruitmentInferenceClient` so the *live* `/recruitment/analyze`
response carries `ranked_candidates[*].top_lime_features` populated
from the XGBoost arm. But the persistence layer (TASK-022 + TASK-032)
predated LIME — `candidate_scores` had only `top_shap_features`, so
every historical session reconstructed through `get_session_detail`
served empty LIME panels even when the original `/analyze` had
produced rich attributions.

This migration adds the symmetric JSONB column. Default `[]` (Postgres
`'[]'::jsonb`) so the column is `NOT NULL` and existing rows backfill
cleanly without a separate UPDATE pass. The mapped Python type stays
`list[dict[str, Any]]` — same shape as `top_shap_features`, since
both fields serialise the identical `SHAPFeatureAttribution` Pydantic
model (the SHAP-vs-LIME semantics are upstream, not on the wire).

The migration is additive + nullable-free; downgrade simply drops
the column. No data needs to be moved.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0007_candidate_scores_lime"
down_revision: str | None = "0006_audit_logs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "candidate_scores",
        sa.Column(
            "top_lime_features",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )


def downgrade() -> None:
    op.drop_column("candidate_scores", "top_lime_features")
