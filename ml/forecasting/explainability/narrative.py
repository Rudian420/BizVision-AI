"""
Deterministic narrative generator for forecast results.

Same role as the recruitment / pricing narrative adapters: produce a
plain-language interpretation that the backend can persist into the
`interpretation` column without an LLM call. The copilot
(`copilot/forecast_copilot.py`) is the LLM-powered upgrade for the
report-style summary; this is the low-latency one used per request.
"""

from __future__ import annotations

import numpy as np

from ml.forecasting.data.schema import ForecastResult, TimeSeriesDataset


def narrate(result: ForecastResult, history: TimeSeriesDataset) -> str:
    """Return a 1-3 sentence narrative for a single forecast.

    Composes three signals:
      1. trend direction (up / flat / down) from the linear fit
      2. magnitude of the end-of-horizon move vs the last observed value
      3. PI width (relative to the point forecast) as an uncertainty cue
    """
    history_values = np.array(history.values, dtype=np.float64)
    last = float(history_values[-1])
    end = result.end_value

    if last <= 0:
        delta_pct = 0.0
    else:
        delta_pct = (end - last) / last

    if abs(delta_pct) < 0.01:
        direction = "is broadly flat"
    elif delta_pct > 0:
        direction = f"rises {delta_pct:.1%}"
    else:
        direction = f"falls {abs(delta_pct):.1%}"

    last_point = result.points[-1]
    band = (last_point.yhat_upper - last_point.yhat_lower) / 2.0
    width_pct = band / abs(end) if end != 0 else 0.0
    if width_pct < 0.05:
        uncertainty = "with tight uncertainty"
    elif width_pct < 0.15:
        uncertainty = "with moderate uncertainty"
    else:
        uncertainty = "with wide uncertainty"

    return (
        f"{result.model_name} forecasts the next {result.horizon_days} "
        f"days: the series {direction} to ~{end:,.0f} {uncertainty} "
        f"(±{band:,.0f})."
    )
