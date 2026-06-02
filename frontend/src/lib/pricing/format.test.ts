/**
 * Pricing format + chart geometry tests — pure functions, no React.
 */

import { describe, expect, it } from 'vitest';

import {
  curveScale,
  formatCurrency,
  formatUplift,
  objectiveLabel,
  pickY,
  projectPoint,
  upliftTone,
  yAxisLabel,
} from './format';
import type { PricePoint } from './types';

const POINTS: PricePoint[] = [
  { price: 10, expected_demand: 200, expected_revenue: 2000, expected_profit: 1000 },
  { price: 12, expected_demand: 175, expected_revenue: 2100, expected_profit: 1200 },
  { price: 15, expected_demand: 140, expected_revenue: 2100, expected_profit: 1400 },
  { price: 18, expected_demand: 110, expected_revenue: 1980, expected_profit: 1320 },
];

// ── formatCurrency ─────────────────────────────────────────────────

describe('formatCurrency', () => {
  it('formats a positive USD value', () => {
    // Locale-dependent; we only check that the symbol + value are present
    const formatted = formatCurrency(19.99);
    expect(formatted).toMatch(/\$/);
    expect(formatted).toMatch(/19\.99/);
  });

  it('returns em-dash for non-finite values', () => {
    expect(formatCurrency(Number.NaN)).toBe('—');
    expect(formatCurrency(Number.POSITIVE_INFINITY)).toBe('—');
  });

  it('falls back gracefully for an unknown currency code', () => {
    // Intl will throw; our wrapper returns a code prefix.
    const out = formatCurrency(5, 'XYZNOTREAL');
    expect(out).toMatch(/XYZNOTREAL/);
    expect(out).toMatch(/5\.00/);
  });
});

// ── formatUplift / upliftTone ──────────────────────────────────────

describe('formatUplift', () => {
  it('prefixes positive uplift with +', () => {
    expect(formatUplift(0.124)).toBe('+12.4%');
  });

  it('prefixes negative uplift with the U+2212 minus sign', () => {
    expect(formatUplift(-0.05)).toBe('−5.0%');
  });

  it('omits the sign on exactly zero', () => {
    expect(formatUplift(0)).toBe('0.0%');
  });

  it('respects custom precision', () => {
    expect(formatUplift(0.12345, 3)).toBe('+12.345%');
  });

  it('returns em-dash for non-finite input', () => {
    expect(formatUplift(Number.NaN)).toBe('—');
  });
});

describe('upliftTone', () => {
  it('returns cyan for positive uplift', () => {
    expect(upliftTone(0.05)).toBe('text-cyan');
  });
  it('returns coral for negative uplift', () => {
    expect(upliftTone(-0.05)).toBe('text-coral');
  });
  it('returns text-secondary for zero or invalid', () => {
    expect(upliftTone(0)).toBe('text-text-secondary');
    expect(upliftTone(Number.NaN)).toBe('text-text-secondary');
  });
});

// ── objectiveLabel / yAxisLabel / pickY ────────────────────────────

describe('objectiveLabel / yAxisLabel', () => {
  it('returns a unique label per objective', () => {
    expect(objectiveLabel('revenue')).toContain('revenue');
    expect(objectiveLabel('profit')).toContain('profit');
    expect(objectiveLabel('volume')).toContain('volume');
  });

  it('y-axis label tracks the objective', () => {
    expect(yAxisLabel('revenue')).toBe('Expected revenue');
    expect(yAxisLabel('profit')).toBe('Expected profit');
    expect(yAxisLabel('volume')).toBe('Expected demand');
  });
});

describe('pickY', () => {
  it('returns the right field for each objective', () => {
    expect(pickY(POINTS[0], 'revenue')).toBe(2000);
    expect(pickY(POINTS[0], 'profit')).toBe(1000);
    expect(pickY(POINTS[0], 'volume')).toBe(200);
  });
});

// ── curveScale ─────────────────────────────────────────────────────

describe('curveScale', () => {
  it('returns a degenerate scale on an empty curve', () => {
    expect(curveScale([], 'revenue')).toEqual({ xMin: 0, xMax: 1, yMin: 0, yMax: 1 });
  });

  it('captures the min/max price over the curve', () => {
    const s = curveScale(POINTS, 'revenue');
    expect(s.xMin).toBe(10);
    expect(s.xMax).toBe(18);
  });

  it('pads the y range by 5% on each side', () => {
    // revenue values are 2000, 2100, 2100, 1980 → range 1980..2100, 5% pad = 6
    const s = curveScale(POINTS, 'revenue');
    expect(s.yMin).toBeCloseTo(1974);
    expect(s.yMax).toBeCloseTo(2106);
  });

  it('uses the picked y field for profit/volume objectives', () => {
    const profit = curveScale(POINTS, 'profit');
    // profit values 1000..1400 → pad 5% of 400 = 20
    expect(profit.yMin).toBeCloseTo(980);
    expect(profit.yMax).toBeCloseTo(1420);
  });

  it('avoids a zero-height domain when every y is identical', () => {
    const flat: PricePoint[] = [
      { price: 1, expected_demand: 5, expected_revenue: 5, expected_profit: 5 },
      { price: 2, expected_demand: 5, expected_revenue: 5, expected_profit: 5 },
    ];
    const s = curveScale(flat, 'revenue');
    expect(s.yMin).toBeLessThan(s.yMax);
  });
});

// ── projectPoint ───────────────────────────────────────────────────

describe('projectPoint', () => {
  const scale = { xMin: 10, xMax: 20, yMin: 0, yMax: 100 };

  it('maps the lower-left of the data domain to (0, height)', () => {
    const p = projectPoint({ x: 10, y: 0 }, scale, 100, 50);
    expect(p.x).toBeCloseTo(0);
    expect(p.y).toBeCloseTo(50);
  });

  it('maps the upper-right of the data domain to (width, 0)', () => {
    const p = projectPoint({ x: 20, y: 100 }, scale, 100, 50);
    expect(p.x).toBeCloseTo(100);
    expect(p.y).toBeCloseTo(0);
  });

  it('flips the y axis so larger y reads upward', () => {
    const low = projectPoint({ x: 15, y: 25 }, scale, 100, 100);
    const high = projectPoint({ x: 15, y: 75 }, scale, 100, 100);
    expect(low.y).toBeGreaterThan(high.y);
  });

  it('tolerates a zero-width domain without dividing by zero', () => {
    const degenerate = { xMin: 5, xMax: 5, yMin: 0, yMax: 10 };
    const p = projectPoint({ x: 5, y: 5 }, degenerate, 100, 100);
    expect(Number.isFinite(p.x)).toBe(true);
    expect(Number.isFinite(p.y)).toBe(true);
  });
});
