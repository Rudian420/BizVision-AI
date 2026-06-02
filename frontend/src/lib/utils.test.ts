import { describe, expect, it } from 'vitest';

import { cn, formatScore } from './utils';

describe('cn', () => {
  it('merges and dedupes tailwind classes', () => {
    expect(cn('px-2', 'px-4')).toBe('px-4');
    expect(cn('text-sm', false && 'hidden', 'font-bold')).toBe('text-sm font-bold');
  });
});

describe('formatScore', () => {
  it('formats a 0-1 score as a percentage', () => {
    expect(formatScore(0.873)).toBe('87%');
    expect(formatScore(0.873, 1)).toBe('87.3%');
  });
});
