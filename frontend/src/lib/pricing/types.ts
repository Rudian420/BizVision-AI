/**
 * Hand-written pricing contract types.
 *
 * Mirror `backend/src/api/v1/schemas/pricing.py`. Kept local until
 * the OpenAPI generator runs against the live backend — same posture
 * as the recruitment and auth modules.
 */

import type { SHAPFeature } from '@/lib/shap/types';

export type PricingObjective = 'revenue' | 'profit' | 'volume';

export type PriceOptimizationRequest = {
  product_id: string;
  current_price: number;
  unit_cost: number;
  historical_demand?: number[];
  competitor_prices?: number[];
  min_price?: number | null;
  max_price?: number | null;
  objective?: PricingObjective;
};

export type PricePoint = {
  price: number;
  expected_demand: number;
  expected_revenue: number;
  expected_profit: number;
};

export type PriceOptimizationResponse = {
  analysis_id: string;
  product_id: string;
  analysis_timestamp: string;
  recommended_price: number;
  current_price: number;
  /** Fractional uplift, e.g. 0.12 = +12% */
  expected_revenue_uplift: number;
  /** [low, high] price band */
  confidence_interval: [number, number] | number[];
  revenue_curve: PricePoint[];
  top_shap_features: SHAPFeature[];
  /** Top-K LIME local linear surrogate weights for the same
   * recommendation (TASK-044 / FE-016). Same shape as
   * `top_shap_features` so `<LimePanel>` can reuse the
   * `SHAPFeature` type. Empty when LIME wasn't computed (mock path
   * or explainer failure). */
  top_lime_features?: SHAPFeature[];
  ai_rationale?: string;
  model_version: string;
};

/** Pricing analysis types — polymorphic discriminator. */
export type PricingAnalysisType =
  | 'optimize'
  | 'monte_carlo'
  | 'elasticity'
  | 'scenario_comparison';

/** Summary row returned by `GET /pricing/history` (paged). */
export type PricingHistoryItem = {
  analysis_id: string;
  analysis_type: PricingAnalysisType;
  product_id: string;
  recommended_price: number | null;
  expected_revenue_uplift: number | null;
  model_version: string;
  created_at: string;
};

export type PricingHistoryPage = {
  items: PricingHistoryItem[];
  total: number;
  page: number;
  page_size: number;
};

/** Persisted-row reconstruction returned by `/pricing/analyses/{id}` (TASK-033). */
export type PricingAnalysisDetail = {
  analysis_id: string;
  analysis_type: PricingAnalysisType;
  product_id: string;
  created_at: string;
  model_version: string;
  processing_time_ms: number;
  recommended_price: number | null;
  expected_revenue_uplift: number | null;
  num_trials_or_points: number | null;
  request_payload: Record<string, unknown>;
  response_payload: Record<string, unknown>;
};
