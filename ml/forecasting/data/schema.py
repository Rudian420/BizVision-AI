"""
Forecasting data schemas.

Pure dataclasses — no heavy imports. Mirrors `ml.pricing.data.schema`
and `ml.recruitment.data.schema` so the cross-module pattern stays
recognisable: every package's `data` sub-module holds frozen
dataclasses; loaders produce a `*Dataset` container; downstream code
consumes these without dragging in pandas / numpy at import time.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class TimeSeriesPoint:
    """One observation in a profit / revenue time series.

    `ds` is an ISO-8601 date string so the dataclass remains pickle-safe
    and JSON-round-trippable. Numeric conversion happens at the feature
    layer where pandas / numpy is already on the import path.
    """

    ds: str
    y: float
    series_id: str = "default"


@dataclass(frozen=True)
class TimeSeriesDataset:
    """A complete history for one series — ordered, gap-free at the
    daily frequency.

    The ordering invariant is enforced by `loader.load_synthetic_dataset`;
    downstream models assume strictly monotonic `ds` and contiguous
    daily spacing. Gaps are filled by forward-fill at load time.
    """

    series_id: str
    frequency: str  # "D" | "W" | "M"
    points: tuple[TimeSeriesPoint, ...]

    def __len__(self) -> int:
        return len(self.points)

    @property
    def values(self) -> tuple[float, ...]:
        return tuple(p.y for p in self.points)


@dataclass(frozen=True)
class ForecastInterval:
    """One point on a forecast curve with a symmetric PI."""

    ds: str
    yhat: float
    yhat_lower: float
    yhat_upper: float


@dataclass(frozen=True)
class ForecastResult:
    """Structured output of a `ForecastModel.predict` call.

    Mirrors the shape the backend `ForecastResponse` expects per
    scenario, so the translation layer between `ml.forecasting` and
    the FastAPI schema is a thin field rename — same posture as the
    pricing-side translation (`ml_translation.py`, TASK-011).
    """

    series_id: str
    horizon_days: int
    points: tuple[ForecastInterval, ...]
    end_value: float
    cumulative_value: float
    mape: float | None = None
    model_name: str = ""
    sub_scores: dict[str, float] = field(default_factory=dict)
    rationale: str = ""
