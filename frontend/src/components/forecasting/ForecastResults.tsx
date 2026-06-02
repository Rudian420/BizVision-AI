'use client';

import { ShapPanel } from '@/components/shap/ShapPanel';
import type {
  ForecastResponse,
  TimeSeriesPoint,
} from '@/lib/forecasting/types';

import { ScenarioCards } from './ScenarioCards';
import { ScenarioChart } from './ScenarioChart';

type ForecastResultsProps = {
  response: ForecastResponse;
  history: readonly TimeSeriesPoint[];
};

export function ForecastResults({ response, history }: ForecastResultsProps) {
  return (
    <section aria-label="Forecast results" className="space-y-6">
      <header className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="font-ui text-base font-semibold text-text-primary">
          {response.series_name}
        </h3>
        <div className="font-ui text-xs text-text-secondary">
          forecast{' '}
          <span className="font-data text-text-secondary/80">
            {response.forecast_id.slice(0, 8)}
          </span>{' '}
          · {response.model_version}
        </div>
      </header>

      <ScenarioCards response={response} />

      <section
        aria-label="Scenario projection"
        className="rounded-xl border border-white/10 bg-white/[0.02] p-5"
      >
        <ScenarioChart response={response} history={history} />
      </section>

      <section
        aria-label="Primary drivers"
        className="rounded-xl border border-white/10 bg-white/[0.02] p-5"
      >
        <h3 className="mb-3 font-ui text-base font-semibold text-text-primary">
          Primary drivers
        </h3>
        <ShapPanel
          features={response.primary_drivers}
          emptyMessage="No driver attributions returned for this forecast."
        />
      </section>
    </section>
  );
}
