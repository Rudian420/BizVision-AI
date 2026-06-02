'use client';

import Link from 'next/link';

import { AnalyzeForm } from './AnalyzeForm';
import { AnalysisResults } from './AnalysisResults';
import { useRunAnalysisMutation } from '@/lib/recruitment/queries';
import { formatAuthError } from '@/lib/auth/errors';
import { moduleById } from '@/lib/modules';

/**
 * Two-column workspace: analyze form on the left, results on the
 * right. Below `xl` they stack so the form stays usable on smaller
 * viewports. The `useRunAnalysisMutation` hook drives the data
 * boundary — submission errors surface via `formatAuthError` (the
 * same JSON-shape handler used by the auth pages; the backend's
 * error contract is uniform).
 */
export function RecruitmentWorkspace() {
  const meta = moduleById('recruitment');
  const mutation = useRunAnalysisMutation();

  return (
    <div>
      <header className="mb-8 border-b border-white/10 pb-6">
        <div className="mb-2 flex items-center gap-3">
          <span className="font-data text-3xl" style={{ color: meta.accent }}>
            {meta.glyph}
          </span>
          <span className="font-ui text-[10px] uppercase tracking-widest text-text-secondary">
            {meta.id} module
          </span>
        </div>
        <div className="flex items-baseline justify-between gap-4">
          <h2 className="font-ui text-3xl font-semibold tracking-tight text-text-primary">
            {meta.label}
          </h2>
          <Link
            href="/modules/recruitment/sessions"
            className="shrink-0 font-ui text-xs text-text-secondary underline-offset-4 hover:text-text-primary hover:underline"
          >
            Past sessions →
          </Link>
        </div>
        <p className="mt-2 font-ui text-sm text-text-secondary">{meta.tagline}</p>
      </header>

      <div className="grid grid-cols-1 gap-8 xl:grid-cols-[minmax(0,_480px)_minmax(0,_1fr)]">
        <section
          aria-label="Run analysis"
          className="rounded-2xl border border-white/10 bg-white/[0.02] p-6"
        >
          <h3 className="mb-4 font-ui text-base font-semibold text-text-primary">Run analysis</h3>
          <AnalyzeForm onSubmit={mutation.mutate} submitting={mutation.isPending} />
        </section>

        <section aria-label="Results">
          {mutation.isError && (
            <p
              role="alert"
              className="mb-4 rounded-md border border-coral/40 bg-coral/10 px-3 py-2 font-ui text-sm text-coral"
            >
              {formatAuthError(mutation.error)}
            </p>
          )}

          {mutation.isPending && (
            <p
              role="status"
              aria-live="polite"
              className="rounded-xl border border-white/10 bg-white/[0.02] px-4 py-12 text-center font-ui text-sm text-text-secondary"
            >
              Ranking candidates with SBERT + XGBoost ensemble…
            </p>
          )}

          {!mutation.isPending && !mutation.data && !mutation.isError && (
            <p className="rounded-xl border border-dashed border-white/10 bg-white/[0.02] px-4 py-12 text-center font-ui text-sm text-text-secondary">
              Results appear here once you run an analysis.
            </p>
          )}

          {mutation.data && <AnalysisResults result={mutation.data} />}
        </section>
      </div>
    </div>
  );
}
