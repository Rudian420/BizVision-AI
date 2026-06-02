/**
 * Forecasting format + projector tests — pure functions, no React.
 */

import { describe, expect, it } from 'vitest';

import {
  colorForScenario,
  endValueChange,
  formatNumber,
  formatPctChange,
  formatShortDate,
  orderedScenarios,
  projectHistory,
  projectScenario,
  SCENARIO_COLOURS,
  scenarioScale,
} from './format';
import type { ForecastResponse, TimeSeriesPoint } from './types';

const HISTORY: TimeSeriesPoint[] = [
  { ds: '2026-01-01', y: 100 },
  { ds: '2026-01-02', y: 102 },
  { ds: '2026-01-03', y: 104 },
];

const RESPONSE: ForecastResponse = {
  forecast_id: '11111111-2222-3333-4444-555555555555',
  series_name: 'profit',
  generated_at: '2026-05-29T00:00:00Z',
  horizon_days: 30,
  model_version: 'forecast-mock-0.1',
  mape: 6.4,
  primary_drivers: [],
  scenarios: {
    bear: {
      scenario: 'bear',
      points: [
        { ds: '2026-01-04', yhat: 80, yhat_lower: 70, yhat_upper: 90 },
        { ds: '2026-01-05', yhat: 78, yhat_lower: 68, yhat_upper: 88 },
      ],
      end_value: 78,
      cumulative_value: 158,
    },
    base: {
      scenario: 'base',
      points: [
        { ds: '2026-01-04', yhat: 106, yhat_lower: 100, yhat_upper: 112 },
        { ds: '2026-01-05', yhat: 108, yhat_lower: 102, yhat_upper: 114 },
      ],
      end_value: 108,
      cumulative_value: 214,
    },
    bull: {
      scenario: 'bull',
      points: [
        { ds: '2026-01-04', yhat: 124, yhat_lower: 118, yhat_upper: 130 },
        { ds: '2026-01-05', yhat: 128, yhat_lower: 122, yhat_upper: 134 },
      ],
      end_value: 128,
      cumulative_value: 252,
    },
  },
};

// ── formatShortDate ────────────────────────────────────────────────

describe('formatShortDate', () => {
  it('drops the year and renders M/D', () => {
    expect(formatShortDate('2026-05-29')).toBe('5/29');
    expect(formatShortDate('2026-01-01')).toBe('1/1');
  });

  it('passes through invalid input unchanged', () => {
    expect(formatShortDate('garbage')).toBe('garbage');
  });
});

// ── formatNumber / formatPctChange ─────────────────────────────────

describe('formatNumber', () => {
  it('returns em-dash for non-finite input', () => {
    expect(formatNumber(Number.NaN)).toBe('—');
  });

  it('respects custom digit count', () => {
    expect(formatNumber(123.456, 2)).toMatch(/123\.46/);
  });
});

describe('formatPctChange', () => {
  it('prefixes positive with +', () => {
    expect(formatPctChange(0.12)).toBe('+12.0%');
  });

  it('uses U+2212 for negative', () => {
    expect(formatPctChange(-0.05)).toBe('−5.0%');
  });

  it('returns em-dash for non-finite', () => {
    expect(formatPctChange(Number.NaN)).toBe('—');
  });
});

// ── colorForScenario ───────────────────────────────────────────────

describe('colorForScenario', () => {
  it('returns the canonical palette for known scenarios', () => {
    expect(colorForScenario('base')).toBe(SCENARIO_COLOURS.base);
    expect(colorForScenario('BULL')).toBe(SCENARIO_COLOURS.bull);
    expect(colorForScenario('bear')).toBe(SCENARIO_COLOURS.bear);
  });

  it('falls back to a stable colour for unknown names', () => {
    const out = colorForScenario('quantum');
    expect(out).toMatch(/^#/);
  });
});

// ── orderedScenarios ───────────────────────────────────────────────

describe('orderedScenarios', () => {
  it('places base → bull → bear regardless of object key order', () => {
    const names = orderedScenarios(RESPONSE).map((s) => s.name);
    expect(names).toEqual(['base', 'bull', 'bear']);
  });
});

// ── scenarioScale ──────────────────────────────────────────────────

describe('scenarioScale', () => {
  it('covers both history and scenario PI bounds in the y range', () => {
    const scale = scenarioScale(HISTORY, [RESPONSE.scenarios.bull, RESPONSE.scenarios.bear]);
    // History min 100, bear lower 68 → yMin must be ≤ 68
    expect(scale.yMin).toBeLessThanOrEqual(68);
    // Bull upper 134 → yMax must be ≥ 134
    expect(scale.yMax).toBeGreaterThanOrEqual(134);
  });

  it('returns a degenerate scale when everything is empty', () => {
    const scale = scenarioScale([], []);
    expect(scale.yMin).toBeLessThan(scale.yMax);
  });
});

// ── projectScenario / projectHistory ───────────────────────────────

describe('projectScenario', () => {
  it('returns aligned centre/upper/lower arrays', () => {
    const scale = scenarioScale(HISTORY, [RESPONSE.scenarios.base]);
    const out = projectScenario(RESPONSE.scenarios.base.points, scale, 100, 100);
    expect(out.centre).toHaveLength(2);
    expect(out.upper).toHaveLength(2);
    expect(out.lower).toHaveLength(2);
  });

  it('places yhat between yhat_lower and yhat_upper after SVG flip', () => {
    // SVG y grows downward, so the y for `yhat_upper` (data top)
    // should be smaller than for `yhat_lower` (data bottom).
    const scale = scenarioScale(HISTORY, [RESPONSE.scenarios.base]);
    const out = projectScenario(RESPONSE.scenarios.base.points, scale, 100, 100);
    expect(out.upper[0].y).toBeLessThan(out.centre[0].y);
    expect(out.centre[0].y).toBeLessThan(out.lower[0].y);
  });
});

describe('projectHistory', () => {
  it('returns one point per history sample', () => {
    const scale = scenarioScale(HISTORY, []);
    expect(projectHistory(HISTORY, scale, 100, 100)).toHaveLength(HISTORY.length);
  });

  it('returns an empty array for empty history', () => {
    const scale = scenarioScale([], []);
    expect(projectHistory([], scale, 100, 100)).toEqual([]);
  });
});

// ── endValueChange ─────────────────────────────────────────────────

describe('endValueChange', () => {
  it('returns a positive fraction when scenario exceeds baseline', () => {
    expect(endValueChange(100, 120)).toBeCloseTo(0.2);
  });

  it('returns a negative fraction when scenario undercuts baseline', () => {
    expect(endValueChange(100, 80)).toBeCloseTo(-0.2);
  });

  it('returns 0 for zero or NaN baseline', () => {
    expect(endValueChange(0, 100)).toBe(0);
    expect(endValueChange(Number.NaN, 100)).toBe(0);
  });
});
