'use client';

import Link from 'next/link';
import type { ReactNode } from 'react';

import type { AIModule } from '@bizvision/contracts';

import { moduleById } from '@/lib/modules';
import { cn } from '@/lib/utils';

type HeadlineCell = {
  /** Short caption rendered as an uppercase chip. */
  label: string;
  /** The value cell (already formatted). Falsy/empty values are skipped. */
  value: ReactNode;
};

type PersistedAnalysisDetailProps = {
  /** Module the detail belongs to — drives the accent rail + glyph. */
  module: AIModule;
  /** "All sessions" / "All analyses" back-link href on the per-module list. */
  backHref: string;
  /** Back-link label for that href. */
  backLabel: string;
  /** Subtitle chip text, e.g. "pricing · analysis" / "forecasting · forecast". */
  scopeLabel: string;
  /** Title row (job title / product id / series name / company). */
  title: string;
  /** Subtitle row (discriminator + model_version + ISO date + extras). */
  subtitle: ReactNode;

  /** Headline cells — surfaced as a key/value grid above the JSONB panels. */
  headlineCells?: HeadlineCell[];

  /** Optional risk badge slot. */
  riskSlot?: ReactNode;
  /** Optional interpretation paragraph. */
  interpretation?: string | null;

  /** Faithful request payload. */
  requestPayload: Record<string, unknown>;
  /** Faithful response payload. */
  responsePayload: Record<string, unknown>;

  /** Loading state. */
  isLoading?: boolean;
  /** Error message (already formatted). */
  errorMessage?: string | null;
};

/**
 * Shared persisted-detail layout used by the 3 polymorphic-table
 * module detail pages (pricing/forecasting/sustainability, TASK-033).
 *
 * Renders:
 *   • back-link → per-module list
 *   • header (accent glyph + scope chip + title + subtitle)
 *   • optional risk badge slot + optional interpretation paragraph
 *   • headline-cell grid (sparse — null values are skipped)
 *   • Request / Response JSONB panels (compact key/value tables)
 *
 * Per-module workspaces wrap this with their own type adaptation —
 * polymorphic discriminator + JSONB shape are uniform enough across
 * the 3 tables that one renderer covers all of them. Module-specific
 * visualisations (price curve, scenario chart, pillar bars) stay in
 * the live-analyze workspaces; the detail view is auditor-grade
 * rather than interactive.
 */
export function PersistedAnalysisDetail({
  module,
  backHref,
  backLabel,
  scopeLabel,
  title,
  subtitle,
  headlineCells,
  riskSlot,
  interpretation,
  requestPayload,
  responsePayload,
  isLoading = false,
  errorMessage = null,
}: PersistedAnalysisDetailProps) {
  const meta = moduleById(module);

  const visibleHeadline = (headlineCells ?? []).filter(
    (c) => c.value !== null && c.value !== undefined && c.value !== '',
  );

  return (
    <div className="flex flex-col gap-6">
      <header className="border-b border-white/10 pb-6">
        <div className="mb-2 flex items-center gap-3">
          <Link
            href={backHref}
            className="font-ui text-[10px] uppercase tracking-widest text-text-secondary underline-offset-4 hover:text-text-primary hover:underline"
          >
            ← {backLabel}
          </Link>
        </div>
        <div className="mb-2 flex items-center gap-3">
          <span className="font-data text-3xl" style={{ color: meta.accent }}>
            {meta.glyph}
          </span>
          <span className="font-ui text-[10px] uppercase tracking-widest text-text-secondary">
            {scopeLabel}
          </span>
        </div>
        <div className="flex items-baseline justify-between gap-4">
          <h2 className="font-ui text-3xl font-semibold tracking-tight text-text-primary">
            {isLoading ? 'Loading…' : title}
          </h2>
          {riskSlot}
        </div>
        <p className="mt-2 max-w-2xl font-data text-[11px] text-text-secondary">
          {subtitle}
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

      {interpretation && (
        <p className="rounded-2xl border border-white/10 bg-white/[0.02] px-5 py-4 font-ui text-sm leading-relaxed text-text-primary">
          {interpretation}
        </p>
      )}

      {visibleHeadline.length > 0 && (
        <dl
          aria-label="Headline values"
          className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4"
        >
          {visibleHeadline.map((cell) => (
            <div
              key={cell.label}
              className="rounded-xl border border-white/10 bg-white/[0.02] p-3"
            >
              <dt className="font-ui text-[10px] uppercase tracking-widest text-text-secondary">
                {cell.label}
              </dt>
              <dd className="mt-1 font-data text-lg text-text-primary">{cell.value}</dd>
            </div>
          ))}
        </dl>
      )}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <JsonSlice title="Request" data={requestPayload} accent="cyan" />
        <JsonSlice title="Response" data={responsePayload} accent="gold" />
      </div>
    </div>
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

function JsonSlice({
  title,
  data,
  accent,
}: {
  title: string;
  data: Record<string, unknown>;
  accent: AccentName;
}) {
  const entries = data
    ? Object.entries(data).filter(([, v]) => v !== null && v !== undefined)
    : [];
  return (
    <article className="rounded-2xl border border-white/10 bg-white/[0.02] p-5">
      <header
        className={cn(
          'mb-3 font-ui text-[10px] uppercase tracking-widest',
          ACCENT_CLASSES[accent],
        )}
      >
        {title} payload
      </header>
      {entries.length === 0 ? (
        <p className="font-ui text-xs italic text-text-secondary">
          No {title.toLowerCase()} payload recorded.
        </p>
      ) : (
        <dl className="space-y-1.5 font-data text-[11px]">
          {entries.map(([key, value]) => (
            <div key={key} className="flex items-start gap-3">
              <dt className="w-36 shrink-0 truncate text-text-secondary">{key}</dt>
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
