'use client';

import Link from 'next/link';
import { useState } from 'react';

import { DateRangeFilter } from '@/components/common/DateRangeFilter';
import { ListFilterChips } from '@/components/common/ListFilterChips';
import { ModuleHistoryShell } from '@/components/common/ModuleHistoryShell';
import { formatAction } from '@/lib/audits/format';
import { formatAuthError } from '@/lib/auth/errors';
import { moduleById } from '@/lib/modules';
import { usePricingHistoryQuery } from '@/lib/pricing/queries';
import type {
  PricingAnalysisType,
  PricingHistoryItem,
} from '@/lib/pricing/types';

const PAGE_SIZE = 20;

const PRICING_TYPE_OPTIONS: ReadonlyArray<{
  value: PricingAnalysisType;
  label: string;
}> = [
  { value: 'optimize', label: 'Optimize' },
  { value: 'monte_carlo', label: 'Monte Carlo' },
  { value: 'elasticity', label: 'Elasticity' },
  { value: 'scenario_comparison', label: 'Scenarios' },
];

/**
 * Pricing analyses history — TASK-035 per-module list page.
 * Backed by `GET /pricing/history` (paged). Each row deep-links into
 * the persisted analysis detail at `/modules/pricing/analyses/{id}`.
 */
export function PricingHistoryWorkspace() {
  const meta = moduleById('pricing');
  const [page, setPage] = useState(1);
  const [analysisType, setAnalysisType] = useState<PricingAnalysisType | null>(
    null,
  );
  const [since, setSince] = useState<string | null>(null);
  const [until, setUntil] = useState<string | null>(null);
  const query = usePricingHistoryQuery(
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

  function handleTypeChange(next: PricingAnalysisType | null) {
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
      module="pricing"
      backHref="/modules/pricing"
      backLabel="Pricing workspace"
      scopeLabel="pricing · history"
      title="Past analyses"
      tagline="Every pricing analysis you've run, newest first. Open one to see the persisted price recommendation + SHAP attributions + faithful request/response payloads."
      filters={
        <div className="flex flex-col gap-4">
          <ListFilterChips
            legend="Analysis type"
            options={PRICING_TYPE_OPTIONS}
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
      keyFor={(item: PricingHistoryItem) => item.analysis_id}
      renderRow={(item: PricingHistoryItem) => (
        <Link
          href={`/modules/pricing/analyses/${item.analysis_id}`}
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
              {formatAction(item.analysis_type)} · {item.product_id}
            </span>
            <span className="font-data text-[11px] text-text-secondary">
              {item.model_version}
              {item.recommended_price !== null && (
                <> · price {item.recommended_price.toFixed(2)}</>
              )}
              {item.expected_revenue_uplift !== null && (
                <> · uplift {(item.expected_revenue_uplift * 100).toFixed(1)}%</>
              )}
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
      emptyPrimary="You haven't run any pricing analyses yet."
      emptyAction={
        <Link
          href="/modules/pricing"
          className="inline-flex items-center gap-1.5 rounded-md border border-white/20 px-3 py-1.5 font-ui text-xs text-text-primary transition hover:border-white/40"
        >
          Open the workspace →
        </Link>
      }
    />
  );
}
