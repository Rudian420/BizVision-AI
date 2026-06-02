'use client';

import { formatAuthError } from '@/lib/auth/errors';
import { useForecastDetailQuery } from '@/lib/forecasting/queries';
import { formatAction } from '@/lib/audits/format';
import { PersistedAnalysisDetail } from '@/components/common/PersistedAnalysisDetail';

type ForecastDetailWorkspaceProps = {
  forecastId: string;
};

/**
 * Forecast detail — TASK-033 deep-link target from the ML Decision
 * Feed's audit row footer (`reference_type=forecast_analysis`).
 *
 * Polymorphic-table renderer — one component covers all 4 variants
 * (forecast / sensitivity / what_if / cross_module). Headline cells
 * surface the scenario end values + MAPE; the JSONB panels show the
 * variant's faithful request/response.
 */
export function ForecastDetailWorkspace({ forecastId }: ForecastDetailWorkspaceProps) {
  const query = useForecastDetailQuery(forecastId);
  const detail = query.data;
  const errorMessage = query.isError ? formatAuthError(query.error) : null;

  return (
    <PersistedAnalysisDetail
      module="forecasting"
      backHref="/modules/forecasting"
      backLabel="Forecasting workspace"
      scopeLabel={`forecasting · ${detail?.analysis_type ?? 'analysis'}`}
      title={
        detail
          ? `${formatAction(detail.analysis_type)} · ${detail.series_name ?? 'cross-module'}`
          : '…'
      }
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
              {
                label: 'Horizon',
                value: detail.horizon_days !== null ? `${detail.horizon_days}d` : null,
              },
              {
                label: 'Base end',
                value: detail.base_end_value?.toFixed(2) ?? null,
              },
              {
                label: 'Bull end',
                value: detail.bull_end_value?.toFixed(2) ?? null,
              },
              {
                label: 'Bear end',
                value: detail.bear_end_value?.toFixed(2) ?? null,
              },
              {
                label: 'MAPE',
                value: detail.mape !== null ? `${detail.mape.toFixed(2)}%` : null,
              },
            ]
          : []
      }
      interpretation={detail?.interpretation ?? null}
      requestPayload={detail?.request_payload ?? {}}
      responsePayload={detail?.response_payload ?? {}}
      isLoading={query.isLoading}
      errorMessage={errorMessage}
    />
  );
}
