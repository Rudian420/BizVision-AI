/**
 * Pricing API client — wraps `/pricing/*` endpoints.
 *
 * Wave 1 exposes only `runOptimize` (the canonical "recommend a
 * price" call). Monte-Carlo simulation, elasticity, and scenario
 * comparison endpoints arrive in wave 2 behind the same workspace
 * tab system.
 */

import { API_ROUTES } from '@bizvision/contracts';

import { apiClient } from '@/lib/api-client';

import type {
  PriceOptimizationRequest,
  PriceOptimizationResponse,
  PricingAnalysisDetail,
  PricingHistoryPage,
} from './types';

export async function runOptimize(
  body: PriceOptimizationRequest,
): Promise<PriceOptimizationResponse> {
  const res = await apiClient.post<PriceOptimizationResponse>(
    API_ROUTES.pricing.optimize,
    body,
  );
  return res.data;
}

export async function fetchAnalysisDetail(
  analysisId: string,
): Promise<PricingAnalysisDetail> {
  const res = await apiClient.get<PricingAnalysisDetail>(
    API_ROUTES.pricing.analysis(analysisId),
  );
  return res.data;
}

export async function fetchPricingHistory(
  page: number,
  pageSize: number,
  productId?: string | null,
  analysisType?: string | null,
  since?: string | null,
  until?: string | null,
): Promise<PricingHistoryPage> {
  const params: Record<string, string | number> = {
    page,
    page_size: pageSize,
  };
  if (productId) params.product_id = productId;
  if (analysisType) params.analysis_type = analysisType;
  if (since) params.since = since;
  if (until) params.until = until;
  const res = await apiClient.get<PricingHistoryPage>(API_ROUTES.pricing.history, {
    params,
  });
  return res.data;
}
