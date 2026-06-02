/**
 * Sustainability format helper tests — pure functions, no React.
 */

import { describe, expect, it } from 'vitest';

import {
  formatScore,
  PILLAR_META,
  PILLAR_ORDER,
  pillarBarPercent,
  regulatoryRiskLabel,
  scoreTier,
  scoreTierTone,
} from './format';

describe('scoreTier', () => {
  it('returns strong for ≥ 75', () => {
    expect(scoreTier(75)).toBe('strong');
    expect(scoreTier(90)).toBe('strong');
  });

  it('returns above average for 55..74', () => {
    expect(scoreTier(55)).toBe('above average');
    expect(scoreTier(74.9)).toBe('above average');
  });

  it('returns below average for 35..54', () => {
    expect(scoreTier(35)).toBe('below average');
    expect(scoreTier(54.9)).toBe('below average');
  });

  it('returns critical for < 35 or NaN', () => {
    expect(scoreTier(20)).toBe('critical');
    expect(scoreTier(Number.NaN)).toBe('critical');
  });
});

describe('scoreTierTone', () => {
  it('returns one Tailwind utility per tier', () => {
    expect(scoreTierTone(80)).toBe('text-emerald');
    expect(scoreTierTone(60)).toBe('text-cyan');
    expect(scoreTierTone(40)).toBe('text-gold');
    expect(scoreTierTone(20)).toBe('text-coral');
  });
});

describe('PILLAR_META + PILLAR_ORDER', () => {
  it('exposes E/S/G in canonical order', () => {
    expect(PILLAR_ORDER).toEqual(['environmental', 'social', 'governance']);
  });

  it('every pillar has a glyph and accent', () => {
    for (const id of PILLAR_ORDER) {
      const meta = PILLAR_META[id];
      expect(meta.id).toBe(id);
      expect(meta.label.length).toBeGreaterThan(0);
      expect(meta.glyph.length).toBeGreaterThan(0);
      expect(meta.accent).toMatch(/^#/);
    }
  });
});

describe('pillarBarPercent', () => {
  it('passes through in-range values', () => {
    expect(pillarBarPercent(0)).toBe(0);
    expect(pillarBarPercent(50)).toBe(50);
    expect(pillarBarPercent(100)).toBe(100);
  });

  it('clamps negative values to 0', () => {
    expect(pillarBarPercent(-10)).toBe(0);
  });

  it('clamps values above 100 to 100', () => {
    expect(pillarBarPercent(150)).toBe(100);
  });

  it('returns 0 for non-finite input', () => {
    expect(pillarBarPercent(Number.NaN)).toBe(0);
    expect(pillarBarPercent(Number.POSITIVE_INFINITY)).toBe(0);
  });
});

describe('formatScore', () => {
  it('formats with 1 decimal by default', () => {
    // JS toFixed uses banker-style rounding on the binary
    // representation; we pick values whose decimals are exactly
    // representable so the assertion is stable across platforms.
    expect(formatScore(62.5)).toBe('62.5');
    expect(formatScore(62)).toBe('62.0');
  });

  it('respects custom digit count', () => {
    expect(formatScore(62.5, 0)).toBe('63');
    expect(formatScore(62.5, 2)).toBe('62.50');
  });

  it('returns em-dash for non-finite values', () => {
    expect(formatScore(Number.NaN)).toBe('—');
  });
});

describe('regulatoryRiskLabel', () => {
  it('returns the right label per flag state', () => {
    expect(regulatoryRiskLabel(true)).toBe('regulatory risk');
    expect(regulatoryRiskLabel(false)).toBe('within compliance');
  });
});
