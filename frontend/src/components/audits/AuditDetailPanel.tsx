'use client';

import Link from 'next/link';

import { auditReferenceLink } from '@/lib/audits/format';
import type { AuditLogRead } from '@/lib/audits/types';
import { cn } from '@/lib/utils';

type AuditDetailPanelProps = {
  row: AuditLogRead;
};

/**
 * In-row detail panel for a single audit log entry. Renders 4
 * JSON-shaped slices (request / response / explanation / fairness)
 * as compact field tables. Each slice is its own collapsible card so
 * the user can scan the high-signal fields without diving into raw
 * JSON.
 *
 * Reference id + soft FK (reference_type) are surfaced so a
 * follow-up wave can deep-link into the owning module's record view.
 */
export function AuditDetailPanel({ row }: AuditDetailPanelProps) {
  return (
    <div className="mt-1 grid grid-cols-1 gap-3 rounded-xl border border-white/10 bg-white/[0.015] p-4 lg:grid-cols-2">
      <Slice title="Request" data={row.request_summary} accent="cyan" />
      <Slice title="Response" data={row.response_summary} accent="gold" />
      <Slice title="Explanation" data={row.explanation_summary} accent="violet" />
      <Slice title="Fairness" data={row.fairness_summary} accent="emerald" />

      <footer className="lg:col-span-2 mt-1 flex flex-wrap items-center gap-x-6 gap-y-1 border-t border-white/10 pt-3 font-data text-[11px] text-text-secondary">
        <span>
          <span className="text-text-primary/60">id</span> {row.id}
        </span>
        {row.reference_id && (
          <ReferenceFooterItem
            referenceType={row.reference_type}
            referenceId={row.reference_id}
          />
        )}
        <span>
          <span className="text-text-primary/60">created</span>{' '}
          {new Date(row.created_at).toISOString()}
        </span>
      </footer>
    </div>
  );
}

/** Soft-FK footer entry. Becomes a deep link when a per-module
 * record-view route exists for the reference_type (TASK-032 wired
 * `recruitment_session`); otherwise renders as plain text. */
function ReferenceFooterItem({
  referenceType,
  referenceId,
}: {
  referenceType: string | null;
  referenceId: string;
}) {
  const href = auditReferenceLink(referenceType, referenceId);
  if (href) {
    return (
      <Link
        href={href}
        className="text-cyan underline-offset-2 hover:underline"
        aria-label={`Open ${referenceType ?? 'record'} ${referenceId}`}
      >
        <span className="text-text-primary/60">{referenceType ?? 'reference'}</span>{' '}
        {referenceId}
      </Link>
    );
  }
  return (
    <span>
      <span className="text-text-primary/60">{referenceType ?? 'reference'}</span>{' '}
      {referenceId}
    </span>
  );
}

type AccentName = 'cyan' | 'gold' | 'violet' | 'emerald' | 'coral';

const ACCENT_CLASSES: Record<AccentName, string> = {
  cyan: 'text-cyan',
  gold: 'text-gold',
  violet: 'text-violet',
  emerald: 'text-emerald',
  coral: 'text-coral',
};

type SliceProps = {
  title: string;
  data: Record<string, unknown> | null | undefined;
  accent: AccentName;
};

function Slice({ title, data, accent }: SliceProps) {
  const entries = data ? Object.entries(data).filter(([, v]) => v !== null && v !== undefined) : [];
  return (
    <article className="rounded-lg border border-white/5 bg-white/[0.02] p-3">
      <header
        className={cn(
          'mb-2 font-ui text-[10px] uppercase tracking-widest',
          ACCENT_CLASSES[accent],
        )}
      >
        {title}
      </header>
      {entries.length === 0 ? (
        <p className="font-ui text-xs italic text-text-secondary">
          No {title.toLowerCase()} summary recorded.
        </p>
      ) : (
        <dl className="space-y-1.5 font-data text-[11px]">
          {entries.map(([key, value]) => (
            <div key={key} className="flex items-start gap-3">
              <dt className="w-32 shrink-0 truncate text-text-secondary">{key}</dt>
              <dd className="min-w-0 flex-1 break-words text-text-primary">
                {formatValue(value)}
              </dd>
            </div>
          ))}
        </dl>
      )}
    </article>
  );
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined) return '—';
  if (typeof value === 'number') {
    return Number.isInteger(value) ? value.toString() : value.toFixed(4).replace(/\.?0+$/, '');
  }
  if (typeof value === 'boolean') return value ? 'true' : 'false';
  if (typeof value === 'string') return value;
  if (Array.isArray(value)) {
    if (value.length === 0) return '[]';
    if (value.every((v) => typeof v === 'string' || typeof v === 'number')) {
      return value.join(', ');
    }
    return JSON.stringify(value);
  }
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
}
