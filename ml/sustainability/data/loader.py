"""
Synthetic ESG dataset loader.

Generates deterministic per-company observations with:
  • realistic industry mix (5 industries)
  • indicator distributions skewed by industry
  • binary labels derived from industry-relative percentiles

Same posture as `ml.forecasting.data.loader` and `ml.pricing.data.loader`
— pure-numpy, no pandas / sklearn dependency, fed into the frozen
`ESGDataset` container.

The label generation is *not* simply `score > threshold` — that would
be trivially recovered by any model. Instead labels are noisy versions
of the industry-relative percentile, which forces models to learn
*per-industry* structure (matters for the fairness audit downstream:
disparate impact across industries must be measured against a label
distribution that isn't uniform).
"""

from __future__ import annotations

import numpy as np

from ml.sustainability.data.schema import (
    CompanyProfile,
    ESGDataset,
    ESGLabel,
    ESGObservation,
)

# 5-industry catalog used across the package — kept consistent with the
# backend mock's `_INDUSTRY_INTENSITY` keys so fairness audits can
# cross-reference both sides.
INDUSTRIES: tuple[str, ...] = (
    "manufacturing",
    "retail",
    "technology",
    "logistics",
    "agriculture",
)

# Industry-shifted means for the indicator dicts (0..1 scale).
_INDUSTRY_MEANS: dict[str, dict[str, float]] = {
    "manufacturing": {"e": 0.42, "s": 0.55, "g": 0.50},
    "retail": {"e": 0.55, "s": 0.60, "g": 0.55},
    "technology": {"e": 0.70, "s": 0.65, "g": 0.65},
    "logistics": {"e": 0.38, "s": 0.50, "g": 0.45},
    "agriculture": {"e": 0.48, "s": 0.55, "g": 0.40},
}

_INDICATOR_KEYS: dict[str, tuple[str, ...]] = {
    "e": ("energy_efficiency", "waste_diversion", "renewable_share", "scope3_reporting"),
    "s": ("dei_index", "labor_compliance", "community_impact", "employee_safety"),
    "g": ("board_independence", "transparency", "anticorruption", "stakeholder_engagement"),
}


def _draw_indicators(
    pillar: str, rng: np.random.Generator, industry: str
) -> dict[str, float]:
    """Sample one indicator dict for a single pillar."""
    mean = _INDUSTRY_MEANS[industry][pillar]
    keys = _INDICATOR_KEYS[pillar]
    raw = rng.normal(loc=mean, scale=0.10, size=len(keys))
    raw = np.clip(raw, 0.05, 0.98)
    return {k: float(v) for k, v in zip(keys, raw, strict=False)}


def _label_from_indicators(
    e_mean: float,
    s_mean: float,
    g_mean: float,
    industry: str,
    rng: np.random.Generator,
    industry_thresholds: dict[str, dict[str, float]],
) -> ESGLabel:
    """Binary labels = industry-percentile > 0.55 with 10% label noise.

    `industry_thresholds[ind][pillar]` is the 55th-percentile cutoff for
    that industry's training distribution — pre-computed once per draw.
    """
    flip_prob = 0.10
    e_strong = e_mean > industry_thresholds[industry]["e"]
    s_strong = s_mean > industry_thresholds[industry]["s"]
    g_strong = g_mean > industry_thresholds[industry]["g"]
    if rng.random() < flip_prob:
        e_strong = not e_strong
    if rng.random() < flip_prob:
        s_strong = not s_strong
    if rng.random() < flip_prob:
        g_strong = not g_strong
    return ESGLabel(
        company_id="placeholder",  # filled by caller
        env_strong=e_strong,
        soc_strong=s_strong,
        gov_strong=g_strong,
    )


def generate_synthetic_dataset(
    n_companies: int = 600,
    seed: int = 42,
) -> ESGDataset:
    """Produce a balanced synthetic ESG training pool.

    Companies are split roughly evenly across the five industries; for
    each industry the indicator distribution is shifted by its mean
    (technology firms score higher on environmental, manufacturing
    lower, etc.) so the multi-label classifier has *learnable*
    industry-conditional structure.
    """
    rng = np.random.default_rng(seed)

    # 1) Draw all indicator dicts so we can compute industry thresholds.
    industries_seq = [INDUSTRIES[i % len(INDUSTRIES)] for i in range(n_companies)]
    profiles: list[CompanyProfile] = []
    means_per_company: list[tuple[float, float, float]] = []
    for i, ind in enumerate(industries_seq):
        env_dict = _draw_indicators("e", rng, ind)
        soc_dict = _draw_indicators("s", rng, ind)
        gov_dict = _draw_indicators("g", rng, ind)
        revenue = float(rng.uniform(1_000_000, 50_000_000))
        headcount = int(rng.integers(5, 400))
        profile = CompanyProfile(
            company_name=f"company-{i:04d}",
            industry=ind,
            annual_revenue=revenue,
            employee_count=headcount,
            environmental_indicators=env_dict,
            social_indicators=soc_dict,
            governance_indicators=gov_dict,
        )
        profiles.append(profile)
        means_per_company.append(
            (
                float(np.mean(list(env_dict.values()))),
                float(np.mean(list(soc_dict.values()))),
                float(np.mean(list(gov_dict.values()))),
            )
        )

    # 2) Compute per-industry percentile thresholds (55th percentile).
    industry_thresholds: dict[str, dict[str, float]] = {}
    arr = np.array(means_per_company, dtype=np.float64)
    for ind in INDUSTRIES:
        mask = np.array([i == ind for i in industries_seq])
        if not mask.any():
            industry_thresholds[ind] = {"e": 0.5, "s": 0.5, "g": 0.5}
            continue
        sub = arr[mask]
        industry_thresholds[ind] = {
            "e": float(np.quantile(sub[:, 0], 0.55)),
            "s": float(np.quantile(sub[:, 1], 0.55)),
            "g": float(np.quantile(sub[:, 2], 0.55)),
        }

    # 3) Draw the labels using the thresholds.
    observations: list[ESGObservation] = []
    for i, (profile, (e_m, s_m, g_m)) in enumerate(
        zip(profiles, means_per_company, strict=False)
    ):
        raw_label = _label_from_indicators(
            e_m, s_m, g_m, profile.industry, rng, industry_thresholds
        )
        label = ESGLabel(
            company_id=profile.company_name,
            env_strong=raw_label.env_strong,
            soc_strong=raw_label.soc_strong,
            gov_strong=raw_label.gov_strong,
        )
        observations.append(ESGObservation(profile=profile, label=label))

    return ESGDataset(observations=tuple(observations), industries=INDUSTRIES)


def split_train_test(
    dataset: ESGDataset, test_fraction: float = 0.2, seed: int = 42
) -> tuple[ESGDataset, ESGDataset]:
    """Random shuffle + holdout split. Deterministic for a given seed."""
    if not (0.0 < test_fraction < 1.0):
        raise ValueError("test_fraction must be in (0, 1)")
    rng = np.random.default_rng(seed)
    idx = np.arange(len(dataset))
    rng.shuffle(idx)
    cut = int(len(dataset) * (1.0 - test_fraction))
    train_obs = tuple(dataset.observations[int(i)] for i in idx[:cut])
    test_obs = tuple(dataset.observations[int(i)] for i in idx[cut:])
    train = ESGDataset(observations=train_obs, industries=dataset.industries)
    test = ESGDataset(observations=test_obs, industries=dataset.industries)
    return train, test
