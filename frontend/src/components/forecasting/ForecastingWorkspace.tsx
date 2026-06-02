'use client';

import Link from 'next/link';
import { useState } from 'react';

import { formatAuthError } from '@/lib/auth/errors';
import { useRunForecastMutation } from '@/lib/forecasting/queries';
import type { ForecastRequest } from '@/lib/forecasting/types';
import { moduleById } from '@/lib/modules';

import { ForecastForm } from './ForecastForm';
import { ForecastResults } from './ForecastResults';

/**
 * Forecasting workspace — matches TASK-022/023's two-column pattern.
 * Wave 1 wires only `/forecast`; sensitivity, what-if, and cross-
 * module endpoints arrive in wave 2 behind workspace tabs.
 */
export function ForecastingWorkspace() {
  const meta = moduleById('forecasting');
  const mutation = useRunForecastMutation();
  // Cache the last submitted history so the results chart can render
  // the observed baseline without re-parsing the form text (which
  // may have changed since submission).
  const [lastRequest, setLastRequest] = useState<ForecastRequest | null>(null);

  function handleSubmit(request: ForecastRequest) {
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
            href="/modules/forecasting/forecasts"
            className="shrink-0 font-ui text-xs text-text-secondary underline-offset-4 hover:text-text-primary hover:underline"
          >
            Past forecasts →
          </Link>
        </div>
        <p className="mt-2 font-ui text-sm text-text-secondary">{meta.tagline}</p>
      </header>

      <div className="grid grid-cols-1 gap-8 xl:grid-cols-[minmax(0,_440px)_minmax(0,_1fr)]">
        <section
          aria-label="Generate forecast"
          className="rounded-2xl border border-white/10 bg-white/[0.02] p-6"
        >
          <h3 className="mb-4 font-ui text-base font-semibold text-text-primary">
            Generate forecast
          </h3>
          <ForecastForm onSubmit={handleSubmit} submitting={mutation.isPending} />
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
              Running the forecast ensemble…
            </p>
          )}

          {!mutation.isPending && !mutation.data && !mutation.isError && (
            <p className="rounded-xl border border-dashed border-white/10 bg-white/[0.02] px-4 py-12 text-center font-ui text-sm text-text-secondary">
              Scenarios appear here once you run a forecast.
            </p>
          )}

          {mutation.data && lastRequest && (
            <ForecastResults
              response={mutation.data}
              history={lastRequest.history}
            />
          )}
        </section>
      </div>
    </div>
  );
}
