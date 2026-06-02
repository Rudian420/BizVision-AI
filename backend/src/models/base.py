"""
BizVision AI — ORM Base & Mixins

Re-exports the single declarative ``Base`` defined in core.database so
that all models share one metadata registry (critical for
``Base.metadata.create_all`` and Alembic autogenerate), and provides
common column mixins.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

# Single source of truth for the declarative base.
from src.core.database import Base

__all__ = ["Base", "UUIDMixin", "TimestampMixin"]


class UUIDMixin:
    """Primary key as a server-generated UUID4."""

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )


class TimestampMixin:
    """``created_at`` / ``updated_at`` audit columns."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
