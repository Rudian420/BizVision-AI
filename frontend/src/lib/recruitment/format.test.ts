/**
 * Recruitment format helper tests — pure functions, no React.
 *
 * Covers percent formatting (NaN tolerance, custom precision), SHAP
 * sign rendering, risk-tone mapping (exhaustive over the four
 * RiskLevel values), and elapsed-time bucketing.
 */

import { describe, expect, it } from 'vitest';

import { formatElapsed, formatPercent, formatShap, RISK_TONES, toneForRisk } from './format';

describe('formatPercent', () => {
  it('formats a 0..1 score with default 1-decimal precision', () => {
    expect(formatPercent(0.873)).toBe('87.3%');
    expect(formatPercent(0)).toBe('0.0%');
    expect(formatPercent(1)).toBe('100.0%');
  });

  it('respects custom digit counts', () => {
    expect(formatPercent(0.873, 0)).toBe('87%');
    expect(formatPercent(0.873, 3)).toBe('87.300%');
  });

  it('returns em-dash for non-finite scores', () => {
    expect(formatPercent(Number.NaN)).toBe('—');
    expect(formatPercent(Number.POSITIVE_INFINITY)).toBe('—');
  });
});

describe('formatShap', () => {
  it('prefixes positive values with +', () => {
    expect(formatShap(0.12)).toBe('+0.12');
  });

  it('prefixes negative values with the minus sign', () => {
    // The function uses U+2212 MINUS SIGN, not ASCII hyphen-minus.
    expect(formatShap(-0.45)).toBe('−0.45');
  });

  it('returns an unsigned 0.00 for exactly zero', () => {
    expect(formatShap(0)).toBe('0.00');
  });

  it('returns em-dash for non-finite values', () => {
    expect(formatShap(Number.NaN)).toBe('—');
  });
});

describe('toneForRisk + RISK_TONES', () => {
  it('exposes a tone for every risk level', () => {
    expect(Object.keys(RISK_TONES)).toEqual(['low', 'medium', 'high', 'critical']);
  });

  it('returns the matching tone object', () => {
    expect(toneForRisk('low')).toBe(RISK_TONES.low);
    expect(toneForRisk('critical')).toBe(RISK_TONES.critical);
  });

  it('uses emerald for low and coral for high/critical', () => {
    expect(RISK_TONES.low.text).toBe('text-emerald');
    expect(RISK_TONES.high.text).toBe('text-coral');
    expect(RISK_TONES.critical.text).toBe('text-coral');
  });
});

describe('formatElapsed', () => {
  it('uses milliseconds under 1 s', () => {
    expect(formatElapsed(42)).toBe('42 ms');
    expect(formatElapsed(999)).toBe('999 ms');
  });

  it('switches to seconds at 1 s and above', () => {
    expect(formatElapsed(1000)).toBe('1.00 s');
    expect(formatElapsed(1234.5)).toBe('1.23 s');
  });

  it('returns em-dash for invalid input', () => {
    expect(formatElapsed(Number.NaN)).toBe('—');
    expect(formatElapsed(-5)).toBe('—');
  });
});
