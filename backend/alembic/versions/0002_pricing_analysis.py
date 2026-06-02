"""Pricing analyses — single discriminator-keyed table.

Revision ID: 0002_pricing_analysis
Revises: 0001_initial
Create Date: 2026-05-29

Mirror of the recruitment-side persistence work (TASK-007). Adds the
`pricing_analyses` table covering all four pricing endpoints:
`/optimize`, `/simulate`, `/elasticity`, `/scenarios`. Discriminator
`analysis_type` + JSONB payloads keep the storage thin while leaving
room for per-type analytics later.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0002_pricing_analysis"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pricing_type = postgresql.ENUM(
        "optimize",
        "monte_carlo",
        "elasticity",
        "scenario_comparison",
        name="pricing_analysis_type",
        create_type=False,
    )
    pricing_type.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "pricing_analyses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("analysis_type", pricing_type, nullable=False),
        sa.Column("product_id", sa.String(length=128), nullable=False),
        sa.Column(
            "request_payload",
            postgresql.JSONB(),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "response_payload",
            postgresql.JSONB(),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("recommended_price", sa.Float(), nullable=True),
        sa.Column("expected_revenue_uplift", sa.Float(), nullable=True),
        sa.Column("model_version", sa.String(length=100), nullable=False),
        sa.Column(
            "processing_time_ms", sa.Float(), nullable=False, server_default="0"
        ),
        sa.Column("context_signal_id", sa.String(length=64), nullable=True),
        sa.Column("num_trials_or_points", sa.Integer(), nullable=True),
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
    op.create_index("ix_pricing_analyses_user_id", "pricing_analyses", ["user_id"])
    op.create_index(
        "ix_pricing_analyses_product_id", "pricing_analyses", ["product_id"]
    )
    op.create_index(
        "ix_pricing_analyses_analysis_type", "pricing_analyses", ["analysis_type"]
    )
    op.create_index("ix_pricing_analyses_id", "pricing_analyses", ["id"])
    # Composite index for the common "latest per product per user" query.
    op.create_index(
        "ix_pricing_analyses_user_product",
        "pricing_analyses",
        ["user_id", "product_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_pricing_analyses_user_product", table_name="pricing_analyses"
    )
    op.drop_index("ix_pricing_analyses_id", table_name="pricing_analyses")
    op.drop_index(
        "ix_pricing_analyses_analysis_type", table_name="pricing_analyses"
    )
    op.drop_index("ix_pricing_analyses_product_id", table_name="pricing_analyses")
    op.drop_index("ix_pricing_analyses_user_id", table_name="pricing_analyses")
    op.drop_table("pricing_analyses")
    op.execute("DROP TYPE IF EXISTS pricing_analysis_type;")
