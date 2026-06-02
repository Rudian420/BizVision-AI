"""
BizVision AI — Unified SHAP Explainability Engine

Provides a consistent explainability interface across all 5 AI modules.
Each module uses the same SHAPEngine but with module-specific interpreters.

Research contribution: SHAP-attributed bias decomposition —
identifies WHICH features in the model drive demographic unfairness.
"""

from dataclasses import dataclass
from typing import Any

import numpy as np
import shap


@dataclass
class SHAPExplanation:
    """Structured output of a SHAP explanation."""

    feature_names: list[str]
    shap_values: np.ndarray  # Shape: (n_samples, n_features)
    base_value: float  # Model output when all features are at baseline
    expected_value: float  # Average prediction across training set

    # Derived
    mean_abs_shap: np.ndarray  # Global feature importance
    feature_ranking: list[str]  # Features sorted by importance

    # For waterfall plots
    sample_shap_values: np.ndarray | None = None  # Single-sample explanation
    sample_feature_values: np.ndarray | None = None

    # Narrative
    narrative: str = ""
    bias_attribution: dict | None = None  # Which features drive demographic bias


class SHAPEngine:
    """
    Unified SHAP explainability engine.

    Automatically selects the best SHAP explainer based on model type:
    - TreeExplainer: XGBoost, LightGBM, Random Forest (exact + fast)
    - DeepExplainer: PyTorch/TF neural networks (approximate)
    - KernelExplainer: Any model (slowest, model-agnostic)
    - LinearExplainer: Linear models (exact)
    """

    def __init__(self, model: Any, feature_names: list[str]):
        self.model = model
        self.feature_names = feature_names
        self.explainer = None
        self._explainer_type = None

    def _build_explainer(self, background_data: np.ndarray | None = None):
        """Automatically select and initialize the right SHAP explainer."""

        model_type = type(self.model).__name__

        if model_type in (
            "XGBClassifier",
            "XGBRegressor",
            "LGBMClassifier",
            "LGBMRegressor",
            "RandomForestClassifier",
            "RandomForestRegressor",
        ):
            self.explainer = shap.TreeExplainer(self.model)
            self._explainer_type = "tree"

        elif "torch" in str(type(self.model).__module__):
            if background_data is None:
                raise ValueError("DeepExplainer requires background_data")
            import torch

            self.explainer = shap.DeepExplainer(
                self.model, torch.tensor(background_data, dtype=torch.float32)
            )
            self._explainer_type = "deep"

        elif hasattr(self.model, "coef_"):
            # Linear model
            if background_data is None:
                raise ValueError("LinearExplainer requires background_data")
            self.explainer = shap.LinearExplainer(
                self.model,
                background_data,
            )
            self._explainer_type = "linear"

        else:
            # Fallback: KernelExplainer (model-agnostic but slow)
            if background_data is None:
                raise ValueError("KernelExplainer requires background_data")
            # Use K-means summary to speed up kernel explainer
            background_summary = shap.kmeans(background_data, 50)
            self.explainer = shap.KernelExplainer(
                self.model.predict_proba,
                background_summary,
            )
            self._explainer_type = "kernel"

    def explain(
        self,
        X: np.ndarray,
        background_data: np.ndarray | None = None,
        sample_index: int | None = None,
    ) -> SHAPExplanation:
        """
        Generate SHAP explanation for model predictions on X.

        Args:
            X: Input features to explain (shape: n_samples x n_features)
            background_data: Background dataset for approximation-based explainers
            sample_index: If provided, generate detailed single-sample explanation

        Returns:
            SHAPExplanation with all attribution data
        """
        if self.explainer is None:
            self._build_explainer(background_data)

        # Compute SHAP values
        raw_shap = self.explainer.shap_values(X)

        # Handle binary classification (returns list of 2 arrays)
        if isinstance(raw_shap, list):
            shap_values = raw_shap[1]  # Use positive class
        else:
            shap_values = raw_shap

        # Global feature importance
        mean_abs_shap = np.abs(shap_values).mean(axis=0)
        feature_ranking = [self.feature_names[i] for i in np.argsort(mean_abs_shap)[::-1]]

        # Base value
        base_value = (
            self.explainer.expected_value[1]
            if isinstance(self.explainer.expected_value, (list, np.ndarray))
            else self.explainer.expected_value
        )

        explanation = SHAPExplanation(
            feature_names=self.feature_names,
            shap_values=shap_values,
            base_value=float(base_value),
            expected_value=float(base_value),
            mean_abs_shap=mean_abs_shap,
            feature_ranking=feature_ranking,
        )

        # Single-sample waterfall explanation
        if sample_index is not None:
            explanation.sample_shap_values = shap_values[sample_index]
            explanation.sample_feature_values = X[sample_index]

        return explanation

    def attribute_bias(
        self,
        X: np.ndarray,
        protected_col_indices: list[int],
        shap_values: np.ndarray,
    ) -> dict:
        """
        SHAP-attributed bias decomposition.

        Novel research contribution: identifies which features
        act as proxies for protected attributes in the model.

        For each protected attribute, computes:
        - Direct influence: SHAP value of the attribute itself
        - Proxy influence: Correlation between other feature SHAP values
          and the protected attribute

        Returns:
            Dict mapping attribute names to bias attribution scores
        """
        results = {}

        for col_idx in protected_col_indices:
            attr_name = self.feature_names[col_idx]
            attr_values = X[:, col_idx]

            # Direct SHAP contribution of protected attribute
            direct_contribution = np.abs(shap_values[:, col_idx]).mean()

            # Proxy contributions: features correlated with protected attr
            proxy_contributions = {}
            for j, feat_name in enumerate(self.feature_names):
                if j == col_idx:
                    continue

                # Correlation between SHAP(feature_j) and protected_attr values
                correlation = np.corrcoef(shap_values[:, j], attr_values)[0, 1]
                if abs(correlation) > 0.1:  # Only significant correlations
                    proxy_contributions[feat_name] = float(correlation)

            results[attr_name] = {
                "direct_shap_contribution": float(direct_contribution),
                "proxy_features": dict(
                    sorted(proxy_contributions.items(), key=lambda x: abs(x[1]), reverse=True)[:5]
                ),
                "total_bias_exposure": float(
                    direct_contribution + sum(abs(v) for v in proxy_contributions.values()) * 0.3
                ),
            }

        return results

    def generate_narrative(
        self,
        explanation: SHAPExplanation,
        prediction_score: float,
        context: str = "ranking",
    ) -> str:
        """
        Generate plain-English narrative from SHAP explanation.
        For thesis purposes: tests whether AI can explain AI.

        In production, this can optionally call an LLM for richer narratives.
        """
        top_positive = [
            (self.feature_names[i], explanation.sample_shap_values[i])
            for i in range(len(self.feature_names))
            if explanation.sample_shap_values is not None and explanation.sample_shap_values[i] > 0
        ]
        top_positive.sort(key=lambda x: x[1], reverse=True)

        top_negative = [
            (self.feature_names[i], explanation.sample_shap_values[i])
            for i in range(len(self.feature_names))
            if explanation.sample_shap_values is not None and explanation.sample_shap_values[i] < 0
        ]
        top_negative.sort(key=lambda x: x[1])

        score_pct = int(prediction_score * 100)

        narrative_parts = [
            f"This candidate received a match score of {score_pct}%.",
            "",
        ]

        if top_positive:
            feat, val = top_positive[0]
            narrative_parts.append(
                f"The strongest positive factor was '{feat}', which increased the "
                f"score by {val:.3f} points — indicating strong alignment with the role requirements."
            )

        if len(top_positive) > 1:
            feat, val = top_positive[1]
            narrative_parts.append(f"Additionally, '{feat}' contributed positively (+{val:.3f}).")

        if top_negative:
            feat, val = top_negative[0]
            narrative_parts.append(
                f"The primary area of concern was '{feat}' ({val:.3f}), "
                f"suggesting a gap in this requirement."
            )

        return " ".join(narrative_parts)
