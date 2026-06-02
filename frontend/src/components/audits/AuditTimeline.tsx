'use client';

import { useState } from 'react';

import { formatAction, formatAuditTimestamp, formatLatency } from '@/lib/audits/format';
import type { AuditLogRead } from '@/lib/audits/types';
import { moduleById } from '@/lib/modules';
import { RiskBadge } from '@/components/common/RiskBadge';
import type { RiskLevel } from '@/lib/risk/types';
import { cn } from '@/lib/utils';

import { AuditDetailPanel } from './AuditDetailPanel';

type AuditTimelineProps = {
  items: AuditLogRead[];
  isLoading: boolean;
  total: number;
  page: number;
  pageSize: number;
  onPageChange: (page: number) => void;
};

const KNOWN_RISK_TIERS: ReadonlySet<RiskLevel> = new Set<RiskLevel>([
  'low',
  'medium',
  'high',
  'critical',
]);

/**
 * Paged timeline of audit-log rows. Each row collapses to a one-line
 * summary; clicking expands an in-row detail panel showing the full
 * request/response/explanation/fairness payloads.
 *
 * Empty + loading states are handled inline. Pagination is button-
 * based (Prev / Next) — keeps the component stateless and matches
 * the recruitment + pricing history panels' future pagination shape.
 */
export function AuditTimeline({
  items,
  isLoading,
  total,
  page,
  pageSize,
  onPageChange,
}: AuditTimelineProps) {
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  if (isLoading && items.length === 0) {
    return <TimelineSkeleton />;
  }
  if (items.length === 0) {
    return (
      <div
        role="status"
        className="rounded-2xl border border-white/10 bg-white/[0.02] p-12 text-center"
      >
        <p className="font-ui text-sm text-text-secondary">
          No ML decisions match the current filters. Try clearing them or run a workflow in one
          of the modules to populate the audit log.
        </p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      <ul aria-label="ML decision timeline" className="flex flex-col gap-2">
        {items.map((row) => {
          const meta = moduleById(row.module);
          const isExpanded = expandedId === row.id;
          const risk = row.risk_tier?.toLowerCase();
          const showRiskBadge = risk && KNOWN_RISK_TIERS.has(risk as RiskLevel);
          const latency = formatLatency(row.latency_ms);
          return (
            <li key={row.id}>
              <button
                type="button"
                onClick={() => setExpandedId(isExpanded ? null : row.id)}
                aria-expanded={isExpanded}
                className={cn(
                  'flex w-full items-center gap-3 rounded-xl border border-white/10 bg-white/[0.02] px-4 py-3 text-left transition hover:border-white/20',
                  isExpanded && 'border-white/30 bg-white/[0.04]',
                )}
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
                  <span className="font-ui text-sm text-text-primary">
                    {formatAction(row.action)}{' '}
                    <span className="text-text-secondary">· {row.module}</span>
                  </span>
                  <span className="font-data text-[11px] text-text-secondary">
                    {row.model_version}
                    {latency && ` · ${latency}`}
                  </span>
                </span>
                {showRiskBadge && (
                  <RiskBadge risk={risk as RiskLevel} />
                )}
                <span className="font-ui text-xs text-text-secondary">
                  {formatAuditTimestamp(row.created_at)}
                </span>
                <span
                  aria-hidden
                  className={cn(
                    'font-data text-text-secondary transition-transform',
                    isExpanded && 'rotate-90',
                  )}
                >
                  ›
                </span>
              </button>
              {isExpanded && <AuditDetailPanel row={row} />}
            </li>
          );
        })}
      </ul>

      <nav
        aria-label="Pagination"
        className="flex items-center justify-between border-t border-white/10 pt-3 font-ui text-xs text-text-secondary"
      >
        <span>
          Page {page} of {totalPages} · {total.toLocaleString()} total
        </span>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => onPageChange(page - 1)}
            disabled={page <= 1}
            className="rounded-md border border-white/10 px-3 py-1 transition hover:border-white/30 disabled:cursor-not-allowed disabled:opacity-30"
          >
            Prev
          </button>
          <button
            type="button"
            onClick={() => onPageChange(page + 1)}
            disabled={page >= totalPages}
            className="rounded-md border border-white/10 px-3 py-1 transition hover:border-white/30 disabled:cursor-not-allowed disabled:opacity-30"
          >
            Next
          </button>
        </div>
      </nav>
    </div>
  );
}

function TimelineSkeleton() {
  return (
    <ul aria-hidden className="flex flex-col gap-2">
      {[0, 1, 2, 3].map((i) => (
        <li
          key={i}
          className="h-14 animate-pulse rounded-xl border border-white/10 bg-white/[0.02]"
        />
      ))}
    </ul>
  );
}
