/**
 * Shared SHAP feature type — used by every module that returns
 * per-prediction feature attributions.
 *
 * Mirrors the backend's `src.api.v1.schemas.common.SHAPFeature`.
 * The recruitment module has its own `SHAPFeatureAttribution` shape
 * (extends with `importance_rank`); recruitment's adapter converts
 * to this shared shape at the panel boundary.
 */
export type SHAPFeature = {
  feature_name: string;
  shap_value: number;
  feature_value: string | number;
  contribution_direction: 'positive' | 'negative';
  importance_rank: number;
};
