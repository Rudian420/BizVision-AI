/**
 * Tests for the forecasting queryKeys factory (TASK-033).
 */

import { describe, expect, it } from 'vitest';

import { forecastingKeys } from './queries';

describe('forecastingKeys', () => {
  it('roots every key under "forecasting"', () => {
    expect(forecastingKeys.all[0]).toBe('forecasting');
    expect(forecastingKeys.forecastDetail('abc')[0]).toBe('forecasting');
  });

  it('isolates forecast-detail keys by id', () => {
    expect(JSON.stringify(forecastingKeys.forecastDetail('a'))).not.toBe(
      JSON.stringify(forecastingKeys.forecastDetail('b')),
    );
  });

  it('keeps the root key terse', () => {
    expect(forecastingKeys.all).toEqual(['forecasting']);
  });

  // TASK-035: history list query keys.
  it('namespaces history-page keys under "history" / "page"', () => {
    // 8 elements after root: page, pageSize, seriesName, analysisType,
    // since, until — null sentinels for the optional filter args.
    expect(forecastingKeys.historyPage(1, 20)).toEqual([
      'forecasting',
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

  it('isolates history-page keys by filter shape', () => {
    expect(JSON.stringify(forecastingKeys.historyPage(1, 20))).not.toBe(
      JSON.stringify(forecastingKeys.historyPage(1, 20, 'profit')),
    );
    expect(JSON.stringify(forecastingKeys.historyPage(1, 20, 'profit'))).not.toBe(
      JSON.stringify(forecastingKeys.historyPage(1, 20, 'profit', 'forecast')),
    );
    expect(JSON.stringify(forecastingKeys.historyPage(1, 20))).not.toBe(
      JSON.stringify(forecastingKeys.historyPage(2, 20)),
    );
  });

  // TASK-037: history-page filter by date range.
  it('isolates history-page keys by since/until date bounds (TASK-037)', () => {
    expect(JSON.stringify(forecastingKeys.historyPage(1, 20))).not.toBe(
      JSON.stringify(
        forecastingKeys.historyPage(1, 20, null, null, '2026-05-01'),
      ),
    );
    expect(
      JSON.stringify(
        forecastingKeys.historyPage(1, 20, null, null, '2026-05-01'),
      ),
    ).not.toBe(
      JSON.stringify(
        forecastingKeys.historyPage(
          1,
          20,
          null,
          null,
          '2026-05-01',
          '2026-05-31',
        ),
      ),
    );
  });
});
