/**
 * Tests for the audit-log display helpers.
 *
 * Same posture as `lib/chatbot/format.test.ts` — pure functions, no
 * React, deterministic time-anchored assertions. Run via vitest.
 */

import { describe, expect, it } from 'vitest';

import {
  MODULE_ORDER,
  RISK_TIER_ORDER,
  auditReferenceLink,
  formatAction,
  formatAuditTimestamp,
  formatLatency,
  formatPassRate,
  formatRiskTierLabel,
  passRateTier,
} from './format';

// ── formatAuditTimestamp ─────────────────────────────────────────

describe('formatAuditTimestamp', () => {
  const NOW = new Date('2026-05-30T12:00:00Z');

  it("returns 'just now' for deltas under one minute", () => {
    const ten_seconds_ago = new Date(NOW.getTime() - 10_000).toISOString();
    expect(formatAuditTimestamp(ten_seconds_ago, NOW)).toBe('just now');
  });

  it('floors minute deltas under one hour', () => {
    const five_min_ago = new Date(NOW.getTime() - 5 * 60_000).toISOString();
    expect(formatAuditTimestamp(five_min_ago, NOW)).toBe('5m ago');
  });

  it('floors hour deltas under one day', () => {
    const three_h_ago = new Date(NOW.getTime() - 3 * 3_600_000).toISOString();
    expect(formatAuditTimestamp(three_h_ago, NOW)).toBe('3h ago');
  });

  it("returns 'yesterday' for deltas in [1d, 2d)", () => {
    const thirty_h_ago = new Date(NOW.getTime() - 30 * 3_600_000).toISOString();
    expect(formatAuditTimestamp(thirty_h_ago, NOW)).toBe('yesterday');
  });

  it('returns Xd ago in the 2..6 day window', () => {
    const three_d_ago = new Date(NOW.getTime() - 3 * 86_400_000).toISOString();
    expect(formatAuditTimestamp(three_d_ago, NOW)).toBe('3d ago');
  });

  it('falls back to ISO date for deltas >= 7 days', () => {
    const eight_d_ago = new Date(NOW.getTime() - 8 * 86_400_000).toISOString();
    // The ISO date is whatever 8 days before NOW is.
    const expected = new Date(NOW.getTime() - 8 * 86_400_000).toISOString().slice(0, 10);
    expect(formatAuditTimestamp(eight_d_ago, NOW)).toBe(expected);
  });

  it("returns 'unknown' for an unparseable ISO string", () => {
    expect(formatAuditTimestamp('not-a-date', NOW)).toBe('unknown');
  });
});

// ── formatAction ─────────────────────────────────────────────────

describe('formatAction', () => {
  it('title-cases a single-word action', () => {
    expect(formatAction('analyze')).toBe('Analyze');
  });

  it('title-cases each underscore-separated segment', () => {
    expect(formatAction('stream_message')).toBe('Stream Message');
    expect(formatAction('executive_report')).toBe('Executive Report');
    expect(formatAction('carbon_estimate')).toBe('Carbon Estimate');
  });

  it('handles a mixed-case input by normalising', () => {
    expect(formatAction('Cross_Module')).toBe('Cross Module');
  });
});

// ── formatLatency ────────────────────────────────────────────────

describe('formatLatency', () => {
  it('returns null for non-positive / sub-noise values', () => {
    expect(formatLatency(0)).toBeNull();
    expect(formatLatency(-1)).toBeNull();
    expect(formatLatency(0.04)).toBeNull();
  });

  it('returns null for non-finite values', () => {
    expect(formatLatency(Number.NaN)).toBeNull();
    expect(formatLatency(Number.POSITIVE_INFINITY)).toBeNull();
  });

  it('renders sub-second latencies in milliseconds', () => {
    expect(formatLatency(42)).toBe('42ms');
    expect(formatLatency(999.4)).toBe('999ms');
  });

  it('renders >= 1 second in seconds with one decimal', () => {
    expect(formatLatency(1500)).toBe('1.5s');
    expect(formatLatency(12345)).toBe('12.3s');
  });
});

// ── formatRiskTierLabel ──────────────────────────────────────────

describe('formatRiskTierLabel', () => {
  it("returns 'unscored' for null / undefined / 'null' inputs", () => {
    expect(formatRiskTierLabel(null)).toBe('unscored');
    expect(formatRiskTierLabel(undefined)).toBe('unscored');
    expect(formatRiskTierLabel('null')).toBe('unscored');
  });

  it('lowercases all known tier names', () => {
    expect(formatRiskTierLabel('LOW')).toBe('low');
    expect(formatRiskTierLabel('Critical')).toBe('critical');
  });
});

