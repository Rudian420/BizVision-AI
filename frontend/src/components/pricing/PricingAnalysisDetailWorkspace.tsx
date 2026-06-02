'use client';

import { formatAuthError } from '@/lib/auth/errors';
import { usePricingAnalysisDetailQuery } from '@/lib/pricing/queries';
import { formatAction } from '@/lib/audits/format';
import { PersistedAnalysisDetail } from '@/components/common/PersistedAnalysisDetail';

type PricingAnalysisDetailWorkspaceProps = {
  analysisId: string;
};

/**
 * Pricing analysis detail — TASK-033 deep-link target from the ML
 * Decision Feed's audit row footer (`reference_type=pricing_analysis`).
 *
 * Reuses the shared `<PersistedAnalysisDetail />` layout. The
 * polymorphic-table shape means one renderer covers all 4 variants
 * (optimize / monte_carlo / elasticity / scenario_comparison) — the
 * discriminator drives the scope chip + headline cells; the JSONB
 * panels show the variant's faithful request/response.
 */
export function PricingAnalysisDetailWorkspace({
  analysisId,
}: PricingAnalysisDetailWorkspaceProps) {
  const query = usePricingAnalysisDetailQuery(analysisId);
  const detail = query.data;
  const errorMessage = query.isError ? formatAuthError(query.error) : null;

  return (
    <PersistedAnalysisDetail
      module="pricing"
      backHref="/modules/pricing"
      backLabel="Pricing workspace"
      scopeLabel={`pricing · ${detail?.analysis_type ?? 'analysis'}`}
      title={detail ? `${formatAction(detail.analysis_type)} · ${detail.product_id}` : '…'}
      subtitle={
        detail
          ? `${detail.model_version} · ${new Date(detail.created_at)
              .toISOString()
              .slice(0, 10)} · ${detail.processing_time_ms.toFixed(1)}ms`
          : ''
      }
      headlineCells={
        detail
          ? [
              { label: 'Recommended price', value: detail.recommended_price?.toFixed(2) ?? null },
              {
                label: 'Revenue uplift',
                value:
                  detail.expected_revenue_uplift !== null
                    ? `${(detail.expected_revenue_uplift * 100).toFixed(1)}%`
                    : null,
              },
              {
                label: 'Trials / points',
                value: detail.num_trials_or_points,
              },
              { label: 'Product id', value: detail.product_id },
            ]
          : []
      }
      requestPayload={detail?.request_payload ?? {}}
      responsePayload={detail?.response_payload ?? {}}
      isLoading={query.isLoading}
      errorMessage={errorMessage}
    />
  );
}
