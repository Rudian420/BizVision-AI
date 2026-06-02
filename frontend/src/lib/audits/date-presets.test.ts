/**
 * Tests for the date-range preset resolvers used by
 * `<DateRangeFilter />`'s quick-range chip strip (TASK-038).
 *
 * Each preset is a pure function of `now` so we anchor every test to
 * a deterministic clock — no need for vi.useFakeTimers or system time
 * mocking. The resolver outputs are local-calendar ISO dates, so we
 * also assert that the format is `YYYY-MM-DD` (no surprise timezone
 * shift).
 */

import { describe, expect, it } from 'vitest';

import {
  DATE_RANGE_PRESETS,
  matchingPresetId,
  resolvePreset,
  toISODate,
} from './date-presets';

// Anchor: 2026-05-15 (a Friday) — picked so the start-of-month +
// end-of-month resolvers have non-trivial work, and "last month" =
// April (30 days).
const NOW = new Date(2026, 4, 15, 14, 30, 0); // month is 0-indexed: 4 = May

describe('toISODate', () => {
  it('formats a Date as YYYY-MM-DD in local calendar terms', () => {
    expect(toISODate(NOW)).toBe('2026-05-15');
  });

  it('zero-pads single-digit months and days', () => {
    expect(toISODate(new Date(2026, 0, 3))).toBe('2026-01-03');
  });

  it('does NOT shift to UTC (avoids off-by-one across midnight in negative offsets)', () => {
    // 23:59 local on May 15 is still 2026-05-15, not 2026-05-16 or
    // 2026-05-15 depending on timezone — toISOString() would have
    // emitted UTC and possibly bumped the day. Our helper stays local.
    expect(toISODate(new Date(2026, 4, 15, 23, 59, 59))).toBe('2026-05-15');
  });
});

describe('DATE_RANGE_PRESETS exposes 5 stable presets', () => {
  it('exports exactly 5 presets in a stable order', () => {
    expect(DATE_RANGE_PRESETS.map((p) => p.id)).toEqual([
      'last7',
      'last30',
      'this-month',
      'last-month',
      'this-year',
    ]);
  });

  it('every preset has a human-readable label', () => {
    for (const p of DATE_RANGE_PRESETS) {
      expect(p.label.length).toBeGreaterThan(0);
    }
  });
});

describe('resolvePreset — last 7 / last 30', () => {
  it('last7 covers the trailing 7 days inclusive of today', () => {
    expect(resolvePreset('last7', NOW)).toEqual({
      since: '2026-05-09',
      until: '2026-05-15',
    });
  });

  it('last30 covers the trailing 30 days inclusive of today', () => {
    expect(resolvePreset('last30', NOW)).toEqual({
      since: '2026-04-16',
      until: '2026-05-15',
    });
  });
});

describe('resolvePreset — this-month / last-month / this-year', () => {
  it('this-month spans 1st → last day of the current month', () => {
    expect(resolvePreset('this-month', NOW)).toEqual({
      since: '2026-05-01',
      until: '2026-05-31',
    });
  });

  it('last-month spans 1st → last day of the previous month', () => {
    // April 2026 has 30 days
    expect(resolvePreset('last-month', NOW)).toEqual({
      since: '2026-04-01',
      until: '2026-04-30',
    });
  });

  it('last-month handles a January `now` (rolls back to previous year)', () => {
    const jan = new Date(2026, 0, 10);
    expect(resolvePreset('last-month', jan)).toEqual({
      since: '2025-12-01',
      until: '2025-12-31',
    });
  });

  it('this-year spans Jan 1 → Dec 31 of the current year', () => {
    expect(resolvePreset('this-year', NOW)).toEqual({
      since: '2026-01-01',
      until: '2026-12-31',
    });
  });

  it('unknown preset id throws', () => {
    // @ts-expect-error — intentionally invalid id
    expect(() => resolvePreset('mystery', NOW)).toThrow();
  });
});

describe('matchingPresetId — round-trip matching for chip aria-pressed', () => {
  it('returns the preset id when bounds equal a preset resolution', () => {
    const r = resolvePreset('this-month', NOW);
    expect(matchingPresetId(r.since, r.until, NOW)).toBe('this-month');
  });

  it('returns null when bounds match no preset', () => {
    expect(matchingPresetId('2026-05-03', '2026-05-09', NOW)).toBeNull();
  });

  it('returns null when either bound is unset', () => {
    expect(matchingPresetId(null, '2026-05-31', NOW)).toBeNull();
    expect(matchingPresetId('2026-05-01', null, NOW)).toBeNull();
    expect(matchingPresetId(null, null, NOW)).toBeNull();
  });

  it('matches last7 exactly', () => {
    const r = resolvePreset('last7', NOW);
    expect(matchingPresetId(r.since, r.until, NOW)).toBe('last7');
  });
});
