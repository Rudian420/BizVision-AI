/**
 * ForecastForm parser tests — verifies the history parser handles
 * the real shapes a user is likely to paste (comma-separated,
 * whitespace-separated, mixed, blank lines).
 */

import { describe, expect, it } from 'vitest';

import { parseHistory } from './ForecastForm';

describe('parseHistory', () => {
  it('parses comma-separated date/value pairs', () => {
    const raw = '2026-01-01, 100\n2026-01-02, 102';
    expect(parseHistory(raw)).toEqual([
      { ds: '2026-01-01', y: 100 },
      { ds: '2026-01-02', y: 102 },
    ]);
  });

  it('accepts whitespace-only separators', () => {
    const raw = '2026-01-01\t100\n2026-01-02 102';
    expect(parseHistory(raw)).toEqual([
      { ds: '2026-01-01', y: 100 },
      { ds: '2026-01-02', y: 102 },
    ]);
  });

  it('skips blank lines', () => {
    const raw = '\n2026-01-01, 100\n\n2026-01-02, 102\n';
    expect(parseHistory(raw)).toHaveLength(2);
  });

  it('skips lines without a valid ISO date', () => {
    const raw = 'not-a-date, 100\n2026-01-02, 102';
    expect(parseHistory(raw)).toEqual([{ ds: '2026-01-02', y: 102 }]);
  });

  it('skips lines with a non-numeric value', () => {
    const raw = '2026-01-01, abc\n2026-01-02, 102';
    expect(parseHistory(raw)).toEqual([{ ds: '2026-01-02', y: 102 }]);
  });

  it('returns an empty array for empty input', () => {
    expect(parseHistory('')).toEqual([]);
    expect(parseHistory('  \n  ')).toEqual([]);
  });

  it('handles decimal values', () => {
    expect(parseHistory('2026-01-01, 100.75')).toEqual([{ ds: '2026-01-01', y: 100.75 }]);
  });

  it('tolerates a single-line input with only whitespace separator', () => {
    expect(parseHistory('2026-01-01   42')).toEqual([{ ds: '2026-01-01', y: 42 }]);
  });
});
