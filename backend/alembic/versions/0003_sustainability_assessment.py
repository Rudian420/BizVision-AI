"""Sustainability assessments — polymorphic discriminator table.

Revision ID: 0003_sustainability_assessment
Revises: 0002_pricing_analysis
Create Date: 2026-05-30

Mirror of the pricing-side persistence work (TASK-009). Adds the
`sustainability_assessments` table covering the four stateful ESG
endpoints (`/score`, `/simulate`, `/recommendations`, `/carbon-estimate`).
The reference endpoint `/benchmarks/{industry}` stays stateless.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0003_sustainability_assessment"
down_revision: str | None = "0002_pricing_analysis"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    sustainability_type = postgresql.ENUM(
        "score",
        "simulation",
        "recommendations",
        "carbon_estimate",
        name="sustainability_assessment_type",
        create_type=False,
    )
    sustainability_type.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "sustainability_assessments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("assessment_type", sustainability_type, nullable=False),
        sa.Column("company_name", sa.String(length=200), nullable=True),
        sa.Column("industry", sa.String(length=100), nullable=True),
        sa.Column(
            "request_payload", postgresql.JSONB(), nullable=False, server_default="{}"
        ),
        sa.Column(
            "response_payload", postgresql.JSONB(), nullable=False, server_default="{}"
        ),
        sa.Column("composite_score", sa.Float(), nullable=True),
        sa.Column("risk_level", sa.String(length=16), nullable=True),
        sa.Column("total_tco2e", sa.Float(), nullable=True),
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
        "ix_sustainability_assessments_user_id",
        "sustainability_assessments",
        ["user_id"],
    )
    op.create_index(
        "ix_sustainability_assessments_assessment_type",
        "sustainability_assessments",
        ["assessment_type"],
    )
    op.create_index(
        "ix_sustainability_assessments_company_name",
        "sustainability_assessments",
        ["company_name"],
    )
    op.create_index(
        "ix_sustainability_assessments_industry",
        "sustainability_assessments",
        ["industry"],
    )
    op.create_index(
        "ix_sustainability_assessments_id",
        "sustainability_assessments",
        ["id"],
    )
    # Composite index for the common "latest per company per user" query.
    op.create_index(
        "ix_sustainability_assessments_user_company",
        "sustainability_assessments",
        ["user_id", "company_name", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_sustainability_assessments_user_company",
        table_name="sustainability_assessments",
    )
    op.drop_index(
        "ix_sustainability_assessments_id", table_name="sustainability_assessments"
    )
    op.drop_index(
        "ix_sustainability_assessments_industry",
        table_name="sustainability_assessments",
    )
    op.drop_index(
        "ix_sustainability_assessments_company_name",
        table_name="sustainability_assessments",
    )
    op.drop_index(
        "ix_sustainability_assessments_assessment_type",
        table_name="sustainability_assessments",
    )
    op.drop_index(
        "ix_sustainability_assessments_user_id",
        table_name="sustainability_assessments",
    )
    op.drop_table("sustainability_assessments")
    op.execute("DROP TYPE IF EXISTS sustainability_assessment_type;")
