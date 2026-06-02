"""
Multi-label logistic regression — one independent classifier per pillar.

Hand-implemented in pure numpy so the package has no sklearn dependency
(same constraint as `ml.pricing` and `ml.forecasting`). Optimisation is
gradient descent with L2 regularisation on the cross-entropy loss; the
gradient and loss are derived from the standard logistic-regression
formulas, so the test suite can verify each against a hand-worked
example.

The 3 pillar heads are *independent*: P(E_strong | x) ⊥ P(S_strong | x)
| x. This is the standard binary-relevance baseline for multi-label
classification (Tsoumakas & Katakis 2007) — it's an honest baseline
that we explicitly beat in the AS-004 ablation report. Joint
chained-classifier and label-powerset arms join in a later wave.

`top_features` for the `ESGScoreResult` is derived from the per-pillar
weight magnitudes — a closed-form SHAP analogue for linear models
(`shap_value_i = w_i · x_i` for a linear logistic head). This is the
linear-model special case that `explainability/shap_adapter.py`
expands on.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from ml.sustainability.data.schema import (
    CompanyProfile,
    ESGObservation,
    ESGScoreResult,
    PillarScore,
)
from ml.sustainability.features.structured import (
    FEATURE_NAMES,
    featurize,
    featurize_batch,
    labels_to_matrix,
)
from ml.sustainability.models.base import ESGScorer
from ml.sustainability.models.baselines import _risk_level


def _sigmoid(z: np.ndarray) -> np.ndarray:
    # Numerically stable sigmoid — avoids overflow for large |z|.
    out = np.empty_like(z, dtype=np.float64)
    pos = z >= 0
    out[pos] = 1.0 / (1.0 + np.exp(-z[pos]))
    expz = np.exp(z[~pos])
    out[~pos] = expz / (1.0 + expz)
    return out


def _fit_logistic_head(
    X: np.ndarray,
    y: np.ndarray,
    *,
    lr: float,
    n_iters: int,
    l2: float,
) -> tuple[np.ndarray, float]:
    """Fit one binary head. Returns (weights, bias).

    Pure batch gradient descent — small synthetic dataset means N·D
    iterations are fast; SGD's variance trade-off isn't worth it here.
    """
    n, d = X.shape
    w = np.zeros(d, dtype=np.float64)
    b = 0.0
    for _ in range(n_iters):
        z = X @ w + b
        p = _sigmoid(z)
        err = p - y
        grad_w = X.T @ err / n + l2 * w
        grad_b = float(err.mean())
        w -= lr * grad_w
        b -= lr * grad_b
    return w, b


class LinearLogisticMultiLabel(ESGScorer):
    """Binary-relevance logistic regression — one head per pillar.

    Features are z-standardised (per-column mean / std) inside the
    classifier before gradient descent — without this the
    `revenue_per_head` feature (scale ~1e5) dominates the gradient and
    every other coefficient gets crushed. Standardisation stats are
    captured at `fit` time and re-applied at `score` time so a fresh
    profile sees the same transform.
    """

    def __init__(
        self,
        *,
        learning_rate: float = 0.3,
        n_iterations: int = 500,
        l2_penalty: float = 1e-4,
    ) -> None:
        self.learning_rate = learning_rate
        self.n_iterations = n_iterations
        self.l2_penalty = l2_penalty
        # Per-pillar (weights, bias) — populated by `fit`.
        self._heads: list[tuple[np.ndarray, float]] = []
        # Per-column standardisation stats — populated by `fit`.
        self._feature_mean: np.ndarray = np.zeros(len(FEATURE_NAMES))
        self._feature_std: np.ndarray = np.ones(len(FEATURE_NAMES))
        # Cache the global pillar means so the score's headline value
        # is well-defined even when label_probabilities are all 0/1.
        self._global_pillar_mean: np.ndarray = np.array([0.5, 0.5, 0.5])
        # TASK-047: stash a small slice of the training pool so the
        # LIME adapter has a background for its perturbation
        # distribution. `score()` lazily builds the explainer and
        # caches it. Capped to keep memory bounded under repeated fits.
        self._lime_background_pool: list[Any] = []
        self._lime_explainer_cache: Any | None = None

    @property
    def name(self) -> str:
        return "LinearLogisticMultiLabel"

    def _standardise(self, X: np.ndarray) -> np.ndarray:
        # std==0 columns (e.g., a constant feature) divide by 1 to leave them at 0.
        return (X - self._feature_mean) / np.where(self._feature_std > 0, self._feature_std, 1.0)

    def fit(self, observations: Sequence[ESGObservation]) -> LinearLogisticMultiLabel:
        if not observations:
            self._heads = [
                (np.zeros(len(FEATURE_NAMES)), 0.0) for _ in range(3)
            ]
            return self
        X_raw = featurize_batch([obs.profile for obs in observations])
        Y = labels_to_matrix(observations)

        # Capture per-column standardisation stats from the training pool.
        self._feature_mean = X_raw.mean(axis=0)
        self._feature_std = X_raw.std(axis=0)
        X = self._standardise(X_raw)

        self._heads = []
        for k in range(3):
            w, b = _fit_logistic_head(
                X,
                Y[:, k].astype(np.float64),
                lr=self.learning_rate,
                n_iters=self.n_iterations,
                l2=self.l2_penalty,
            )
            self._heads.append((w, b))
        # Per-pillar mean — cached for the pillar-score headline.
        pillar_rows = np.array(
            [
                (
                    _safe_mean(obs.profile.environmental_indicators),
                    _safe_mean(obs.profile.social_indicators),
                    _safe_mean(obs.profile.governance_indicators),
                )
                for obs in observations
            ],
            dtype=np.float64,
        )
        self._global_pillar_mean = pillar_rows.mean(axis=0)
        # Stash up to 256 profiles for LIME perturbation background
        # (matches the SHAP adapter's recommended sample size — see
        # shap_adapter.shap_values_for_pillar).
        self._lime_background_pool = [obs.profile for obs in observations[:256]]
        self._lime_explainer_cache = None
        return self

    def score(self, profile: CompanyProfile) -> ESGScoreResult:
        if not self._heads:
            raise RuntimeError("fit() must be called before score()")
        x_raw = featurize(profile)
        x = self._standardise(x_raw[np.newaxis, :])[0]
        probs = np.empty(3, dtype=np.float64)
        for k, (w, b) in enumerate(self._heads):
            probs[k] = float(_sigmoid(np.array([x @ w + b]))[0])

        # Map per-pillar prob → 0..100 pillar score by blending with the
        # raw indicator mean. Honest framing: prob alone is binary, the
        # raw mean carries continuous information; we average so the
        # headline number tracks both.
        raw_pillars = np.array(
            [
                _safe_mean(profile.environmental_indicators),
                _safe_mean(profile.social_indicators),
                _safe_mean(profile.governance_indicators),
            ],
            dtype=np.float64,
        )
        blended = 0.5 * (probs + raw_pillars)
        pillars = PillarScore(
            environmental=float(np.clip(blended[0] * 100.0, 0.0, 100.0)),
            social=float(np.clip(blended[1] * 100.0, 0.0, 100.0)),
            governance=float(np.clip(blended[2] * 100.0, 0.0, 100.0)),
        )

        # Linear-SHAP: top features by |w_i · x_i| over the environmental
        # head (the highest-weighted pillar in most fits — the others
        # are symmetric). Operates on the standardised feature vector
        # so contributions are comparable across features of vastly
        # different raw scales.
        env_w, env_b = self._heads[0]
        contributions = env_w * x
        top_idx = np.argsort(-np.abs(contributions))[:3]
        top_features = tuple(
            (FEATURE_NAMES[int(i)], float(contributions[int(i)])) for i in top_idx
        )

        # LIME: independent second-explainer view of the same env
        # head (TASK-047 / FE-016 wave 2). Renders side-by-side with
        # SHAP in the UI — agreement on the top driver is a
        # defensibility signal; disagreement flags an
        # explainer-divergence surface for the user.
        lime_attributions = self._lime_top_features(profile, top_k=3)

        return ESGScoreResult(
            company_name=profile.company_name,
            industry=profile.industry,
            pillar_scores=pillars,
            risk_level=_risk_level(pillars.composite),
            industry_percentile=round(min(99.0, pillars.composite + 5.0), 1),
            label_probabilities={
                "env_strong": float(probs[0]),
                "soc_strong": float(probs[1]),
                "gov_strong": float(probs[2]),
            },
            top_features=top_features,
            lime_attributions=lime_attributions,
            model_name=self.name,
            rationale=(
                f"Linear logistic — composite {pillars.composite:.1f}, "
                f"E_prob={probs[0]:.2f}, S_prob={probs[1]:.2f}, G_prob={probs[2]:.2f}."
            ),
        )

    def _lime_top_features(
        self, profile: CompanyProfile, *, top_k: int
    ) -> tuple[tuple[str, float], ...]:
        """Compute the top-`k` LIME attributions for the env head.

        Returns `()` if no background pool was captured at fit time
        (the model wasn't trained), or if the LIME backend isn't
        importable, or if the explanation fails. The downstream
        translator emits an empty `top_lime_features` list in any of
        those cases — same UX as TASK-044's pricing path."""
        if not self._lime_background_pool:
            return ()
        try:
            from ml.sustainability.explainability.lime_adapter import (
                SustainabilityLIMEExplainer,
                top_k_lime_features,
            )

            if self._lime_explainer_cache is None:
                self._lime_explainer_cache = SustainabilityLIMEExplainer(
                    self,
                    background=self._lime_background_pool,
                    pillar="environmental",
                )
            attribution = self._lime_explainer_cache.explain(profile)
            weights_by_name = {
                name: float(val)
                for name, val in zip(FEATURE_NAMES, attribution.weights, strict=False)
            }
            return top_k_lime_features(weights_by_name, k=top_k)
        except Exception:  # pragma: no cover - defensive
            import logging

            logging.getLogger(__name__).info(
                "SustainabilityLIMEExplainer.explain failed; "
                "returning empty lime_attributions",
                exc_info=True,
            )
            return ()

    # ── introspection (for AS-004 reports + SHAP adapter) ─────────
    def weights_per_pillar(self) -> dict[str, np.ndarray]:
        """Return the fitted weight vectors keyed by pillar name."""
        if not self._heads:
            raise RuntimeError("fit() must be called first")
        return {
            "environmental": self._heads[0][0].copy(),
            "social": self._heads[1][0].copy(),
            "governance": self._heads[2][0].copy(),
        }

    def biases_per_pillar(self) -> dict[str, float]:
        if not self._heads:
            raise RuntimeError("fit() must be called first")
        return {
            "environmental": self._heads[0][1],
            "social": self._heads[1][1],
            "governance": self._heads[2][1],
        }


def _safe_mean(d: dict[str, float]) -> float:
    if not d:
        return 0.5
    return float(np.mean(list(d.values())))
