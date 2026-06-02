/**
 * Hand-written sustainability contract types.
 *
 * Mirror `backend/src/api/v1/schemas/sustainability.py`. Kept local
 * until the OpenAPI generator runs against the live backend — same
 * posture as the other module type files.
 */

import type { RiskLevel } from '@/lib/risk/types';
import type { SHAPFeature } from '@/lib/shap/types';

export type ESGScoreRequest = {
  company_name: string;
  industry: string;
  annual_revenue: number;
  employee_count: number;
  environmental_indicators?: Record<string, number>;
  social_indicators?: Record<string, number>;
  governance_indicators?: Record<string, number>;
};

export type ESGSubScores = {
  environmental: number;
  social: number;
  governance: number;
};

export type ESGScoreResponse = {
  assessment_id: string;
  company_name: string;
  industry: string;
  assessed_at: string;
  composite_score: number;
  sub_scores: ESGSubScores;
  risk_level: RiskLevel;
  industry_percentile: number;
  regulatory_risk_flag: boolean;
  top_shap_features: SHAPFeature[];
  /** Top-K LIME local linear surrogate weights for the same ESG
   * score (TASK-047 / FE-016 wave 2). Same shape as
   * `top_shap_features` so `<LimePanel>` can reuse the
   * `SHAPFeature` type. Empty when LIME wasn't computed (mock
   * scorer / explainer backend failure). */
  top_lime_features?: SHAPFeature[];
  model_version: string;
};

export type Pillar = 'environmental' | 'social' | 'governance';

/** ESG assessment types — polymorphic discriminator. */
export type SustainabilityAssessmentType =
  | 'score'
  | 'simulation'
  | 'recommendations'
  | 'carbon_estimate';

/** Summary row returned by `GET /sustainability/assessments` (paged, TASK-035). */
export type SustainabilityAssessmentHistoryItem = {
  assessment_id: string;
  assessment_type: SustainabilityAssessmentType;
  company_name: string | null;
  industry: string | null;
  composite_score: number | null;
  risk_level: RiskLevel | null;
  total_tco2e: number | null;
  model_version: string;
  created_at: string;
};

export type SustainabilityAssessmentsPage = {
  items: SustainabilityAssessmentHistoryItem[];
  total: number;
  page: number;
  page_size: number;
};

/** Persisted-row reconstruction returned by
 * `/sustainability/assessments/{id}` (TASK-033). */
export type SustainabilityAssessmentDetail = {
  assessment_id: string;
  assessment_type: SustainabilityAssessmentType;
  company_name: string | null;
  industry: string | null;
  created_at: string;
  model_version: string;
  processing_time_ms: number;
  composite_score: number | null;
  risk_level: RiskLevel | null;
  total_tco2e: number | null;
  interpretation: string | null;
  request_payload: Record<string, unknown>;
  response_payload: Record<string, unknown>;
};
