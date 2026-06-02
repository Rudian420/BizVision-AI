/**
 * Display-formatting helpers for the audit-log timeline + cards.
 *
 * Mirrors the posture used by the chatbot module's `format.ts`:
 * pure functions, tested in isolation, no React imports. Relative-
 * time bucketing matches the chatbot's `formatRelativeTime` so the
 * "just now" / "Xm ago" feel is consistent across the app.
 */

import type { AuditModuleName } from './types';

/** Bucket sizes — same boundaries as `chatbot/format.formatRelativeTime`. */
const ONE_MINUTE_MS = 60_000;
const ONE_HOUR_MS = 60 * ONE_MINUTE_MS;
const ONE_DAY_MS = 24 * ONE_HOUR_MS;

export function formatAuditTimestamp(iso: string, now: Date = new Date()): string {
  const ts = new Date(iso).getTime();
  if (Number.isNaN(ts)) return 'unknown';

  const delta = now.getTime() - ts;
  if (delta < ONE_MINUTE_MS) return 'just now';
  if (delta < ONE_HOUR_MS) return `${Math.floor(delta / ONE_MINUTE_MS)}m ago`;
  if (delta < ONE_DAY_MS) return `${Math.floor(delta / ONE_HOUR_MS)}h ago`;
  if (delta < 2 * ONE_DAY_MS) return 'yesterday';
  if (delta < 7 * ONE_DAY_MS) return `${Math.floor(delta / ONE_DAY_MS)}d ago`;
  return new Date(iso).toISOString().slice(0, 10);
}

/** Title-case action names for the timeline. `analyze` → `Analyze`,
 * `stream_message` → `Stream Message`. */
export function formatAction(action: string): string {
  return action
    .split('_')
    .map((segment) => segment.charAt(0).toUpperCase() + segment.slice(1).toLowerCase())
    .join(' ');
}

/** Format a latency in ms — sub-second uses ms, otherwise s with one
 * decimal. Returns null when the value is 0 (or close to it) so the
 * timeline can hide the column rather than show a noisy "0ms". */
export function formatLatency(ms: number): string | null {
  if (!Number.isFinite(ms) || ms <= 0.05) return null;
  if (ms < 1000) return `${Math.round(ms)}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

/** A risk_tier slice in the summary histogram might be unset for
 * non-fairness modules. Render `unscored` as the bucket label so the
 * chart doesn't show a blank entry. */
export function formatRiskTierLabel(tier: string | null | undefined): string {
  if (!tier || tier === 'null') return 'unscored';
  return tier.toLowerCase();
}

/** Sort order used by both the summary cards and the chip filter.
 * Stable order = stable visual layout across renders. */
export const MODULE_ORDER: readonly AuditModuleName[] = [
  'recruitment',
  'pricing',
  'forecasting',
  'sustainability',
  'chatbot',
] as const;

export const RISK_TIER_ORDER: readonly string[] = ['low', 'medium', 'high', 'critical'] as const;

/** Format a [0, 1] pass rate as a percentage with no decimals.
 * Values outside [0, 1] are clamped before rendering — the backend
 * Pydantic schema already enforces the range, but defensive clamping
 * keeps the UI stable against a future API drift. */
export function formatPassRate(rate: number): string {
  if (!Number.isFinite(rate)) return '—';
  const clamped = Math.max(0, Math.min(1, rate));
  return `${Math.round(clamped * 100)}%`;
}

/** Tone keyword for a pass rate — feeds into a tailwind class lookup.
 * Thresholds reflect the recruitment risk module's 4/5ths-rule
 * posture: ≥80% pass rate is healthy (low risk), 60..80 is medium,
 * 40..60 high, <40 critical. */
export function passRateTier(rate: number): 'low' | 'medium' | 'high' | 'critical' {
  if (!Number.isFinite(rate) || rate >= 0.8) return 'low';
  if (rate >= 0.6) return 'medium';
  if (rate >= 0.4) return 'high';
  return 'critical';
}

/** Resolve the audit row's `(reference_type, reference_id)` soft FK
 * into a per-module deep-link, or null if the reference_type is
 * unknown.
 *
 * 5/5 module reference_types are wired as of TASK-034:
 *   • TASK-032 wired `recruitment_session`
 *   • TASK-033 wired `pricing_analysis` / `forecast_analysis` /
 *     `sustainability_assessment`
 *   • TASK-034 wired `chatbot_message` (lands on a transition page
 *     that resolves the message → conversation_id and redirects into
 *     the chatbot workspace with that conversation loaded) +
 *     `chatbot_executive_report` (lands on a dedicated executive-
 *     report detail page using the shared persisted-detail layout). */
export function auditReferenceLink(
  referenceType: string | null,
  referenceId: string | null,
): string | null {
  if (!referenceType || !referenceId) return null;
  switch (referenceType) {
    case 'recruitment_session':
      return `/modules/recruitment/sessions/${referenceId}`;
    case 'pricing_analysis':
      return `/modules/pricing/analyses/${referenceId}`;
    case 'forecast_analysis':
      return `/modules/forecasting/forecasts/${referenceId}`;
    case 'sustainability_assessment':
      return `/modules/sustainability/assessments/${referenceId}`;
    case 'chatbot_message':
      return `/modules/chatbot/messages/${referenceId}`;
    case 'chatbot_executive_report':
      return `/modules/chatbot/reports/${referenceId}`;
    default:
      return null;
  }
}
