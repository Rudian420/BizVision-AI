"""
Linear-SHAP adapter for the multi-label classifier.

For a linear logistic model the SHAP value of feature `i` for prediction
`f(x) = sigmoid(w·x + b)` simplifies to the *linear contribution to the
log-odds*:

    shap_i(x) = w_i · (x_i - E[x_i])

(see Štrumbelj & Kononenko 2014, Lundberg & Lee 2017 §3.2). The expected
value `E[x_i]` is the training-pool feature mean — captured during
`shap_values_for_pillar` as a fresh batched mean over the supplied
background sample.

This is a closed-form special case; for non-linear arms (a future
gradient-boosted classifier) the `kernel_shap` Monte-Carlo path replaces
this without touching the call sites.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from ml.sustainability.data.schema import CompanyProfile
from ml.sustainability.features.structured import FEATURE_NAMES, featurize_batch
from ml.sustainability.models.multilabel import LinearLogisticMultiLabel


def shap_values_for_pillar(
    model: LinearLogisticMultiLabel,
    profile: CompanyProfile,
    *,
    pillar: str,
    background: Sequence[CompanyProfile],
) -> dict[str, float]:
    """Return per-feature SHAP values for the chosen pillar.

    `pillar` ∈ {"environmental", "social", "governance"}. `background`
    is the reference distribution for E[x] — typically the model's
    training pool sampled to ≤ 256 rows.
    """
    if pillar not in {"environmental", "social", "governance"}:
        raise ValueError(f"unknown pillar: {pillar!r}")

    # The model's weights live in the *standardised* feature space, so
    # the SHAP attribution must too. Standardise the input + background
    # using the model's captured fit-time stats; then the closed-form
    # linear-SHAP contribution is `w_i · (x_std_i - E_background[x_std_i])`.
    # With the background drawn from the model's training pool,
    # E[x_std_i] ≈ 0, so this collapses to `w_i · x_std_i`.
    weights = model.weights_per_pillar()[pillar]
    x_raw = featurize_batch([profile])[0]
    x_std = model._standardise(x_raw[np.newaxis, :])[0]
    if not background:
        mean_std = np.zeros(len(FEATURE_NAMES), dtype=np.float64)
    else:
        bg_X_raw = featurize_batch(list(background))
        bg_X_std = model._standardise(bg_X_raw)
        mean_std = bg_X_std.mean(axis=0)
    contributions = weights * (x_std - mean_std)
    return {name: float(val) for name, val in zip(FEATURE_NAMES, contributions, strict=False)}


def top_k_shap_features(
    shap: dict[str, float], k: int = 3
) -> tuple[tuple[str, float], ...]:
    """Return the top-k features by absolute SHAP magnitude."""
    items = sorted(shap.items(), key=lambda kv: -abs(kv[1]))
    return tuple(items[:k])
