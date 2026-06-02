'use client';

import Link from 'next/link';
import type { ReactNode } from 'react';

import type { AIModule } from '@bizvision/contracts';

import { moduleById } from '@/lib/modules';
import { cn } from '@/lib/utils';

type ModuleHistoryShellProps<TItem> = {
  /** Module the history belongs to — drives the accent rail + glyph. */
  module: AIModule;
  /** Back-link target (typically the live workspace at `/modules/{m}`). */
  backHref: string;
  /** Back-link label, e.g. "Pricing workspace". */
  backLabel: string;
  /** Page header subtitle chip text. */
  scopeLabel: string;
  /** Page title. */
  title: string;
  /** Page tagline / lede paragraph. */
  tagline: string;
  /** Optional filter strip rendered above the list (chips, buttons, etc.). */
  filters?: ReactNode;

  /** Typed list rows. */
  items: TItem[];
  /** Loading state. */
  isLoading: boolean;
  /** Error message (already formatted). */
  errorMessage: string | null;

  /** Total row count for pagination caption. */
  total: number;
  /** 1-based current page. */
  page: number;
  /** Rows per page. */
  pageSize: number;
  /** Pagination cursor handler. */
  onPageChange: (page: number) => void;

  /** Per-row renderer. Each row should return a clickable Link to the
   * module's detail route. The shell wraps in <ul role="list">. */
  renderRow: (item: TItem) => ReactNode;
  /** Stable key extractor — usually the row's id field. */
  keyFor: (item: TItem) => string;

  /** Optional in-page action shown to the right of the title (e.g.
   * a "+ New analysis" link to the live workspace). */
  headerAction?: ReactNode;

  /** Empty-state copy. */
  emptyPrimary: string;
  /** Optional secondary CTA inside the empty state. */
  emptyAction?: ReactNode;
};

/**
 * Shared per-module history list shell (TASK-035). Used by:
 *   • `/modules/pricing/analyses`
 *   • `/modules/forecasting/forecasts`
 *   • `/modules/sustainability/assessments`
 *
 * The recruitment sessions list at `/modules/recruitment/sessions`
 * was the original template (TASK-032); this component consolidates
 * its header + list + skeleton + empty + pagination posture so the
 * 3 polymorphic-table modules share one renderer. Recruitment kept
 * its bespoke workspace because its empty-state copy + detail
 * caption shape predate this consolidation; the visual identity
 * matches.
 */
export function ModuleHistoryShell<TItem>({
  module,
  backHref,
  backLabel,
  scopeLabel,
  title,
  tagline,
  filters,
  items,
  isLoading,
  errorMessage,
  total,
  page,
  pageSize,
  onPageChange,
  renderRow,
  keyFor,
  headerAction,
  emptyPrimary,
  emptyAction,
}: ModuleHistoryShellProps<TItem>) {
  const meta = moduleById(module);
  const totalPages = Math.max(1, Math.ceil(total / pageSize));

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
            {title}
          </h2>
          {headerAction}
        </div>
        <p className="mt-2 max-w-2xl font-ui text-sm text-text-secondary">{tagline}</p>
      </header>

      {errorMessage && (
        <p
          role="alert"
          className="rounded-md border border-coral/40 bg-coral/10 px-3 py-2 font-ui text-sm text-coral"
        >
          {errorMessage}
        </p>
      )}

      {filters}

      {isLoading && items.length === 0 ? (
        <ListSkeleton />
      ) : items.length === 0 ? (
        <div
          role="status"
          className="rounded-2xl border border-white/10 bg-white/[0.02] p-12 text-center"
        >
          <p className="font-ui text-sm text-text-secondary">{emptyPrimary}</p>
          {emptyAction && <div className="mt-3">{emptyAction}</div>}
        </div>
      ) : (
        <ul aria-label={`${title} list`} className="flex flex-col gap-2">
          {items.map((item) => (
            <li key={keyFor(item)}>{renderRow(item)}</li>
          ))}
        </ul>
      )}

      <nav
        aria-label="Pagination"
        className={cn(
          'flex items-center justify-between border-t border-white/10 pt-3 font-ui text-xs text-text-secondary',
          items.length === 0 && 'hidden',
        )}
      >
        <span>
          Page {page} of {totalPages} · {total.toLocaleString()} total
        </span>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => onPageChange(Math.max(1, page - 1))}
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

function ListSkeleton() {
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
