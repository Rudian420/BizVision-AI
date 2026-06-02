'use client';

import Link from 'next/link';
import { useState } from 'react';

import { DateRangeFilter } from '@/components/common/DateRangeFilter';
import { ListFilterChips } from '@/components/common/ListFilterChips';
import { ModuleHistoryShell } from '@/components/common/ModuleHistoryShell';
import { formatAction } from '@/lib/audits/format';
import { formatAuthError } from '@/lib/auth/errors';
import { useForecastHistoryQuery } from '@/lib/forecasting/queries';
import type {
  ForecastAnalysisType,
  ForecastHistoryItem,
} from '@/lib/forecasting/types';
import { moduleById } from '@/lib/modules';

const PAGE_SIZE = 20;

const FORECAST_TYPE_OPTIONS: ReadonlyArray<{
  value: ForecastAnalysisType;
  label: string;
}> = [
  { value: 'forecast', label: 'Forecast' },
  { value: 'sensitivity', label: 'Sensitivity' },
  { value: 'what_if', label: 'What-if' },
  { value: 'cross_module', label: 'Cross-module' },
];

/**
 * Forecast analyses history — TASK-035 per-module list page.
 * Backed by `GET /forecasting/history` (paged). Each row deep-links
 * into the persisted forecast detail at
 * `/modules/forecasting/forecasts/{id}`.
 */
export function ForecastHistoryWorkspace() {
  const meta = moduleById('forecasting');
  const [page, setPage] = useState(1);
  const [analysisType, setAnalysisType] = useState<ForecastAnalysisType | null>(
    null,
  );
  const [since, setSince] = useState<string | null>(null);
  const [until, setUntil] = useState<string | null>(null);
  const query = useForecastHistoryQuery(
    page,
    PAGE_SIZE,
    null,
    analysisType,
    since,
    until,
  );

  const items = query.data?.items ?? [];
  const total = query.data?.total ?? 0;
  const errorMessage = query.isError ? formatAuthError(query.error) : null;

  function handleTypeChange(next: ForecastAnalysisType | null) {
    setAnalysisType(next);
    setPage(1);
  }

  function handleDateChange(next: { since: string | null; until: string | null }) {
    setSince(next.since);
    setUntil(next.until);
    setPage(1);
  }

  return (
    <ModuleHistoryShell
      module="forecasting"
      backHref="/modules/forecasting"
      backLabel="Forecasting workspace"
      scopeLabel="forecasting · history"
      title="Past forecasts"
      tagline="Every forecast you've run, newest first. Open one to see the persisted scenarios + primary drivers + faithful request/response payloads."
      filters={
        <div className="flex flex-col gap-4">
          <ListFilterChips
            legend="Analysis type"
            options={FORECAST_TYPE_OPTIONS}
            active={analysisType}
            onChange={handleTypeChange}
            allLabel="All types"
          />
          <DateRangeFilter since={since} until={until} onChange={handleDateChange} />
        </div>
      }
      items={items}
      isLoading={query.isLoading}
      errorMessage={errorMessage}
      total={total}
      page={page}
      pageSize={PAGE_SIZE}
      onPageChange={setPage}
      keyFor={(item: ForecastHistoryItem) => item.forecast_id}
      renderRow={(item: ForecastHistoryItem) => (
        <Link
          href={`/modules/forecasting/forecasts/${item.forecast_id}`}
          className="flex w-full items-center gap-3 rounded-xl border border-white/10 bg-white/[0.02] px-4 py-3 text-left transition hover:border-white/30"
          style={{ boxShadow: `inset 3px 0 0 ${meta.accent}` }}
        >
          <span
            className="font-data text-xl"
            style={{ color: meta.accent }}
            aria-hidden
          >
            {meta.glyph}
          </span>
          <span className="flex min-w-0 flex-1 flex-col">
            <span className="truncate font-ui text-sm text-text-primary">
              {formatAction(item.analysis_type)}
              {item.series_name && <> · {item.series_name}</>}
            </span>
            <span className="font-data text-[11px] text-text-secondary">
              {item.model_version}
              {item.horizon_days !== null && <> · {item.horizon_days}d</>}
              {item.mape !== null && <> · {item.mape.toFixed(2)}% MAPE</>}
            </span>
          </span>
          <span className="font-ui text-xs text-text-secondary">
            {new Date(item.created_at).toISOString().slice(0, 10)}
          </span>
          <span aria-hidden className="font-data text-text-secondary">
            ›
          </span>
        </Link>
      )}
      emptyPrimary="You haven't run any forecasts yet."
      emptyAction={
        <Link
          href="/modules/forecasting"
          className="inline-flex items-center gap-1.5 rounded-md border border-white/20 px-3 py-1.5 font-ui text-xs text-text-primary transition hover:border-white/40"
        >
          Open the workspace →
        </Link>
      }
    />
  );
}
