/**
 * ScoreForm indicator parser tests — verifies the `key: value`
 * parser handles the real shapes a user is likely to paste.
 */

import { describe, expect, it } from 'vitest';

import { parseIndicators } from './ScoreForm';

describe('parseIndicators', () => {
  it('parses colon-separated key/value pairs', () => {
    const raw = 'energy_efficiency: 0.65\nwaste_diversion: 0.55';
    expect(parseIndicators(raw)).toEqual({
      energy_efficiency: 0.65,
      waste_diversion: 0.55,
    });
  });

  it('accepts equals as a separator', () => {
    expect(parseIndicators('dei_index = 0.6')).toEqual({ dei_index: 0.6 });
  });

  it('tolerates whitespace around the separator', () => {
    expect(parseIndicators('board_independence   :   0.7')).toEqual({
      board_independence: 0.7,
    });
  });

  it('skips blank lines', () => {
    const raw = '\nfoo: 1\n\nbar: 2\n';
    expect(parseIndicators(raw)).toEqual({ foo: 1, bar: 2 });
  });

  it('skips lines with no separator', () => {
    expect(parseIndicators('not-a-pair\nfoo: 1')).toEqual({ foo: 1 });
  });

  it('skips lines with non-numeric values', () => {
    expect(parseIndicators('foo: bar\nbaz: 2')).toEqual({ baz: 2 });
  });

  it('returns an empty object for empty input', () => {
    expect(parseIndicators('')).toEqual({});
    expect(parseIndicators('  \n  ')).toEqual({});
  });

  it('keeps the last value when a key repeats', () => {
    expect(parseIndicators('foo: 1\nfoo: 2')).toEqual({ foo: 2 });
  });

  it('handles negative + decimal values', () => {
    expect(parseIndicators('signed: -0.25\nzero: 0')).toEqual({
      signed: -0.25,
      zero: 0,
    });
  });
});
