/**
 * Chatbot format helper tests — pure functions, no React.
 */

import { describe, expect, it } from 'vitest';

import {
  CONTEXT_MODULES,
  formatClockTime,
  formatRelativeTime,
  freshnessTier,
  moduleMetaById,
  previewSnippet,
} from './format';

const NOW = new Date('2026-05-29T12:00:00Z');

describe('formatRelativeTime', () => {
  it('returns "just now" for sub-minute deltas', () => {
    // 10 seconds — Math.round(10/60) = 0, so we're under the
    // 1-minute threshold even after rounding.
    expect(formatRelativeTime('2026-05-29T11:59:50Z', NOW)).toBe('just now');
  });

  it('uses Xm ago for sub-hour deltas', () => {
    expect(formatRelativeTime('2026-05-29T11:55:00Z', NOW)).toBe('5m ago');
  });

  it('uses Xh ago for sub-day deltas', () => {
    expect(formatRelativeTime('2026-05-29T09:00:00Z', NOW)).toBe('3h ago');
  });

  it('uses "yesterday" for ~24h deltas', () => {
    expect(formatRelativeTime('2026-05-28T12:00:00Z', NOW)).toBe('yesterday');
  });

  it('uses Xd ago between 2..6 days', () => {
    expect(formatRelativeTime('2026-05-26T12:00:00Z', NOW)).toBe('3d ago');
  });

  it('falls back to month + day for older entries', () => {
    const formatted = formatRelativeTime('2025-12-01T12:00:00Z', NOW);
    // Locale-dependent — check the shape, not exact string.
    expect(formatted).not.toMatch(/ago/);
    expect(formatted.length).toBeGreaterThan(0);
  });

  it('returns em-dash for an invalid date string', () => {
    expect(formatRelativeTime('not-a-date', NOW)).toBe('—');
  });
});

describe('formatClockTime', () => {
  it('returns HH:MM for a valid date', () => {
    const out = formatClockTime('2026-05-29T14:35:00Z');
    expect(out).toMatch(/\d{1,2}:\d{2}/);
  });

  it('returns em-dash for an invalid date', () => {
    expect(formatClockTime('garbage')).toBe('—');
  });
});

describe('CONTEXT_MODULES + moduleMetaById', () => {
  it('exposes every BizVision module except the chatbot itself', () => {
    const ids = CONTEXT_MODULES.map((m) => m.id);
    expect(ids).toContain('recruitment');
    expect(ids).toContain('pricing');
    expect(ids).toContain('forecasting');
    expect(ids).toContain('sustainability');
    expect(ids).not.toContain('chatbot');
  });

  it('moduleMetaById returns the right meta for a known id', () => {
    const meta = moduleMetaById('pricing');
    expect(meta).not.toBeNull();
    expect(meta?.id).toBe('pricing');
    expect(meta?.accent).toMatch(/^#/);
  });

  it('moduleMetaById returns null for an unknown id', () => {
    expect(moduleMetaById('not-a-module')).toBeNull();
  });
});

describe('freshnessTier', () => {
  it('returns fresh for < 1 hour', () => {
    expect(freshnessTier('2026-05-29T11:30:00Z', NOW)).toBe('fresh');
  });

  it('returns recent for 1..24 hours', () => {
    expect(freshnessTier('2026-05-29T05:00:00Z', NOW)).toBe('recent');
  });

  it('returns stale for ≥ 24 hours', () => {
    expect(freshnessTier('2026-05-27T12:00:00Z', NOW)).toBe('stale');
  });

  it('returns stale for invalid input', () => {
    expect(freshnessTier('garbage', NOW)).toBe('stale');
  });
});

describe('previewSnippet', () => {
  it('collapses whitespace and trims', () => {
    expect(previewSnippet('   foo   bar  ')).toBe('foo bar');
  });

  it('truncates with an ellipsis when over the cap', () => {
    const out = previewSnippet('a'.repeat(120), 10);
    expect(out.length).toBe(10);
    expect(out.endsWith('…')).toBe(true);
  });

  it('returns the original string when under the cap', () => {
    expect(previewSnippet('hello', 100)).toBe('hello');
  });
});
