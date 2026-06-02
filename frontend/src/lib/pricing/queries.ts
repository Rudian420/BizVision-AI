/**
 * React Query hooks + key factory for the pricing module.
 *
 * Wave 1 only shipped the optimize mutation. TASK-033 adds the
 * analysis-detail read so the audit feed can deep-link into the
 * persisted pricing analysis view.
 */

import { useMutation, useQuery } from '@tanstack/react-query';

import {
  fetchAnalysisDetail,
  fetchPricingHistory,
  runOptimize,
} from './client';
import type {
  PriceOptimizationRequest,
  PriceOptimizationResponse,
  PricingAnalysisDetail,
  PricingHistoryPage,
} from './types';

export const pricingKeys = {
  all: ['pricing'] as const,
  analysisDetail: (analysisId: string) =>
    [...pricingKeys.all, 'analyses', 'detail', analysisId] as const,
  historyPage: (
    page: number,
    pageSize: number,
    productId?: string | null,
    analysisType?: string | null,
    since?: string | null,
    until?: string | null,
  ) =>
    [
      ...pricingKeys.all,
      'history',
      'page',
      page,
      pageSize,
      productId ?? null,
      analysisType ?? null,
      since ?? null,
      until ?? null,
    ] as const,
};

export function useRunOptimizeMutation() {
  return useMutation<PriceOptimizationResponse, Error, PriceOptimizationRequest>({
    mutationFn: runOptimize,
  });
}

export function usePricingAnalysisDetailQuery(analysisId: string | null) {
  return useQuery<PricingAnalysisDetail>({
    queryKey: pricingKeys.analysisDetail(analysisId ?? ''),
    queryFn: () => {
      if (!analysisId) throw new Error('analysisId required');
      return fetchAnalysisDetail(analysisId);
    },
    enabled: Boolean(analysisId),
    staleTime: 60_000,
  });
}

export function usePricingHistoryQuery(
  page: number,
  pageSize: number,
  productId?: string | null,
  analysisType?: string | null,
  since?: string | null,
  until?: string | null,
) {
  return useQuery<PricingHistoryPage>({
    queryKey: pricingKeys.historyPage(
      page,
      pageSize,
      productId,
      analysisType,
      since,
      until,
    ),
    queryFn: () =>
      fetchPricingHistory(
        page,
        pageSize,
        productId,
        analysisType,
        since,
        until,
      ),
    staleTime: 30_000,
  });
}
