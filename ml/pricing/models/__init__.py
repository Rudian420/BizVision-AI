"""Pricing models — demand estimators + pricing policies + Monte Carlo.

The full taxonomy used in AS-002 (pricing ablation):

    Demand estimators
        ConstantElasticityEstimator  — closed-form log-log regression
        LightGBMDemandModel          — boosted trees (EXP-PRC-001)
    Pricing policies (the things actually benchmarked)
        ConstantPricePolicy          — keep `current_price` (sanity floor)
        CompetitorMatchPolicy        — match the lowest competitor price
        ElasticityOptimalPolicy      — closed-form revenue maximiser
        LightGBMGridPolicy           — grid search over LightGBM demand
        PPOPricingPolicy             — RL agent (EXP-PRC-002)
    Stochastic
        MonteCarloSimulator          — revenue distribution under demand noise

All policies implement `models.base.PricingPolicy`; all demand
estimators implement `models.base.DemandModel`. ADR-022's uniform-
interface principle applies here too — the ablation runner is generic
over any `PricingPolicy`.
"""

from ml.pricing.models.base import DemandModel, PricingPolicy
from ml.pricing.models.baselines import (
    CompetitorMatchPolicy,
    ConstantPricePolicy,
)
from ml.pricing.models.demand import LightGBMDemandModel, LightGBMGridPolicy
from ml.pricing.models.elasticity import (
    ConstantElasticityEstimator,
    ElasticityOptimalPolicy,
)
from ml.pricing.models.monte_carlo import MonteCarloResult, MonteCarloSimulator
from ml.pricing.models.rl_agent import PPOPricingPolicy

__all__ = [
    "CompetitorMatchPolicy",
    "ConstantElasticityEstimator",
    "ConstantPricePolicy",
    "DemandModel",
    "ElasticityOptimalPolicy",
    "LightGBMDemandModel",
    "LightGBMGridPolicy",
    "MonteCarloResult",
    "MonteCarloSimulator",
    "PPOPricingPolicy",
    "PricingPolicy",
]
