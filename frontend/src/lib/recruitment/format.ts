/**
 * Display formatters + risk colour mapping for the recruitment UI.
 *
 * Kept here (not in components) so the test suite can verify them
 * without rendering React. Same posture as `lib/utils.ts`.
 */

import type { RiskLevel } from './types';

/** Map a 0..1 score to a percentage string with a fixed decimal. */
export function formatPercent(score: number, digits = 1): string {
  if (!Number.isFinite(score)) return '—';
  return `${(score * 100).toFixed(digits)}%`;
}

/** Two-decimal absolute SHAP value. */
export function formatShap(value: number): string {
  if (!Number.isFinite(value)) return '—';
  const sign = value > 0 ? '+' : value < 0 ? '−' : '';
  return `${sign}${Math.abs(value).toFixed(2)}`;
}

// Risk-tone palette + helper extracted to the shared `lib/risk/`
// module so sustainability (and any future module with a categorical
// risk band) reuses the same cyan / gold / coral / coral-deep
// palette. The re-exports below preserve the public API so the
// existing recruitment tests + components keep compiling without
// import-site changes.
export { RISK_TONES, toneForRisk, type RiskTone } from '@/lib/risk/tones';

/** Human-readable elapsed-time label (milliseconds → s/ms). */
export function formatElapsed(ms: number): string {
  if (!Number.isFinite(ms) || ms < 0) return '—';
  if (ms < 1000) return `${Math.round(ms)} ms`;
  return `${(ms / 1000).toFixed(2)} s`;
}
