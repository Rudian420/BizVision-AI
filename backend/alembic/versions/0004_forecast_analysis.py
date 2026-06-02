"""Forecast analyses — polymorphic discriminator table.

Revision ID: 0004_forecast_analysis
Revises: 0003_sustainability_assessment
Create Date: 2026-05-30

Mirror of the pricing-side (TASK-009) and ESG-side (TASK-012) persistence
work. Adds the `forecast_analyses` table covering the four stateful
forecasting endpoints (`/forecast`, `/sensitivity`, `/what-if`,
`/cross-module`). The explanation endpoint is stateful only as a *read*
of an existing row — no row produced.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0004_forecast_analysis"
down_revision: str | None = "0003_sustainability_assessment"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    forecast_type = postgresql.ENUM(
        "forecast",
        "sensitivity",
        "what_if",
        "cross_module",
        name="forecast_analysis_type",
        create_type=False,
    )
    forecast_type.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "forecast_analyses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("analysis_type", forecast_type, nullable=False),
        sa.Column("series_name", sa.String(length=128), nullable=True),
        sa.Column(
            "request_payload", postgresql.JSONB(), nullable=False, server_default="{}"
        ),
        sa.Column(
            "response_payload", postgresql.JSONB(), nullable=False, server_default="{}"
        ),
        sa.Column("horizon_days", sa.Integer(), nullable=True),
        sa.Column("base_end_value", sa.Float(), nullable=True),
        sa.Column("bull_end_value", sa.Float(), nullable=True),
        sa.Column("bear_end_value", sa.Float(), nullable=True),
        sa.Column("mape", sa.Float(), nullable=True),
        sa.Column("model_version", sa.String(length=100), nullable=False),
        sa.Column(
            "processing_time_ms", sa.Float(), nullable=False, server_default="0"
        ),
        sa.Column("context_signal_id", sa.String(length=64), nullable=True),
        sa.Column("interpretation", sa.Text(), nullable=True),
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
        "ix_forecast_analyses_user_id", "forecast_analyses", ["user_id"]
    )
    op.create_index(
        "ix_forecast_analyses_analysis_type", "forecast_analyses", ["analysis_type"]
    )
    op.create_index(
        "ix_forecast_analyses_series_name", "forecast_analyses", ["series_name"]
    )
    op.create_index("ix_forecast_analyses_id", "forecast_analyses", ["id"])
    # Composite index for the common "latest per series per user" query.
    op.create_index(
        "ix_forecast_analyses_user_series",
        "forecast_analyses",
        ["user_id", "series_name", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_forecast_analyses_user_series", table_name="forecast_analyses"
    )
    op.drop_index("ix_forecast_analyses_id", table_name="forecast_analyses")
    op.drop_index(
        "ix_forecast_analyses_series_name", table_name="forecast_analyses"
    )
    op.drop_index(
        "ix_forecast_analyses_analysis_type", table_name="forecast_analyses"
    )
    op.drop_index("ix_forecast_analyses_user_id", table_name="forecast_analyses")
    op.drop_table("forecast_analyses")
    op.execute("DROP TYPE IF EXISTS forecast_analysis_type;")
