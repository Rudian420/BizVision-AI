'use client';

import { bandPath, polylinePath } from '@/lib/chart/geometry';
import {
  colorForScenario,
  formatShortDate,
  orderedScenarios,
  projectHistory,
  projectScenario,
  scenarioScale,
} from '@/lib/forecasting/format';
import type { ForecastResponse, TimeSeriesPoint } from '@/lib/forecasting/types';

type ScenarioChartProps = {
  response: ForecastResponse;
  history: readonly TimeSeriesPoint[];
  width?: number;
  height?: number;
};

const PADDING = { top: 16, right: 28, bottom: 28, left: 28 } as const;

/**
 * SVG-based scenario chart.
 *
 * Renders the observed history as a dim baseline, then layers each
 * scenario (base / bull / bear / …) as a confidence band + centre
 * line in its accent colour. The x-axis uses serial day numbers via
 * `isoDateToDayNumber` so timezone shifts can't perturb the layout.
 *
 * Same discipline as the pricing revenue chart and the SHAP panel:
 * no chart library — inline SVG + shared geometry helpers from
 * `lib/chart/geometry.ts`. Bundle impact is a handful of TypeScript
 * helpers, not 50 KB of Recharts.
 */
export function ScenarioChart({
  response,
  history,
  width = 720,
  height = 300,
}: ScenarioChartProps) {
  const scenarios = orderedScenarios(response).map((s) => s.scenario);
  if (scenarios.length === 0) {
    return (
      <p className="font-ui text-xs text-text-secondary">
        Forecast has no scenarios to render.
      </p>
    );
  }

  const innerWidth = width - PADDING.left - PADDING.right;
  const innerHeight = height - PADDING.top - PADDING.bottom;
  const scale = scenarioScale(history, scenarios);

  const historyPoints = projectHistory(history, scale, innerWidth, innerHeight);
  const projectedScenarios = scenarios.map((scenario) => ({
    scenario,
    geometry: projectScenario(scenario.points, scale, innerWidth, innerHeight),
  }));

  // Compute the x position where the forecast picks up — the last
  // history date (or the first forecast date if no history was
  // supplied). Used to draw a faint divider so the user sees the
  // boundary at a glance.
  const firstScenarioCentre = projectedScenarios[0]?.geometry.centre[0];
  const forecastStartX = firstScenarioCentre?.x ?? innerWidth;

  return (
    <figure>
      <figcaption className="mb-2 flex items-baseline justify-between font-ui text-[10px] uppercase tracking-widest text-text-secondary">
        <span>{response.series_name} · {response.horizon_days}-day horizon</span>
        <span className="font-data normal-case text-text-secondary/70">
          MAPE {response.mape.toFixed(1)}%
        </span>
      </figcaption>

      <svg
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label={`Scenario forecast for ${response.series_name} over ${response.horizon_days} days`}
        className="h-auto w-full"
        preserveAspectRatio="none"
      >
        <g transform={`translate(${PADDING.left} ${PADDING.top})`}>
          {/* Frame */}
          <rect
            x={0}
            y={0}
            width={innerWidth}
            height={innerHeight}
            fill="rgba(255,255,255,0.01)"
            stroke="rgba(255,255,255,0.06)"
            strokeWidth={1}
          />

          {/* Forecast-boundary divider */}
          {forecastStartX > 0 && forecastStartX < innerWidth && (
            <line
              x1={forecastStartX}
              x2={forecastStartX}
              y1={0}
              y2={innerHeight}
              stroke="rgba(255,255,255,0.18)"
              strokeDasharray="2 4"
              strokeWidth={1}
            />
          )}

          {/* Observed history (dim baseline) */}
          {historyPoints.length >= 2 && (
            <path
              d={polylinePath(historyPoints)}
              fill="none"
              stroke="rgba(255,255,255,0.45)"
              strokeWidth={1.5}
              strokeLinejoin="round"
              strokeLinecap="round"
            />
          )}

          {/* Per-scenario band + centre line */}
          {projectedScenarios.map(({ scenario, geometry }) => {
            const accent = colorForScenario(scenario.scenario);
            return (
              <g key={scenario.scenario}>
                <path
                  d={bandPath(geometry.upper, geometry.lower)}
                  fill={accent}
                  fillOpacity={0.08}
                  stroke="none"
                />
                <path
                  d={polylinePath(geometry.centre)}
                  fill="none"
                  stroke={accent}
                  strokeWidth={2}
                  strokeLinejoin="round"
                  strokeLinecap="round"
                />
              </g>
            );
          })}
        </g>

        {/* X-axis date labels */}
        {history.length > 0 && (
          <text
            x={PADDING.left}
            y={height - 8}
            fill="rgba(255,255,255,0.4)"
            fontSize={10}
            fontFamily="JetBrains Mono"
          >
            {formatShortDate(history[0].ds)}
          </text>
        )}
        {projectedScenarios.length > 0 && (() => {
          const lastScenario = projectedScenarios[0].scenario;
          const lastPoint = lastScenario.points[lastScenario.points.length - 1];
          if (!lastPoint) return null;
          return (
            <text
              x={width - PADDING.right}
              y={height - 8}
              fill="rgba(255,255,255,0.4)"
              fontSize={10}
              fontFamily="JetBrains Mono"
              textAnchor="end"
            >
              {formatShortDate(lastPoint.ds)}
            </text>
          );
        })()}
      </svg>

      <ul className="mt-2 flex flex-wrap gap-x-5 gap-y-1 font-ui text-[10px] uppercase tracking-widest text-text-secondary">
        {history.length >= 2 && (
          <li className="flex items-center gap-2">
            <span aria-hidden className="inline-block h-0.5 w-4 bg-text-secondary/60" />
            <span>observed history</span>
          </li>
        )}
        {scenarios.map((scenario) => (
          <li key={scenario.scenario} className="flex items-center gap-2">
            <span
              aria-hidden
              className="inline-block h-0.5 w-4"
              style={{ background: colorForScenario(scenario.scenario) }}
            />
            <span>{scenario.scenario}</span>
          </li>
        ))}
      </ul>
    </figure>
  );
}
