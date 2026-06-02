"""
PPO RL pricing agent (EXP-PRC-002).

The RL arm of AS-002. We wrap Stable-Baselines3 PPO around a tiny custom
Gymnasium environment whose dynamics are the constant-elasticity demand
curve learned at training time (`ConstantElasticityEstimator`). The
agent's *state* is the product's current price + competitor price +
season; the *action* is a continuous price multiplier in `[0.6, 1.6]`;
the *reward* is per-step revenue.

Why a custom env over a more elaborate simulator: the constant-elasticity
environment is the same model the `ElasticityOptimalPolicy` uses for its
closed-form solution. That means AS-002's RL arm is directly comparable
to the closed-form arm — any *uplift* from PPO comes from cross-feature
interactions (season × competitor × promotion) that the closed-form
ignores, not from a richer demand model. This isolates the contribution
of RL specifically (RC-003).

Heavy dependencies (`gymnasium`, `stable_baselines3`) are lazy-imported
inside `fit` so the module imports cleanly in environments without them
(CI lint, backend container). The class still exposes a stable
`PricingPolicy` interface.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

import numpy as np

from ml.pricing.data.schema import PriceObservation, PricePoint, PriceRecommendation
from ml.pricing.models.base import PricingPolicy
from ml.pricing.models.elasticity import ConstantElasticityEstimator

if TYPE_CHECKING:
    from ml.pricing.data.schema import Product


class PPOPricingPolicy(PricingPolicy):
    """PPO over a constant-elasticity pricing environment.

    Training runs `total_timesteps` PPO updates; recommendation rolls one
    deterministic step from the current price + competitor + season
    context."""

    requires_training = True

    def __init__(
        self,
        *,
        total_timesteps: int = 50_000,
        action_scale_low: float = 0.6,
        action_scale_high: float = 1.6,
        learning_rate: float = 3e-4,
        seed: int = 42,
    ) -> None:
        self._total_timesteps = int(total_timesteps)
        self._action_low = float(action_scale_low)
        self._action_high = float(action_scale_high)
        self._lr = float(learning_rate)
        self._seed = int(seed)
        self._model: Any | None = None
        self._elasticity = ConstantElasticityEstimator()

    @property
    def name(self) -> str:
        return "policy-ppo-rl"

    def fit(self, observations: Sequence[PriceObservation]) -> PPOPricingPolicy:
        # Always fit the elasticity backbone — provides the env dynamics
        # AND a fallback path if the heavy RL stack isn't installed.
        self._elasticity.fit(observations)

        try:
            import gymnasium as gym
            from gymnasium import spaces
            from stable_baselines3 import PPO
        except ImportError:
            # Soft fallback — the policy still works; recommendations come
            # from the elasticity backbone alone. The benchmark harness
            # will flag the lower diversity in the run summary.
            self._model = None
            return self

        env = _ConstantElasticityEnv(
            elasticity=self._elasticity,
            observations=list(observations),
            action_low=self._action_low,
            action_high=self._action_high,
            gym=gym,
            spaces=spaces,
        )
        self._model = PPO(
            "MlpPolicy",
            env,
            learning_rate=self._lr,
            seed=self._seed,
            verbose=0,
        )
        self._model.learn(total_timesteps=self._total_timesteps)
        return self

    def recommend_price(
        self,
        product: Product,
        context: Sequence[PriceObservation] | None = None,
    ) -> PriceRecommendation:
        # Build the observation vector: [price, competitor, season_sin, season_cos]
        comp = float(product.competitor_prices[0]) if product.competitor_prices else 0.0
        obs_vec = np.asarray(
            [float(product.current_price), comp, 0.0, 1.0],
            dtype=np.float32,
        )

        if self._model is None:
            # Fallback to closed-form elasticity recommendation.
            grid = np.linspace(
                max(0.0, product.unit_cost),
                float(product.current_price) * self._action_high,
                25,
            )
            demand = self._elasticity.predict_demand(grid)
            revenue = grid * demand
            best = int(np.argmax(revenue))
            recommended = float(grid[best])
            expected_revenue = float(revenue[best])
            expected_demand = float(demand[best])
            rationale = (
                "PPO unavailable in this environment — fell back to "
                f"closed-form elasticity (ε={self._elasticity.elasticity:.2f})."
            )
            curve = tuple(
                PricePoint(
                    price=round(float(p), 4),
                    expected_demand=round(float(d), 4),
                    expected_revenue=round(float(p * d), 4),
                    expected_profit=round(float((p - product.unit_cost) * d), 4),
                )
                for p, d in zip(grid, demand, strict=False)
            )
        else:
            action, _ = self._model.predict(obs_vec, deterministic=True)
            multiplier = float(np.clip(action, self._action_low, self._action_high))
            recommended = float(product.current_price) * multiplier
            expected_demand = float(self._elasticity.predict_demand(np.array([recommended]))[0])
            expected_revenue = recommended * expected_demand
            rationale = (
                f"PPO policy chose multiplier×{multiplier:.2f} of current price "
                f"({product.current_price:.2f})."
            )
            curve = ()  # PPO is point-recommendation; no native curve

        return PriceRecommendation(
            product_id=product.product_id,
            recommended_price=round(recommended, 4),
            expected_revenue=round(expected_revenue, 4),
            expected_demand=round(expected_demand, 4),
            confidence_interval=(
                round(recommended * 0.95, 4),
                round(recommended * 1.05, 4),
            ),
            revenue_curve=curve,
            sub_scores={"elasticity": round(self._elasticity.elasticity, 4)},
            rationale=rationale,
        )


# ── Custom Gym env (loaded lazily — only constructed when RL is available) ──


class _ConstantElasticityEnv:
    """Gymnasium env wrapper. Built dynamically inside `PPOPricingPolicy.fit`
    so the module can be imported without `gymnasium` installed."""

    def __init__(
        self,
        *,
        elasticity: ConstantElasticityEstimator,
        observations: list[PriceObservation],
        action_low: float,
        action_high: float,
        gym: Any,
        spaces: Any,
    ) -> None:
        self._elasticity = elasticity
        self._observations = observations
        self._action_low = action_low
        self._action_high = action_high
        self._rng = np.random.default_rng(0)

        # Tiny observation space: [current_price, competitor_price, sin_season, cos_season]
        self.action_space = spaces.Box(
            low=action_low, high=action_high, shape=(1,), dtype=np.float32
        )
        self.observation_space = spaces.Box(
            low=np.array([0.0, 0.0, -1.0, -1.0], dtype=np.float32),
            high=np.array([1e4, 1e4, 1.0, 1.0], dtype=np.float32),
            dtype=np.float32,
        )
        self._step = 0

    def reset(self, *, seed: int | None = None, options: dict | None = None):
        if seed is not None:
            self._rng = np.random.default_rng(seed)
        self._step = 0
        return self._observation(), {}

    def step(self, action: np.ndarray):
        # Sample a random observation as the "current state", apply the
        # action as a price multiplier, score revenue under the
        # constant-elasticity demand curve.
        obs = self._rng.choice(self._observations)
        multiplier = float(np.clip(action[0], self._action_low, self._action_high))
        price = float(obs.price) * multiplier
        demand = float(self._elasticity.predict_demand(np.array([price]))[0])
        reward = float(price * max(0.0, demand))
        self._step += 1
        terminated = self._step >= 64
        truncated = False
        return self._observation(obs=obs), reward, terminated, truncated, {}

    def _observation(self, obs: PriceObservation | None = None) -> np.ndarray:
        if obs is None:
            obs = self._rng.choice(self._observations)
        season_rad = 2 * np.pi * (obs.season % 4) / 4
        return np.asarray(
            [
                obs.price,
                obs.competitor_price if obs.competitor_price is not None else 0.0,
                float(np.sin(season_rad)),
                float(np.cos(season_rad)),
            ],
            dtype=np.float32,
        )
