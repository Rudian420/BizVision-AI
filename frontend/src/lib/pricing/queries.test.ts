/**
 * Tests for the pricing queryKeys factory (TASK-033).
 */

import { describe, expect, it } from 'vitest';

import { pricingKeys } from './queries';

describe('pricingKeys', () => {
  it('roots every key under "pricing"', () => {
    expect(pricingKeys.all[0]).toBe('pricing');
    expect(pricingKeys.analysisDetail('abc')[0]).toBe('pricing');
  });

  it('isolates analysis-detail keys by id', () => {
    expect(JSON.stringify(pricingKeys.analysisDetail('a'))).not.toBe(
      JSON.stringify(pricingKeys.analysisDetail('b')),
    );
  });

  it('keeps the root key terse so invalidateQueries({queryKey: all}) wipes only pricing', () => {
    expect(pricingKeys.all).toEqual(['pricing']);
  });

  // TASK-035: history list query keys.
  it('namespaces history-page keys under "history" / "page"', () => {
    // 8 elements after root: page, pageSize, productId, analysisType,
    // since, until — null sentinels for the optional filter args.
    expect(pricingKeys.historyPage(1, 20)).toEqual([
      'pricing',
      'history',
      'page',
      1,
      20,
      null,
      null,
      null,
      null,
    ]);
  });

  it('isolates history-page keys by (page, pageSize, productId)', () => {
    expect(JSON.stringify(pricingKeys.historyPage(1, 20))).not.toBe(
      JSON.stringify(pricingKeys.historyPage(2, 20)),
    );
    expect(JSON.stringify(pricingKeys.historyPage(1, 20))).not.toBe(
      JSON.stringify(pricingKeys.historyPage(1, 50)),
    );
    expect(JSON.stringify(pricingKeys.historyPage(1, 20))).not.toBe(
      JSON.stringify(pricingKeys.historyPage(1, 20, 'sku-001')),
    );
  });

  // TASK-036: history-page filter by analysis_type chip.
  it('isolates history-page keys by analysis_type filter (TASK-036)', () => {
    expect(JSON.stringify(pricingKeys.historyPage(1, 20))).not.toBe(
      JSON.stringify(pricingKeys.historyPage(1, 20, null, 'optimize')),
    );
    expect(
      JSON.stringify(pricingKeys.historyPage(1, 20, null, 'optimize')),
    ).not.toBe(
      JSON.stringify(pricingKeys.historyPage(1, 20, null, 'elasticity')),
    );
    // product_id + analysis_type together compose distinct cache keys.
    expect(
      JSON.stringify(pricingKeys.historyPage(1, 20, 'sku-001', 'optimize')),
    ).not.toBe(JSON.stringify(pricingKeys.historyPage(1, 20, 'sku-001')));
  });

  // TASK-037: history-page filter by date range.
  it('isolates history-page keys by since/until date bounds (TASK-037)', () => {
    expect(JSON.stringify(pricingKeys.historyPage(1, 20))).not.toBe(
      JSON.stringify(
        pricingKeys.historyPage(1, 20, null, null, '2026-05-01'),
      ),
    );
    expect(
      JSON.stringify(pricingKeys.historyPage(1, 20, null, null, '2026-05-01')),
    ).not.toBe(
      JSON.stringify(pricingKeys.historyPage(1, 20, null, null, '2026-04-01')),
    );
    expect(
      JSON.stringify(
        pricingKeys.historyPage(1, 20, null, null, '2026-05-01'),
      ),
    ).not.toBe(
      JSON.stringify(
        pricingKeys.historyPage(1, 20, null, null, '2026-05-01', '2026-05-31'),
      ),
    );
  });
});
