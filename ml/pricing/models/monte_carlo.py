"""
Revenue Monte Carlo simulator.

Given a `MonteCarloConfig` (candidate_price, unit_cost, demand mean +
std, num_trials), simulates demand draws from a clipped Gaussian and
reports the revenue + profit distribution: P5/P50/P95, Value-at-Risk at
5%, probability of profit, a coarse histogram.

Pure numpy, fully reproducible (seeded). Used by:
  • the API's `/pricing/simulate` endpoint (mocked today via
    `backend/src/services/pricing/pricing_service.py:run_monte_carlo`;
    real path swap is one line);
  • the recruiter copilot for "what if we charge $X?" follow-ups;
  • the ablation's revenue-uncertainty axis (RC-003) — every recommended
    price gets an MC distribution attached so we can compare policies by
    *risk-adjusted* revenue, not just point estimate.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ml.pricing.data.schema import MonteCarloConfig


@dataclass(frozen=True)
class MonteCarloResult:
    """Structured Monte Carlo result. Mirrors the API response schema."""

    product_id: str
    candidate_price: float
    num_trials: int
    mean_revenue: float
    revenue_p5: float
    revenue_p50: float
    revenue_p95: float
    value_at_risk_5pct: float
    probability_of_profit: float
    histogram: tuple[dict[str, float], ...]
    mean_profit: float


class MonteCarloSimulator:
    """Revenue/profit Monte Carlo under a Gaussian demand assumption.

    The Gaussian is clipped at 0 (demand can't go negative). For SME
    workloads this matches the API mock behaviour today; we can swap to a
    Poisson/log-normal draw in a future iteration without changing the
    return shape.
    """

    def __init__(self, *, n_bins: int = 20) -> None:
        self._n_bins = max(2, int(n_bins))

    def simulate(self, config: MonteCarloConfig) -> MonteCarloResult:
        rng = np.random.default_rng(config.seed)
        demand_draws = rng.normal(
            loc=config.demand_mean,
            scale=max(1e-9, config.demand_std),
            size=int(config.num_trials),
        )
        demand_draws = np.maximum(demand_draws, 0.0)

        revenue = demand_draws * float(config.candidate_price)
        profit = (float(config.candidate_price) - float(config.unit_cost)) * demand_draws

        p5, p50, p95 = np.percentile(revenue, [5, 50, 95])
        mean_rev = float(revenue.mean())
        mean_prof = float(profit.mean())
        var5 = float(mean_rev - p5)  # downside vs the mean at 5% tail
        prob_profit = float((profit > 0).mean())

        # Coarse histogram for the API response (no Plot in the package).
        counts, edges = np.histogram(revenue, bins=self._n_bins)
        histogram = tuple(
            {
                "bin_low": round(float(edges[i]), 4),
                "bin_high": round(float(edges[i + 1]), 4),
                "count": int(counts[i]),
            }
            for i in range(self._n_bins)
        )

        return MonteCarloResult(
            product_id=config.product_id,
            candidate_price=float(config.candidate_price),
            num_trials=int(config.num_trials),
            mean_revenue=round(mean_rev, 4),
            revenue_p5=round(float(p5), 4),
            revenue_p50=round(float(p50), 4),
            revenue_p95=round(float(p95), 4),
            value_at_risk_5pct=round(var5, 4),
            probability_of_profit=round(prob_profit, 4),
            histogram=histogram,
            mean_profit=round(mean_prof, 4),
        )
