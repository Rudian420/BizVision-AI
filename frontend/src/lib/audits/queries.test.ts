/**
 * Tests for the audit-log queryKeys factory.
 *
 * Mirrors the chatbot module's queries test posture — keys are
 * structural tuples used by the React Query cache; if two different
 * filter shapes produce the same key, cache poisoning happens. This
 * test asserts the key discipline.
 */

import { describe, expect, it } from 'vitest';

import { auditKeys } from './queries';
import type { AuditListFilters } from './types';

describe('auditKeys', () => {
  it('roots every key under "audits"', () => {
    expect(auditKeys.all[0]).toBe('audits');
    expect(auditKeys.pages()[0]).toBe('audits');
    expect(auditKeys.summary()[0]).toBe('audits');
    expect(auditKeys.detail('abc')[0]).toBe('audits');
  });

  it('namespaces page keys under "page"', () => {
    const filters: AuditListFilters = { module: 'pricing', page: 1, page_size: 20 };
    expect(auditKeys.page(filters)).toEqual(['audits', 'page', filters]);
  });

  it('treats different filter shapes as distinct cache keys', () => {
    const a: AuditListFilters = { module: 'pricing', page: 1, page_size: 20 };
    const b: AuditListFilters = { module: 'forecasting', page: 1, page_size: 20 };
    const aKey = JSON.stringify(auditKeys.page(a));
    const bKey = JSON.stringify(auditKeys.page(b));
    expect(aKey).not.toBe(bKey);
  });

  it('treats different page numbers as distinct cache keys', () => {
    const a: AuditListFilters = { module: 'pricing', page: 1, page_size: 20 };
    const b: AuditListFilters = { module: 'pricing', page: 2, page_size: 20 };
    expect(JSON.stringify(auditKeys.page(a))).not.toBe(JSON.stringify(auditKeys.page(b)));
  });

  it('uses sentinels for the all-time summary key', () => {
    // After TASK-038 the summary key carries both since + until null
    // sentinels so distinct date bounds isolate cleanly.
    expect(auditKeys.summary()).toEqual(['audits', 'summary', null, null]);
    expect(auditKeys.summary(null, null)).toEqual([
      'audits',
      'summary',
      null,
      null,
    ]);
  });

  it('namespaces fairness keys distinctly from summary keys', () => {
    expect(auditKeys.fairness()).toEqual(['audits', 'fairness', null, null]);
    expect(JSON.stringify(auditKeys.summary())).not.toBe(
      JSON.stringify(auditKeys.fairness()),
    );
  });

  it('isolates fairness keys by their `since` window', () => {
    const a = auditKeys.fairness('2026-01-01T00:00:00Z');
    const b = auditKeys.fairness('2026-04-01T00:00:00Z');
    expect(JSON.stringify(a)).not.toBe(JSON.stringify(b));
  });

  // TASK-038: until isolation across summary + fairness keys.
  it('isolates summary keys by `until` independently of `since`', () => {
    const a = auditKeys.summary('2026-05-01', '2026-05-15');
    const b = auditKeys.summary('2026-05-01', '2026-05-31');
    expect(JSON.stringify(a)).not.toBe(JSON.stringify(b));
  });

  it('isolates fairness keys by `until`', () => {
    const a = auditKeys.fairness('2026-05-01');
    const b = auditKeys.fairness('2026-05-01', '2026-05-31');
    expect(JSON.stringify(a)).not.toBe(JSON.stringify(b));
  });

  it('isolates summary keys by their `since` window', () => {
    const a = auditKeys.summary('2026-01-01T00:00:00Z');
    const b = auditKeys.summary('2026-04-01T00:00:00Z');
    expect(JSON.stringify(a)).not.toBe(JSON.stringify(b));
  });

  it('isolates detail keys by audit id', () => {
    expect(auditKeys.detail('abc')).toEqual(['audits', 'detail', 'abc']);
    expect(JSON.stringify(auditKeys.detail('abc'))).not.toBe(
      JSON.stringify(auditKeys.detail('def')),
    );
  });

  it('keeps the root key terse so invalidateQueries({ queryKey: all }) wipes only audits', () => {
    expect(auditKeys.all).toEqual(['audits']);
  });
});
