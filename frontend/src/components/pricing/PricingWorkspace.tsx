'use client';

import Link from 'next/link';
import { useState } from 'react';

import { formatAuthError } from '@/lib/auth/errors';
import { useRunOptimizeMutation } from '@/lib/pricing/queries';
import type { PriceOptimizationRequest } from '@/lib/pricing/types';
import { moduleById } from '@/lib/modules';

import { OptimizeForm } from './OptimizeForm';
import { PricingResults } from './PricingResults';

/**
 * Pricing workspace — two-column layout matching the recruitment
 * workspace pattern (TASK-022). Wave 1 wires only the optimize flow;
 * Monte Carlo simulation, elasticity, and scenario comparison arrive
 * in wave 2 behind tabs.
 */
export function PricingWorkspace() {
  const meta = moduleById('pricing');
  const mutation = useRunOptimizeMutation();
  // The form is the source of truth for the request; we cache the
  // last-submitted payload so the results chart knows which objective
  // and price baseline to draw without re-deriving it from the form
  // state (which may have changed since submission).
  const [lastRequest, setLastRequest] = useState<PriceOptimizationRequest | null>(null);

  function handleSubmit(request: PriceOptimizationRequest) {
    setLastRequest(request);
    mutation.mutate(request);
  }

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
            href="/modules/pricing/analyses"
            className="shrink-0 font-ui text-xs text-text-secondary underline-offset-4 hover:text-text-primary hover:underline"
          >
            Past analyses →
          </Link>
        </div>
        <p className="mt-2 font-ui text-sm text-text-secondary">{meta.tagline}</p>
      </header>

      <div className="grid grid-cols-1 gap-8 xl:grid-cols-[minmax(0,_480px)_minmax(0,_1fr)]">
        <section
          aria-label="Optimise"
          className="rounded-2xl border border-white/10 bg-white/[0.02] p-6"
        >
          <h3 className="mb-4 font-ui text-base font-semibold text-text-primary">
            Optimise price
          </h3>
          <OptimizeForm onSubmit={handleSubmit} submitting={mutation.isPending} />
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
              Running LightGBM demand model + PPO pricing agent…
            </p>
          )}

          {!mutation.isPending && !mutation.data && !mutation.isError && (
            <p className="rounded-xl border border-dashed border-white/10 bg-white/[0.02] px-4 py-12 text-center font-ui text-sm text-text-secondary">
              Recommendations appear here once you run an analysis.
            </p>
          )}

          {mutation.data && lastRequest && (
            <PricingResults result={mutation.data} request={lastRequest} />
          )}
        </section>
      </div>
    </div>
  );
}
