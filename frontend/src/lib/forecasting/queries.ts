/**
 * React Query hooks + key factory for the forecasting module.
 *
 * Wave 1 only shipped the forecast mutation. TASK-033 adds the
 * forecast-detail read so the audit feed can deep-link into the
 * persisted forecast view.
 */

import { useMutation, useQuery } from '@tanstack/react-query';

import {
  fetchForecastDetail,
  fetchForecastHistory,
  runForecast,
} from './client';
import type {
  ForecastAnalysisDetail,
  ForecastHistoryPage,
  ForecastRequest,
  ForecastResponse,
} from './types';

export const forecastingKeys = {
  all: ['forecasting'] as const,
  forecastDetail: (forecastId: string) =>
    [...forecastingKeys.all, 'forecasts', 'detail', forecastId] as const,
  historyPage: (
    page: number,
    pageSize: number,
    seriesName?: string | null,
    analysisType?: string | null,
    since?: string | null,
    until?: string | null,
  ) =>
    [
      ...forecastingKeys.all,
      'history',
      'page',
      page,
      pageSize,
      seriesName ?? null,
      analysisType ?? null,
      since ?? null,
      until ?? null,
    ] as const,
};

export function useRunForecastMutation() {
  return useMutation<ForecastResponse, Error, ForecastRequest>({
    mutationFn: runForecast,
  });
}

export function useForecastDetailQuery(forecastId: string | null) {
  return useQuery<ForecastAnalysisDetail>({
    queryKey: forecastingKeys.forecastDetail(forecastId ?? ''),
    queryFn: () => {
      if (!forecastId) throw new Error('forecastId required');
      return fetchForecastDetail(forecastId);
    },
    enabled: Boolean(forecastId),
    staleTime: 60_000,
  });
}

export function useForecastHistoryQuery(
  page: number,
  pageSize: number,
  seriesName?: string | null,
  analysisType?: string | null,
  since?: string | null,
  until?: string | null,
) {
  return useQuery<ForecastHistoryPage>({
    queryKey: forecastingKeys.historyPage(
      page,
      pageSize,
      seriesName,
      analysisType,
      since,
      until,
    ),
    queryFn: () =>
      fetchForecastHistory(
        page,
        pageSize,
        seriesName,
        analysisType,
        since,
        until,
      ),
    staleTime: 30_000,
  });
}
