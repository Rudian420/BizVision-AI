/**
 * Display formatters + chart geometry helpers for the pricing UI.
 *
 * Kept here (not in components) so the test suite can verify them
 * without rendering React. Same posture as
 * `lib/recruitment/format.ts`.
 */

import type { PricePoint, PricingObjective } from './types';

/** Format a currency amount with the user's locale + 2 decimal precision. */
export function formatCurrency(amount: number, currency: string = 'USD'): string {
  if (!Number.isFinite(amount)) return '—';
  try {
    return new Intl.NumberFormat(undefined, {
      style: 'currency',
      currency,
      maximumFractionDigits: 2,
    }).format(amount);
  } catch {
    // Unknown currency code — fall back to a plain prefix so the UI
    // still renders something useful.
    return `${currency} ${amount.toFixed(2)}`;
  }
}

/** Signed percentage with explicit + / − for uplift display. */
export function formatUplift(fraction: number, digits: number = 1): string {
  if (!Number.isFinite(fraction)) return '—';
  const pct = fraction * 100;
  const sign = pct > 0 ? '+' : pct < 0 ? '−' : '';
  return `${sign}${Math.abs(pct).toFixed(digits)}%`;
}

/** Tailwind text-colour utility for a signed uplift value. */
export function upliftTone(fraction: number): string {
  if (!Number.isFinite(fraction) || fraction === 0) return 'text-text-secondary';
  return fraction > 0 ? 'text-cyan' : 'text-coral';
}

/** Human-friendly label for a pricing objective. */
export function objectiveLabel(objective: PricingObjective): string {
  switch (objective) {
    case 'revenue':
      return 'Maximise revenue';
    case 'profit':
      return 'Maximise profit';
    case 'volume':
      return 'Maximise volume';
  }
}

/**
 * Pick the y-axis value from a `PricePoint` for the active objective.
 * Used by the revenue-curve chart so the same component handles all
 * three objectives without branching at the call site.
 */
export function pickY(point: PricePoint, objective: PricingObjective): number {
  switch (objective) {
    case 'revenue':
      return point.expected_revenue;
    case 'profit':
      return point.expected_profit;
    case 'volume':
      return point.expected_demand;
  }
}

/** Axis label for the chart y-axis given the active objective. */
export function yAxisLabel(objective: PricingObjective): string {
  switch (objective) {
    case 'revenue':
      return 'Expected revenue';
    case 'profit':
      return 'Expected profit';
    case 'volume':
      return 'Expected demand';
  }
}

// ── Chart geometry ─────────────────────────────────────────────────

// Re-exports from the shared chart-geometry module so existing
// imports (`@/lib/pricing/format` ↔ `curveScale`, `projectPoint`,
// `ChartScale`) keep working. The shared module is the source of
// truth; this thin layer just supplies the pricing-specific
// projector. Forecasting will follow the same pattern.
export type { ChartScale } from '@/lib/chart/geometry';
export { projectPoint } from '@/lib/chart/geometry';

import { scaleFor, type ChartScale as _Scale } from '@/lib/chart/geometry';

/**
 * Compute (xMin, xMax, yMin, yMax) for a revenue curve under a given
 * objective. Delegates to the shared `scaleFor` helper with pricing-
 * specific projectors. Returns a degenerate but valid scale on an
 * empty curve so the caller doesn't have to special-case rendering.
 */
export function curveScale(curve: PricePoint[], objective: PricingObjective): _Scale {
  return scaleFor(
    curve ?? [],
    (p) => p.price,
    (p) => pickY(p, objective),
  );
}
