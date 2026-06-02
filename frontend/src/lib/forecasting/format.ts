/**
 * Forecasting display formatters + chart geometry projectors.
 *
 * Kept here so the test suite can verify the math without rendering
 * React. Builds on `lib/chart/geometry.ts` for the shared scale +
 * projection helpers — same posture as `lib/pricing/format.ts`.
 */

import {
  isoDateToDayNumber,
  scaleFor,
  type ChartScale,
} from '@/lib/chart/geometry';

import type { ForecastPoint, ForecastResponse, ScenarioForecast, TimeSeriesPoint } from './types';

/** Compact ISO-date label for the x-axis (M/D form drops the year). */
export function formatShortDate(iso: string): string {
  const m = iso.match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (!m) return iso;
  const month = Number(m[2]);
  const day = Number(m[3]);
  return `${month}/${day}`;
}

/** Number with thousands separators + at-most-1-decimal precision. */
export function formatNumber(value: number, digits = 1): string {
  if (!Number.isFinite(value)) return '—';
  return new Intl.NumberFormat(undefined, {
    minimumFractionDigits: 0,
    maximumFractionDigits: digits,
  }).format(value);
}

/** Percentage with explicit + / − for scenario uplift display. */
export function formatPctChange(fraction: number, digits = 1): string {
  if (!Number.isFinite(fraction)) return '—';
  const pct = fraction * 100;
  const sign = pct > 0 ? '+' : pct < 0 ? '−' : '';
  return `${sign}${Math.abs(pct).toFixed(digits)}%`;
}

/** Stable scenario palette — cyan / gold / coral / violet fallback. */
export const SCENARIO_COLOURS: Record<string, string> = {
  base: '#00F5FF',
  bull: '#10F07C',
  bear: '#FF3B6B',
  adjusted: '#FFB800',
};

export function colorForScenario(name: string): string {
  return SCENARIO_COLOURS[name.toLowerCase()] ?? '#7C3AED';
}

/** Sort scenarios in a deterministic UI order (base → bull → bear → rest). */
const SCENARIO_ORDER: Record<string, number> = {
  base: 0,
  bull: 1,
  bear: 2,
};

export function orderedScenarios(
  response: ForecastResponse,
): { name: string; scenario: ScenarioForecast }[] {
  return Object.entries(response.scenarios)
    .map(([name, scenario]) => ({ name, scenario }))
    .sort((a, b) => {
      const ai = SCENARIO_ORDER[a.name.toLowerCase()] ?? 99;
      const bi = SCENARIO_ORDER[b.name.toLowerCase()] ?? 99;
      if (ai !== bi) return ai - bi;
      return a.name.localeCompare(b.name);
    });
}

/**
 * Compute a `ChartScale` over the supplied history + every scenario's
 * forecast points. The x-axis is a serial-day number computed by
 * `isoDateToDayNumber`; the y-axis covers the observed history,
 * scenario points (yhat), and PI bounds (yhat_lower / yhat_upper)
 * so both the line and the confidence band fit inside the frame.
 *
 * Returns a degenerate scale if everything is empty so the chart can
 * render without crashing.
 */
export function scenarioScale(
  history: readonly TimeSeriesPoint[],
  scenarios: readonly ScenarioForecast[],
): ChartScale {
  type Plot = { x: number; y: number };
  const all: Plot[] = [];
  for (const h of history) {
    all.push({ x: isoDateToDayNumber(h.ds), y: h.y });
  }
  for (const s of scenarios) {
    for (const p of s.points) {
      const x = isoDateToDayNumber(p.ds);
      all.push({ x, y: p.yhat });
      all.push({ x, y: p.yhat_lower });
      all.push({ x, y: p.yhat_upper });
    }
  }
  return scaleFor(
    all,
    (p) => p.x,
    (p) => p.y,
  );
}

/**
 * Project a scenario's `ForecastPoint[]` to three pixel-coord arrays:
 * the centre line (yhat), the upper edge (yhat_upper), and the lower
 * edge (yhat_lower). Consumed by `ScenarioChart` which renders the
 * line via `polylinePath` and the band via `bandPath` from the
 * shared geometry module.
 */
export function projectScenario(
  points: readonly ForecastPoint[],
  scale: ChartScale,
  width: number,
  height: number,
): {
  centre: { x: number; y: number }[];
  upper: { x: number; y: number }[];
  lower: { x: number; y: number }[];
} {
  const xRange = scale.xMax - scale.xMin || 1;
  const yRange = scale.yMax - scale.yMin || 1;
  const project = (xData: number, yData: number) => ({
    x: ((xData - scale.xMin) / xRange) * width,
    y: height - ((yData - scale.yMin) / yRange) * height,
  });

  const centre: { x: number; y: number }[] = [];
  const upper: { x: number; y: number }[] = [];
  const lower: { x: number; y: number }[] = [];
  for (const p of points) {
    const x = isoDateToDayNumber(p.ds);
    centre.push(project(x, p.yhat));
    upper.push(project(x, p.yhat_upper));
    lower.push(project(x, p.yhat_lower));
  }
  return { centre, upper, lower };
}

/**
 * Same projector for the observed history line — the chart renders
 * this as a dim baseline so the user can see where the forecast
 * picks up. Returns an empty array on an empty history.
 */
export function projectHistory(
  history: readonly TimeSeriesPoint[],
  scale: ChartScale,
  width: number,
  height: number,
): { x: number; y: number }[] {
  if (history.length === 0) return [];
  const xRange = scale.xMax - scale.xMin || 1;
  const yRange = scale.yMax - scale.yMin || 1;
  return history.map((h) => ({
    x: ((isoDateToDayNumber(h.ds) - scale.xMin) / xRange) * width,
    y: height - ((h.y - scale.yMin) / yRange) * height,
  }));
}

/**
 * Compute the fractional change from a baseline series end to a
 * scenario's end value. Used by the scenario cards' uplift chip.
 * Returns 0 when the baseline is 0 or NaN.
 */
export function endValueChange(baseline: number, scenario: number): number {
  if (!Number.isFinite(baseline) || baseline === 0 || !Number.isFinite(scenario)) {
    return 0;
  }
  return (scenario - baseline) / baseline;
}
