/**
 * Forecasting API client — wraps `/forecasting/forecast`.
 *
 * Wave 1 exposes only the `runForecast` mutation. Sensitivity,
 * what-if, and cross-module endpoints arrive in wave 2 behind the
 * same workspace tab system.
 */

import { API_ROUTES } from '@bizvision/contracts';

import { apiClient } from '@/lib/api-client';

import type {
  ForecastAnalysisDetail,
  ForecastHistoryPage,
  ForecastRequest,
  ForecastResponse,
} from './types';

export async function runForecast(body: ForecastRequest): Promise<ForecastResponse> {
  const res = await apiClient.post<ForecastResponse>(
    API_ROUTES.forecasting.forecast,
    body,
  );
  return res.data;
}

export async function fetchForecastDetail(
  forecastId: string,
): Promise<ForecastAnalysisDetail> {
  const res = await apiClient.get<ForecastAnalysisDetail>(
    API_ROUTES.forecasting.detail(forecastId),
  );
  return res.data;
}

export async function fetchForecastHistory(
  page: number,
  pageSize: number,
  seriesName?: string | null,
  analysisType?: string | null,
  since?: string | null,
  until?: string | null,
): Promise<ForecastHistoryPage> {
  const params: Record<string, string | number> = {
    page,
    page_size: pageSize,
  };
  if (seriesName) params.series_name = seriesName;
  if (analysisType) params.analysis_type = analysisType;
  if (since) params.since = since;
  if (until) params.until = until;
  const res = await apiClient.get<ForecastHistoryPage>(
    API_ROUTES.forecasting.history,
    { params },
  );
  return res.data;
}
