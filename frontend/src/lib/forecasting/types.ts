/**
 * Hand-written forecasting contract types.
 *
 * Mirror `backend/src/api/v1/schemas/forecasting.py`. Kept local
 * until the OpenAPI generator runs against the live backend — same
 * posture as the recruitment, pricing, and auth modules.
 */

import type { SHAPFeature } from '@/lib/shap/types';

export type TimeSeriesPoint = {
  /** ISO date string (`YYYY-MM-DD`). */
  ds: string;
  y: number;
};

export type ForecastRequest = {
  series_name?: string;
  history: TimeSeriesPoint[];
  forecast_horizon_days?: number;
  include_scenarios?: boolean;
};

export type ForecastPoint = {
  ds: string;
  yhat: number;
  yhat_lower: number;
  yhat_upper: number;
};

export type ScenarioForecast = {
  scenario: string;
  points: ForecastPoint[];
  end_value: number;
  cumulative_value: number;
};

export type ForecastResponse = {
  forecast_id: string;
  series_name: string;
  generated_at: string;
  horizon_days: number;
  scenarios: Record<string, ScenarioForecast>;
  primary_drivers: SHAPFeature[];
  /** Backtest MAPE — surfaced as a percentage (e.g. 6.4 = 6.4%). */
  mape: number;
  model_version: string;
};

/** Forecast analysis types — polymorphic discriminator. */
export type ForecastAnalysisType =
  | 'forecast'
  | 'sensitivity'
  | 'what_if'
  | 'cross_module';

/** Summary row returned by `GET /forecasting/history` (paged). */
export type ForecastHistoryItem = {
  forecast_id: string;
  analysis_type: ForecastAnalysisType;
  series_name: string | null;
  horizon_days: number | null;
  base_end_value: number | null;
  bull_end_value: number | null;
  bear_end_value: number | null;
  mape: number | null;
  model_version: string;
  created_at: string;
};

export type ForecastHistoryPage = {
  items: ForecastHistoryItem[];
  total: number;
  page: number;
  page_size: number;
};

/** Persisted-row reconstruction returned by `/forecasting/forecasts/{id}` (TASK-033). */
export type ForecastAnalysisDetail = {
  forecast_id: string;
  analysis_type: ForecastAnalysisType;
  series_name: string | null;
  created_at: string;
  model_version: string;
  processing_time_ms: number;
  horizon_days: number | null;
  base_end_value: number | null;
  bull_end_value: number | null;
  bear_end_value: number | null;
  mape: number | null;
  interpretation: string | null;
  request_payload: Record<string, unknown>;
  response_payload: Record<string, unknown>;
};
