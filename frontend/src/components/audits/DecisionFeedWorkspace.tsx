'use client';

import { useState } from 'react';

import { DateRangeFilter } from '@/components/common/DateRangeFilter';
import { formatAuthError } from '@/lib/auth/errors';
import {
  useAuditPageQuery,
  useAuditSummaryQuery,
  useFairnessAggregateQuery,
} from '@/lib/audits/queries';
import type { AuditModuleName } from '@/lib/audits/types';

import { AuditFilters } from './AuditFilters';
import { AuditSummaryCards } from './AuditSummaryCards';
import { AuditTimeline } from './AuditTimeline';
import { FairnessByAttributeCard } from './FairnessByAttributeCard';
import { IntersectionalFairnessGrid } from './IntersectionalFairnessGrid';

const PAGE_SIZE = 20;

/**
 * ML Decision Feed workspace — the first Phase-4 cross-module
 * dashboard (TASK-030, FE-023). Pure consumer of `/api/v1/audits` +
 * `/api/v1/audits/summary` (live since TASK-028 + TASK-029).
 *
 * Layout:
 *   1. Page header (matches module workspace shape).
 *   2. Summary band — total + per-module histogram + per-risk
 *      histogram (`AuditSummaryCards`).
 *   3. Filter strips — module chips + risk_tier chips (`AuditFilters`).
 *   4. Paged timeline — `AuditTimeline` with in-row detail drawer.
 *
 * State management:
 *   • `activeModule` + `activeRiskTier` are local; toggling either
 *     resets the page to 1 (a filtered listing's page semantics
 *     change when the filter changes, so the React Query cache key
 *     changes too — page state would otherwise be stale).
 *   • Summary query is independent of filters — the histograms must
 *     show the *whole* user surface regardless of which module is
 *     drilled into.
 */
export function DecisionFeedWorkspace() {
  const [activeModule, setActiveModule] = useState<AuditModuleName | null>(null);
  const [activeRiskTier, setActiveRiskTier] = useState<string | null>(null);
  const [since, setSince] = useState<string | null>(null);
  const [until, setUntil] = useState<string | null>(null);
  const [page, setPage] = useState(1);

  // Summary + fairness queries honour the date range so the
  // histograms reflect the selected window (TASK-038). Module + risk
  // chip filters still NOT applied to the summary, by design — the
  // user wants to see "of the decisions in this window, how many were
  // in each module" without chip filters shrinking the histogram.
  const summaryQuery = useAuditSummaryQuery(since, until);
  const fairnessQuery = useFairnessAggregateQuery(since, until);
  const pageQuery = useAuditPageQuery({
    module: activeModule,
    risk_tier: activeRiskTier,
    since,
    until,
    page,
    page_size: PAGE_SIZE,
  });

  function handleModuleChange(mod: AuditModuleName | null) {
    setActiveModule(mod);
    setPage(1);
  }

  function handleRiskTierChange(tier: string | null) {
    setActiveRiskTier(tier);
    setPage(1);
  }

  function handleDateChange(next: { since: string | null; until: string | null }) {
    setSince(next.since);
    setUntil(next.until);
    setPage(1);
  }

  const errorMessage = pageQuery.isError
    ? formatAuthError(pageQuery.error)
    : summaryQuery.isError
      ? formatAuthError(summaryQuery.error)
      : null;

  return (
    <div className="flex flex-col gap-8">
      <header className="border-b border-white/10 pb-6">
        <span className="font-ui text-[10px] uppercase tracking-widest text-text-secondary">
          Phase-4 · cross-module
        </span>
        <h2 className="mt-1 font-ui text-3xl font-semibold tracking-tight text-text-primary">
          ML Decision Feed
        </h2>
        <p className="mt-2 max-w-2xl font-ui text-sm text-text-secondary">
          Every AI decision across recruitment, pricing, forecasting, sustainability, and the
          chatbot — append-only, with the request, response, explanation, and fairness slice
          captured at decision time.
        </p>
      </header>

      {errorMessage && (
        <p
          role="alert"
          className="rounded-md border border-coral/40 bg-coral/10 px-3 py-2 font-ui text-sm text-coral"
        >
          {errorMessage}
        </p>
      )}

      <AuditSummaryCards
        summary={summaryQuery.data}
        isLoading={summaryQuery.isLoading}
      />

      <div className="grid gap-4 md:grid-cols-2">
        <FairnessByAttributeCard
          data={fairnessQuery.data}
          isLoading={fairnessQuery.isLoading}
        />
        <IntersectionalFairnessGrid
          data={fairnessQuery.data}
          isLoading={fairnessQuery.isLoading}
        />
      </div>

      <AuditFilters
        activeModule={activeModule}
        activeRiskTier={activeRiskTier}
        onModuleChange={handleModuleChange}
        onRiskTierChange={handleRiskTierChange}
      />

      <DateRangeFilter since={since} until={until} onChange={handleDateChange} />

      <AuditTimeline
        items={pageQuery.data?.items ?? []}
        isLoading={pageQuery.isLoading}
        total={pageQuery.data?.total ?? 0}
        page={pageQuery.data?.page ?? page}
        pageSize={pageQuery.data?.page_size ?? PAGE_SIZE}
        onPageChange={setPage}
      />
    </div>
  );
}
