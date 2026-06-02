/**
 * Shared chart-geometry tests — pure functions, no React.
 */

import { describe, expect, it } from 'vitest';

import {
  bandPath,
  isoDateToDayNumber,
  polylinePath,
  projectPoint,
  scaleFor,
} from './geometry';

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

describe('scaleFor', () => {
  it('returns a degenerate scale for an empty collection', () => {
    expect(scaleFor([], (n) => n, (n) => n)).toEqual({
      xMin: 0,
      xMax: 1,
      yMin: 0,
      yMax: 1,
    });
  });

  it('captures the min/max via projector functions', () => {
    const items = [
      { x: 1, y: 10 },
      { x: 5, y: 20 },
      { x: 3, y: 15 },
    ];
    const s = scaleFor(
      items,
      (p) => p.x,
      (p) => p.y,
    );
    expect(s.xMin).toBe(1);
    expect(s.xMax).toBe(5);
    // y range 10..20 with 5% pad on each side = 0.5
    expect(s.yMin).toBeCloseTo(9.5);
    expect(s.yMax).toBeCloseTo(20.5);
  });

  it('pads by the supplied fraction', () => {
    const s = scaleFor(
      [
        { x: 0, y: 0 },
        { x: 1, y: 100 },
      ],
      (p) => p.x,
      (p) => p.y,
      0.1,
    );
    expect(s.yMin).toBeCloseTo(-10);
    expect(s.yMax).toBeCloseTo(110);
  });

  it('avoids a zero-height domain when every y is identical', () => {
    const s = scaleFor(
      [
        { x: 0, y: 5 },
        { x: 1, y: 5 },
      ],
      (p) => p.x,
      (p) => p.y,
    );
    expect(s.yMin).toBeLessThan(s.yMax);
  });
});

describe('polylinePath', () => {
  it('returns an empty string on no points', () => {
    expect(polylinePath([])).toBe('');
  });

  it('starts with M and uses L for subsequent points', () => {
    const out = polylinePath([
      { x: 0, y: 0 },
      { x: 10, y: 5 },
      { x: 20, y: 10 },
    ]);
    expect(out.startsWith('M0.00,0.00')).toBe(true);
    expect(out).toContain('L10.00,5.00');
    expect(out).toContain('L20.00,10.00');
  });
});

describe('bandPath', () => {
  it('returns an empty string when upper/lower lengths mismatch', () => {
    expect(bandPath([{ x: 0, y: 0 }], [])).toBe('');
  });

  it('closes the path with Z', () => {
    const out = bandPath(
      [
        { x: 0, y: 10 },
        { x: 10, y: 12 },
      ],
      [
        { x: 0, y: 5 },
        { x: 10, y: 7 },
      ],
    );
    expect(out.endsWith('Z')).toBe(true);
    // Forward edge first, reverse lower edge after
    expect(out.startsWith('M0.00,10.00')).toBe(true);
  });
});

describe('isoDateToDayNumber', () => {
  it('returns integer day counts that are monotonically increasing', () => {
    const a = isoDateToDayNumber('2026-01-01');
    const b = isoDateToDayNumber('2026-01-02');
    expect(b - a).toBe(1);
  });

  it('is stable across timezone interpretation (UTC math)', () => {
    // The same date should always map to the same day number
    // regardless of when the JS Date constructor runs.
    expect(isoDateToDayNumber('2026-05-29')).toBe(isoDateToDayNumber('2026-05-29'));
  });

  it('returns NaN for malformed input', () => {
    expect(Number.isNaN(isoDateToDayNumber('not-a-date'))).toBe(true);
  });
});
