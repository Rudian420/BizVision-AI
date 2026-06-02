"""
BizVision AI — Shared Schema Primitives

Enums and small response models reused across multiple modules.
"""

from __future__ import annotations

from enum import Enum
from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ScenarioType(str, Enum):
    BASE = "base"
    BULL = "bull"
    BEAR = "bear"


class MessageResponse(BaseModel):
    """Simple acknowledgement payload."""

    message: str = Field(..., description="Human-readable status message")


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic envelope for list endpoints."""

    items: list[T] = Field(default_factory=list)
    total: int = Field(0, ge=0)
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)


class SHAPFeature(BaseModel):
    """One feature's contribution to a model output."""

    feature_name: str
    shap_value: float
    feature_value: str | float
    contribution_direction: str = Field(..., description="'positive' or 'negative'")
    importance_rank: int = Field(..., ge=1)
