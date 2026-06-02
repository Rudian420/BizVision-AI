'use client';

import Link from 'next/link';

import { formatAuthError } from '@/lib/auth/errors';
import { moduleById } from '@/lib/modules';
import { useRunScoreMutation } from '@/lib/sustainability/queries';

import { ESGResults } from './ESGResults';
import { ScoreForm } from './ScoreForm';

/**
 * Sustainability workspace — matches TASK-022/023/024's two-column
 * pattern. Wave 1 wires only `/score`; /simulate, /recommendations,
 * /carbon-estimate arrive in wave 2 behind workspace tabs.
 */
export function SustainabilityWorkspace() {
  const meta = moduleById('sustainability');
  const mutation = useRunScoreMutation();

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
            href="/modules/sustainability/assessments"
            className="shrink-0 font-ui text-xs text-text-secondary underline-offset-4 hover:text-text-primary hover:underline"
          >
            Past assessments →
          </Link>
        </div>
        <p className="mt-2 font-ui text-sm text-text-secondary">{meta.tagline}</p>
      </header>

      <div className="grid grid-cols-1 gap-8 xl:grid-cols-[minmax(0,_440px)_minmax(0,_1fr)]">
        <section
          aria-label="Score ESG profile"
          className="rounded-2xl border border-white/10 bg-white/[0.02] p-6"
        >
          <h3 className="mb-4 font-ui text-base font-semibold text-text-primary">
            Score ESG profile
          </h3>
          <ScoreForm onSubmit={mutation.mutate} submitting={mutation.isPending} />
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
              Running multi-label ESG classifier + fairness audit…
            </p>
          )}

          {!mutation.isPending && !mutation.data && !mutation.isError && (
            <p className="rounded-xl border border-dashed border-white/10 bg-white/[0.02] px-4 py-12 text-center font-ui text-sm text-text-secondary">
              Composite score appears here once you run an assessment.
            </p>
          )}

          {mutation.data && <ESGResults result={mutation.data} />}
        </section>
      </div>
    </div>
  );
}
