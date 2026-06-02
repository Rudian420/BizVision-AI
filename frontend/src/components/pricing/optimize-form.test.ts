/**
 * OptimizeForm parser tests — verifies the number-list + optional
 * positive parsers independently of any React rendering. The form
 * component itself is exercised by the wave-2 e2e suite.
 */

import { describe, expect, it } from 'vitest';

import { parseNumberList, parseOptionalPositive } from './OptimizeForm';

describe('parseNumberList', () => {
  it('parses a comma-separated list of numbers', () => {
    expect(parseNumberList('120, 118, 122')).toEqual([120, 118, 122]);
  });

  it('drops non-numeric entries silently', () => {
    expect(parseNumberList('1, two, 3')).toEqual([1, 3]);
  });

  it('tolerates extra whitespace', () => {
    expect(parseNumberList('  10  ,   20.5  ,  30  ')).toEqual([10, 20.5, 30]);
  });

  it('returns an empty list for empty input', () => {
    expect(parseNumberList('')).toEqual([]);
  });

  it('handles decimal numbers', () => {
    expect(parseNumberList('21.00, 20.50, 22.00')).toEqual([21, 20.5, 22]);
  });
});

describe('parseOptionalPositive', () => {
  it('returns undefined for empty input', () => {
    expect(parseOptionalPositive('')).toBeUndefined();
    expect(parseOptionalPositive('   ')).toBeUndefined();
  });

  it('returns undefined for zero, negative, or NaN', () => {
    expect(parseOptionalPositive('0')).toBeUndefined();
    expect(parseOptionalPositive('-5')).toBeUndefined();
    expect(parseOptionalPositive('not-a-number')).toBeUndefined();
  });

  it('returns the parsed number for a positive value', () => {
    expect(parseOptionalPositive('19.99')).toBe(19.99);
    expect(parseOptionalPositive('  42 ')).toBe(42);
  });
});
