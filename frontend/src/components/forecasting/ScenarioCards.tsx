'use client';

import {
  colorForScenario,
  endValueChange,
  formatNumber,
  formatPctChange,
  orderedScenarios,
} from '@/lib/forecasting/format';
import type { ForecastResponse } from '@/lib/forecasting/types';
import { cn } from '@/lib/utils';

type ScenarioCardsProps = {
  response: ForecastResponse;
};

/**
 * One card per scenario — end value, cumulative value, and uplift
 * vs the `base` scenario. Same role as pricing's `RecommendationCard`:
 * a headline-stat strip that reads at a glance.
 */
export function ScenarioCards({ response }: ScenarioCardsProps) {
  const scenarios = orderedScenarios(response);
  if (scenarios.length === 0) {
    return null;
  }
  const baseline = response.scenarios.base?.end_value;
  const hasBaseline = typeof baseline === 'number' && Number.isFinite(baseline);

  return (
    <section
      aria-label="Scenario summary"
      className="grid grid-cols-1 gap-3 sm:grid-cols-3"
    >
      {scenarios.map(({ name, scenario }) => {
        const colour = colorForScenario(name);
        const isBase = name.toLowerCase() === 'base';
        const change = hasBaseline && !isBase ? endValueChange(baseline, scenario.end_value) : 0;
        const showChange = hasBaseline && !isBase;
        const tone = !showChange
          ? 'text-text-secondary'
          : change > 0
            ? 'text-cyan'
            : change < 0
              ? 'text-coral'
              : 'text-text-secondary';

        return (
          <div
            key={name}
            className="rounded-xl border border-white/10 bg-white/[0.02] p-4"
            style={{ boxShadow: `inset 3px 0 0 ${colour}` }}
          >
            <div className="font-ui text-[10px] uppercase tracking-widest text-text-secondary">
              {name}
            </div>
            <div
              className="mt-1 font-data text-2xl font-semibold"
              style={{ color: colour }}
            >
              {formatNumber(scenario.end_value)}
            </div>
            <div className="mt-1 font-ui text-xs text-text-secondary">
              cumulative {formatNumber(scenario.cumulative_value)}
            </div>
            {showChange && (
              <div className={cn('mt-2 font-data text-sm', tone)}>
                {formatPctChange(change)} vs base
              </div>
            )}
          </div>
        );
      })}
    </section>
  );
}
