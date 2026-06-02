/**
 * Hand-written recruitment contract types.
 *
 * Mirror `backend/src/api/v1/schemas/recruitment.py`. Kept local until
 * the OpenAPI generator runs against the live backend — same posture
 * as `lib/auth/types.ts`.
 */

export type ExperienceLevel = 'entry' | 'mid' | 'senior' | 'lead' | 'executive';
export type RiskLevel = 'low' | 'medium' | 'high' | 'critical';

export type JobDescriptionInput = {
  title: string;
  description: string;
  required_skills?: string[];
  preferred_skills?: string[];
  experience_level?: ExperienceLevel;
  min_years_experience?: number | null;
  max_years_experience?: number | null;
  location?: string | null;
  remote_allowed?: boolean;
  department?: string | null;
};

export type CandidateInput = {
  candidate_id: string;
  cv_text?: string | null;
  cv_file_id?: string | null;
  name?: string | null;
};

export type RecruitmentAnalysisRequest = {
  job_description: JobDescriptionInput;
  candidates: CandidateInput[];
  anonymize_names?: boolean;
  protected_attributes?: string[];
  top_k?: number;
  ensemble_sbert_weight?: number;
};

export type SHAPFeatureAttribution = {
  feature_name: string;
  shap_value: number;
  feature_value: string | number;
  contribution_direction: 'positive' | 'negative';
  importance_rank: number;
};

export type CandidateRankingResult = {
  rank: number;
  candidate_id: string;
  display_name?: string | null;
  composite_score: number;
  semantic_score: number;
  structured_score: number;
  confidence_level: number;
  years_experience?: number | null;
  matched_skills?: string[];
  missing_skills?: string[];
  education_level?: string | null;
  top_shap_features?: SHAPFeatureAttribution[];
  /** Top-K LIME local linear surrogate weights for this candidate
   * (TASK-048 / FE-016 wave 3). Same shape as
   * `top_shap_features` so `<LimePanel>` can reuse the
   * `SHAPFeatureAttribution` type. Feature names from LIME's
   * discretised classifier mode include threshold expressions
   * (e.g. `"years_experience > 5"`), not bare names — that's how
   * LIME phrases per-rule attributions for tree models. Empty
   * when LIME wasn't computed (real-ML path before the explainer
   * singleton is wired). */
  top_lime_features?: SHAPFeatureAttribution[];
  ai_rationale?: string;
};

export type FairnessMetric = {
  attribute: string;
  metric_name: string;
  value: number;
  threshold: number;
  passed: boolean;
  interpretation: string;
};

export type FairnessAuditSummary = {
  overall_risk_level: RiskLevel;
  total_candidates_audited: number;
  fairness_metrics: FairnessMetric[];
  recommendations: string[];
  audit_timestamp: string;
};

/** Per-session fairness audit returned by `GET /recruitment/fairness/{id}`.
 * Different shape from `FairnessAuditSummary` (which is embedded in the
 * `/analyze` response) — this is the persisted-row reconstruction. */
export type FairnessAuditResponse = {
  session_id: string;
  audit_timestamp: string;
  protected_attributes: string[];
  metrics: FairnessMetric[];
  bias_heatmap_data: Record<string, unknown>;
  mitigation_strategies: Array<Record<string, unknown>>;
  overall_risk_level: RiskLevel;
  model_card_url: string | null;
};

export type RecruitmentAnalysisResponse = {
  session_id: string;
  job_title: string;
  analysis_timestamp: string;
  total_candidates: number;
  processing_time_ms: number;
  ranked_candidates: CandidateRankingResult[];
  fairness_audit: FairnessAuditSummary;
  model_version: string;
  sbert_model: string;
  ensemble_weights: Record<string, number>;
  context_signal_id?: string | null;
};

/** Single-session summary returned by the paged `/sessions` list. */
export type RecruitmentSessionSummary = {
  session_id: string;
  job_title: string;
  total_candidates: number;
  model_version: string;
  created_at: string;
};

export type RecruitmentSessionsPage = {
  items: RecruitmentSessionSummary[];
  total: number;
  page: number;
  page_size: number;
};

/** Persisted-session detail returned by `/sessions/{id}` (TASK-032).
 * Mirrors `backend.api.v1.schemas.recruitment.RecruitmentSessionDetailResponse`. */
export type RecruitmentSessionDetail = {
  session_id: string;
  job_title: string;
  job_description: string;
  created_at: string;
  total_candidates: number;
  top_k: number;
  anonymize_names: boolean;
  protected_attributes: string[];
  ranked_candidates: CandidateRankingResult[];
  model_version: string;
  sbert_model: string;
  ensemble_weights: Record<string, number>;
};

/** One parsed CV from the `/recruitment/upload-cvs` batch (TASK-045 /
 * ML-003 on the backend; TASK-046 / FE-022 here on the FE). `cv_text`
 * is the raw extracted resume text from pypdf / python-docx / UTF-8;
 * `skills` / `years_experience` / `education_level` come from the
 * `EntityExtractor` lexicon + regex. `error` is set when a single
 * file fails to parse — the batch still returns the rest. */
export type UploadFileResult = {
  file_id: string;
  filename: string;
  source: 'pdf' | 'docx' | 'text' | 'unknown';
  cv_text: string;
  char_count: number;
  skills: string[];
  years_experience: number | null;
  education_level: string | null;
  error: string | null;
};

export type UploadCvsResponse = {
  uploaded: UploadFileResult[];
  count: number;
  parsed_count: number;
};
