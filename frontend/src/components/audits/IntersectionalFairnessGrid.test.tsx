/**
 * Tests for the IntersectionalFairnessGrid matrix builder + helpers
 * (TASK-043, FE-017). The component itself is mostly markup that
 * leans on existing `passRateTier` / `toneForRisk` / `formatPassRate`
 * primitives (already tested elsewhere) — the *interesting* logic is
 * the pivot from a flat `FairnessCell[]` into a `(rows × cols × map)`
 * matrix and the deterministic label formatting. That's what we test
 * here.
 */

import { describe, expect, it } from 'vitest';

import type { FairnessCell } from '@/lib/audits/types';

import {
  buildMatrix,
  cellKey,
  describeCell,
  formatMetricLabel,
} from './IntersectionalFairnessGrid';

const baseCell = (over: Partial<FairnessCell> = {}): FairnessCell => ({
  attribute: 'gender',
  metric_name: 'demographic_parity',
  decision_count: 4,
  pass_count: 3,
  pass_rate: 0.75,
  avg_value: 0.04,
  threshold: 0.1,
  ...over,
});

describe('buildMatrix', () => {
  it('returns an empty matrix on empty input', () => {
    const m = buildMatrix([]);
    expect(m.attributes).toEqual([]);
    expect(m.metrics).toEqual([]);
    expect(m.cells).toEqual([]);
    expect(m.lookup.size).toBe(0);
  });

  it('sorts attributes and metrics ascending so column order is stable across renders', () => {
    const cells: FairnessCell[] = [
      baseCell({ attribute: 'race', metric_name: 'equal_opportunity' }),
      baseCell({ attribute: 'gender', metric_name: 'demographic_parity' }),
      baseCell({ attribute: 'age_group', metric_name: 'demographic_parity' }),
      baseCell({ attribute: 'gender', metric_name: 'equal_opportunity' }),
    ];
    const m = buildMatrix(cells);
    expect(m.attributes).toEqual(['age_group', 'gender', 'race']);
    expect(m.metrics).toEqual(['demographic_parity', 'equal_opportunity']);
  });

  it('builds a lookup keyed by (attribute, metric) for O(1) cell access', () => {
    const cells: FairnessCell[] = [
      baseCell({ attribute: 'gender', metric_name: 'demographic_parity', pass_rate: 0.9 }),
      baseCell({ attribute: 'age_group', metric_name: 'demographic_parity', pass_rate: 0.6 }),
    ];
    const m = buildMatrix(cells);
    expect(m.lookup.get(cellKey('gender', 'demographic_parity'))?.pass_rate).toBe(0.9);
    expect(m.lookup.get(cellKey('age_group', 'demographic_parity'))?.pass_rate).toBe(0.6);
    expect(m.lookup.get(cellKey('gender', 'equal_opportunity'))).toBeUndefined();
  });

  it('preserves all input cells (no deduplication beyond key collision)', () => {
    const cells: FairnessCell[] = [
      baseCell({ attribute: 'gender', metric_name: 'demographic_parity' }),
      baseCell({ attribute: 'gender', metric_name: 'equal_opportunity' }),
    ];
    const m = buildMatrix(cells);
    expect(m.cells).toHaveLength(2);
  });
});

describe('formatMetricLabel', () => {
  it('title-cases snake_case metric names', () => {
    expect(formatMetricLabel('demographic_parity')).toBe('Demographic Parity');
    expect(formatMetricLabel('equal_opportunity')).toBe('Equal Opportunity');
    expect(formatMetricLabel('disparate_impact_ratio')).toBe('Disparate Impact Ratio');
  });

  it('returns the raw name when there is no underscore to split on', () => {
    expect(formatMetricLabel('parity')).toBe('parity');
    expect(formatMetricLabel('')).toBe('');
  });
});

describe('cellKey', () => {
  it('builds a stable composite key', () => {
    expect(cellKey('gender', 'demographic_parity')).toBe('gender::demographic_parity');
  });

  it('handles attribute names containing the separator delimiter safely (no collision with other attribute pairs in practice)', () => {
    // We don't expect `::` to appear in real attribute/metric names but
    // documenting the behaviour so a future regression is intentional.
    expect(cellKey('a::b', 'c')).toBe('a::b::c');
  });
});

describe('describeCell', () => {
  it('formats a complete cell into a tooltip-ready multi-line string', () => {
    const tip = describeCell(
      baseCell({ pass_count: 7, decision_count: 10, pass_rate: 0.7, avg_value: 0.042, threshold: 0.1 }),
    );
    expect(tip).toContain('gender × demographic_parity');
    expect(tip).toContain('7 of 10 decisions passed (70%)');
    expect(tip).toContain('avg metric value 0.0420');
    expect(tip).toContain('pass threshold 0.1000');
  });

  it('omits avg_value and threshold lines when they are null', () => {
    const tip = describeCell(baseCell({ avg_value: null, threshold: null }));
    expect(tip).not.toContain('avg metric value');
    expect(tip).not.toContain('pass threshold');
  });
});
