"""
BizVision AI — Synthetic Data Generators

Deterministic (seeded) generators producing privacy-safe training data for each
module. Used for development, CI, and ablation baselines until real/partner data
is integrated. No personally identifiable information is ever produced.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

_RNG_SEED = 42


def _rng(seed: int | None = None) -> np.random.Generator:
    return np.random.default_rng(_RNG_SEED if seed is None else seed)


def generate_recruitment(n: int = 2000, seed: int | None = None) -> pd.DataFrame:
    """Candidate features + a (synthetic) hire label with injected, auditable bias."""
    rng = _rng(seed)
    years = rng.gamma(shape=2.0, scale=3.0, size=n).round(1)
    skill_match = rng.beta(2, 2, size=n)
    education = rng.integers(0, 4, size=n)  # 0=HS .. 3=PhD
    gender = rng.integers(0, 2, size=n)  # protected attribute
    # True signal + a small, deliberate proxy bias for fairness experiments.
    logit = 1.6 * skill_match + 0.12 * years + 0.2 * education - 1.5 + 0.15 * gender
    prob = 1 / (1 + np.exp(-logit))
    hired = (rng.random(n) < prob).astype(int)
    return pd.DataFrame(
        {
            "years_experience": years,
            "skill_match": skill_match.round(4),
            "education_level": education,
            "gender": gender,
            "hired": hired,
        }
    )


def generate_pricing(n: int = 3000, seed: int | None = None) -> pd.DataFrame:
    """Price/demand observations following a constant-elasticity curve + noise."""
    rng = _rng(seed)
    base_price = rng.uniform(10, 200, size=n)
    elasticity = rng.uniform(-2.5, -0.5, size=n)
    competitor = base_price * rng.uniform(0.8, 1.2, size=n)
    season = rng.integers(0, 4, size=n)
    base_demand = rng.uniform(50, 500, size=n)
    demand = base_demand * (competitor / base_price) ** (-elasticity)
    demand *= 1 + 0.05 * season + rng.normal(0, 0.05, size=n)
    return pd.DataFrame(
        {
            "price": base_price.round(2),
            "competitor_price": competitor.round(2),
            "season": season,
            "elasticity": elasticity.round(3),
            "demand": demand.clip(min=0).round(2),
        }
    )


def generate_forecasting(days: int = 720, seed: int | None = None) -> pd.DataFrame:
    """Daily profit time series with trend + weekly/yearly seasonality + noise."""
    rng = _rng(seed)
    t = np.arange(days)
    trend = 1000 + 2.5 * t
    weekly = 80 * np.sin(2 * np.pi * t / 7)
    yearly = 300 * np.sin(2 * np.pi * t / 365)
    noise = rng.normal(0, 50, size=days)
    y = trend + weekly + yearly + noise
    ds = pd.date_range("2024-01-01", periods=days, freq="D")
    return pd.DataFrame({"ds": ds, "y": y.round(2)})


def generate_sustainability(n: int = 1500, seed: int | None = None) -> pd.DataFrame:
    """Firm-level ESG indicators with multi-label E/S/G outcomes."""
    rng = _rng(seed)
    env = rng.beta(2, 2, size=n)
    soc = rng.beta(2, 2, size=n)
    gov = rng.beta(2, 2, size=n)
    revenue = rng.lognormal(mean=14, sigma=1.0, size=n)
    employees = rng.integers(5, 500, size=n)
    return pd.DataFrame(
        {
            "annual_revenue": revenue.round(2),
            "employee_count": employees,
            "env_score": env.round(4),
            "soc_score": soc.round(4),
            "gov_score": gov.round(4),
            "label_env_strong": (env > 0.6).astype(int),
            "label_soc_strong": (soc > 0.6).astype(int),
            "label_gov_strong": (gov > 0.6).astype(int),
        }
    )


GENERATORS = {
    "recruitment": generate_recruitment,
    "pricing": generate_pricing,
    "forecasting": generate_forecasting,
    "sustainability": generate_sustainability,
}
