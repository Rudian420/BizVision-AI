'use client';

import Link from 'next/link';
import { useState } from 'react';

import { DateRangeFilter } from '@/components/common/DateRangeFilter';
import { ListFilterChips } from '@/components/common/ListFilterChips';
import { ModuleHistoryShell } from '@/components/common/ModuleHistoryShell';
import { RiskBadge } from '@/components/common/RiskBadge';
import { formatAction } from '@/lib/audits/format';
import { formatAuthError } from '@/lib/auth/errors';
import { moduleById } from '@/lib/modules';
import type { RiskLevel } from '@/lib/risk/types';
import { useAssessmentsListQuery } from '@/lib/sustainability/queries';
import type {
  SustainabilityAssessmentHistoryItem,
  SustainabilityAssessmentType,
} from '@/lib/sustainability/types';

const PAGE_SIZE = 20;

const SUSTAINABILITY_TYPE_OPTIONS: ReadonlyArray<{
  value: SustainabilityAssessmentType;
  label: string;
}> = [
  { value: 'score', label: 'Score' },
  { value: 'simulation', label: 'Simulation' },
  { value: 'recommendations', label: 'Recommendations' },
  { value: 'carbon_estimate', label: 'Carbon' },
];

const KNOWN_RISK_TIERS: ReadonlySet<RiskLevel> = new Set<RiskLevel>([
  'low',
  'medium',
  'high',
  'critical',
]);

/**
 * Sustainability assessments history — TASK-035 per-module list
 * page. Backed by `GET /sustainability/assessments` (paged). Each
 * row deep-links into the persisted assessment detail at
 * `/modules/sustainability/assessments/{id}`.
 */
export function SustainabilityHistoryWorkspace() {
  const meta = moduleById('sustainability');
  const [page, setPage] = useState(1);
  const [assessmentType, setAssessmentType] =
    useState<SustainabilityAssessmentType | null>(null);
  const [since, setSince] = useState<string | null>(null);
  const [until, setUntil] = useState<string | null>(null);
  const query = useAssessmentsListQuery(
    page,
    PAGE_SIZE,
    assessmentType,
    null,
    since,
    until,
  );

  const items = query.data?.items ?? [];
  const total = query.data?.total ?? 0;
  const errorMessage = query.isError ? formatAuthError(query.error) : null;

  function handleTypeChange(next: SustainabilityAssessmentType | null) {
    setAssessmentType(next);
    setPage(1);
  }

  function handleDateChange(next: { since: string | null; until: string | null }) {
    setSince(next.since);
    setUntil(next.until);
    setPage(1);
  }

  return (
    <ModuleHistoryShell
      module="sustainability"
      backHref="/modules/sustainability"
      backLabel="Sustainability workspace"
      scopeLabel="sustainability · history"
      title="Past assessments"
      tagline="Every ESG assessment you've run, newest first. Open one to see the persisted composite score + sub-pillars + faithful request/response payloads."
      filters={
        <div className="flex flex-col gap-4">
          <ListFilterChips
            legend="Assessment type"
            options={SUSTAINABILITY_TYPE_OPTIONS}
            active={assessmentType}
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
      keyFor={(item: SustainabilityAssessmentHistoryItem) => item.assessment_id}
      renderRow={(item: SustainabilityAssessmentHistoryItem) => {
        const showRisk =
          item.risk_level && KNOWN_RISK_TIERS.has(item.risk_level as RiskLevel);
        return (
          <Link
            href={`/modules/sustainability/assessments/${item.assessment_id}`}
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
                {formatAction(item.assessment_type)}
                {item.company_name && <> · {item.company_name}</>}
                {!item.company_name && item.industry && <> · {item.industry}</>}
              </span>
              <span className="font-data text-[11px] text-text-secondary">
                {item.model_version}
                {item.composite_score !== null && (
                  <> · score {item.composite_score.toFixed(1)}</>
                )}
                {item.total_tco2e !== null && (
                  <> · {item.total_tco2e.toFixed(1)} tCO2e</>
                )}
              </span>
            </span>
            {showRisk && <RiskBadge risk={item.risk_level as RiskLevel} />}
            <span className="font-ui text-xs text-text-secondary">
              {new Date(item.created_at).toISOString().slice(0, 10)}
            </span>
            <span aria-hidden className="font-data text-text-secondary">
              ›
            </span>
          </Link>
        );
      }}
      emptyPrimary="You haven't run any ESG assessments yet."
      emptyAction={
        <Link
          href="/modules/sustainability"
          className="inline-flex items-center gap-1.5 rounded-md border border-white/20 px-3 py-1.5 font-ui text-xs text-text-primary transition hover:border-white/40"
        >
          Open the workspace →
        </Link>
      }
    />
  );
}