// ── formatPassRate (TASK-031) ────────────────────────────────────

describe('formatPassRate', () => {
  it('renders [0, 1] as a percentage with no decimals', () => {
    expect(formatPassRate(0)).toBe('0%');
    expect(formatPassRate(0.5)).toBe('50%');
    expect(formatPassRate(1)).toBe('100%');
  });

  it('rounds at 0.5 boundary', () => {
    // 0.005 → 0.5% → rounds to 1% under Math.round (banker's round
    // applies only to .5 ties; 0.005 * 100 = 0.5 exactly which rounds
    // up under Math.round)
    expect(formatPassRate(0.005)).toBe('1%');
    expect(formatPassRate(0.504)).toBe('50%');
    expect(formatPassRate(0.506)).toBe('51%');
  });

  it('clamps out-of-range inputs to [0, 1]', () => {
    expect(formatPassRate(-0.2)).toBe('0%');
    expect(formatPassRate(1.5)).toBe('100%');
  });

  it("returns '—' for non-finite values", () => {
    expect(formatPassRate(Number.NaN)).toBe('—');
    expect(formatPassRate(Number.POSITIVE_INFINITY)).toBe('—');
  });
});

// ── passRateTier (TASK-031) ──────────────────────────────────────

describe('passRateTier', () => {
  it("returns 'low' for rates >= 0.8 (4/5ths-rule healthy)", () => {
    expect(passRateTier(0.8)).toBe('low');
    expect(passRateTier(0.95)).toBe('low');
    expect(passRateTier(1)).toBe('low');
  });

  it("returns 'medium' for [0.6, 0.8)", () => {
    expect(passRateTier(0.6)).toBe('medium');
    expect(passRateTier(0.79)).toBe('medium');
  });

  it("returns 'high' for [0.4, 0.6)", () => {
    expect(passRateTier(0.4)).toBe('high');
    expect(passRateTier(0.59)).toBe('high');
  });

  it("returns 'critical' for rates < 0.4", () => {
    expect(passRateTier(0.39)).toBe('critical');
    expect(passRateTier(0)).toBe('critical');
  });

  it("defaults to 'low' for non-finite values (defensive)", () => {
    expect(passRateTier(Number.NaN)).toBe('low');
  });
});

// ── auditReferenceLink (TASK-032) ────────────────────────────────

describe('auditReferenceLink', () => {
  it('resolves recruitment_session to the per-session deep link', () => {
    expect(auditReferenceLink('recruitment_session', 'abc-123')).toBe(
      '/modules/recruitment/sessions/abc-123',
    );
  });

  it('resolves pricing_analysis to the per-analysis deep link (TASK-033)', () => {
    expect(auditReferenceLink('pricing_analysis', 'pa-1')).toBe(
      '/modules/pricing/analyses/pa-1',
    );
  });

  it('resolves forecast_analysis to the per-forecast deep link (TASK-033)', () => {
    expect(auditReferenceLink('forecast_analysis', 'fa-1')).toBe(
      '/modules/forecasting/forecasts/fa-1',
    );
  });

  it('resolves sustainability_assessment to the per-assessment deep link (TASK-033)', () => {
    expect(auditReferenceLink('sustainability_assessment', 'sa-1')).toBe(
      '/modules/sustainability/assessments/sa-1',
    );
  });

  it('resolves chatbot_message to the message transition page (TASK-034)', () => {
    expect(auditReferenceLink('chatbot_message', 'cm-1')).toBe(
      '/modules/chatbot/messages/cm-1',
    );
  });

  it('resolves chatbot_executive_report to its dedicated detail page (TASK-034)', () => {
    expect(auditReferenceLink('chatbot_executive_report', 'er-1')).toBe(
      '/modules/chatbot/reports/er-1',
    );
  });

  it('returns null when either side of the soft FK is missing', () => {
    expect(auditReferenceLink(null, 'abc')).toBeNull();
    expect(auditReferenceLink('recruitment_session', null)).toBeNull();
    expect(auditReferenceLink(null, null)).toBeNull();
  });

  it('returns null for unknown reference_types', () => {
    expect(auditReferenceLink('mystery_table', 'abc')).toBeNull();
  });
});

// ── order constants ──────────────────────────────────────────────

describe('MODULE_ORDER + RISK_TIER_ORDER', () => {
  it('exposes the 5 modules in the canonical UI sequence', () => {
    expect(MODULE_ORDER).toEqual([
      'recruitment',
      'pricing',
      'forecasting',
      'sustainability',
      'chatbot',
    ]);
  });

  it('exposes the 4 risk tiers low → critical', () => {
    expect(RISK_TIER_ORDER).toEqual(['low', 'medium', 'high', 'critical']);
  });
});
