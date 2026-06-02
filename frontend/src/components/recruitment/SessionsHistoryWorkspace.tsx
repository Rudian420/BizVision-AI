'use client';

import Link from 'next/link';
import { useState } from 'react';

import { DateRangeFilter } from '@/components/common/DateRangeFilter';
import { formatAuthError } from '@/lib/auth/errors';
import { useSessionsListQuery } from '@/lib/recruitment/queries';
import { moduleById } from '@/lib/modules';
import { cn } from '@/lib/utils';

const PAGE_SIZE = 20;

/**
 * Recruitment session history — paged list of past `/analyze` runs,
 * each row deep-links into the session detail view (TASK-032). Backed
 * by `GET /api/v1/recruitment/sessions`. Lives at
 * `/modules/recruitment/sessions`.
 *
 * Header echoes the per-module accent palette so the page sits inside
 * the module workspace shell visually. Empty + loading states match
 * the Decision Feed's posture for consistency.
 */
export function SessionsHistoryWorkspace() {
  const meta = moduleById('recruitment');
  const [page, setPage] = useState(1);
  const [since, setSince] = useState<string | null>(null);
  const [until, setUntil] = useState<string | null>(null);
  const query = useSessionsListQuery(page, PAGE_SIZE, since, until);

  const items = query.data?.items ?? [];
  const total = query.data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const errorMessage = query.isError ? formatAuthError(query.error) : null;

  function handleDateChange(next: { since: string | null; until: string | null }) {
    setSince(next.since);
    setUntil(next.until);
    setPage(1);
  }

  return (
    <div className="flex flex-col gap-6">
      <header className="border-b border-white/10 pb-6">
        <div className="mb-2 flex items-center gap-3">
          <span className="font-data text-3xl" style={{ color: meta.accent }}>
            {meta.glyph}
          </span>
          <span className="font-ui text-[10px] uppercase tracking-widest text-text-secondary">
            recruitment · history
          </span>
        </div>
        <h2 className="font-ui text-3xl font-semibold tracking-tight text-text-primary">
          Past sessions
        </h2>
        <p className="mt-2 max-w-2xl font-ui text-sm text-text-secondary">
          Every recruitment analysis you&apos;ve run, newest first. Open one to see the persisted
          candidates ranking + SHAP attributions + fairness audit.
        </p>
      </header>

      <DateRangeFilter since={since} until={until} onChange={handleDateChange} />

      {errorMessage && (
        <p
          role="alert"
          className="rounded-md border border-coral/40 bg-coral/10 px-3 py-2 font-ui text-sm text-coral"
        >
          {errorMessage}
        </p>
      )}

      {query.isLoading && items.length === 0 ? (
        <SessionsSkeleton />
      ) : items.length === 0 ? (
        <p
          role="status"
          className="rounded-2xl border border-white/10 bg-white/[0.02] p-12 text-center font-ui text-sm text-text-secondary"
        >
          You haven&apos;t run any recruitment analyses yet. Head back to{' '}
          <Link
            href="/modules/recruitment"
            className="text-text-primary underline-offset-4 hover:underline"
          >
            the workspace
          </Link>{' '}
          to kick one off.
        </p>
      ) : (
        <ul aria-label="Recruitment session history" className="flex flex-col gap-2">
          {items.map((row) => (
            <li key={row.session_id}>
              <Link
                href={`/modules/recruitment/sessions/${row.session_id}`}
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
                    {row.job_title}
                  </span>
                  <span className="font-data text-[11px] text-text-secondary">
                    {row.total_candidates} candidate{row.total_candidates === 1 ? '' : 's'}
                    {' · '}
                    {row.model_version}
                  </span>
                </span>
                <span className="font-ui text-xs text-text-secondary">
                  {new Date(row.created_at).toISOString().slice(0, 10)}
                </span>
                <span aria-hidden className="font-data text-text-secondary">
                  ›
                </span>
              </Link>
            </li>
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
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page <= 1}
            className="rounded-md border border-white/10 px-3 py-1 transition hover:border-white/30 disabled:cursor-not-allowed disabled:opacity-30"
          >
            Prev
          </button>
          <button
            type="button"
            onClick={() => setPage((p) => p + 1)}
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

function SessionsSkeleton() {
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
