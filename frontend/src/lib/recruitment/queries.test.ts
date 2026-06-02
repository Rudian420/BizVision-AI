/**
 * Tests for the recruitment-domain queryKeys factory introduced in
 * TASK-032. Mirrors `lib/audits/queries.test.ts` posture — keys are
 * structural tuples used by the React Query cache; two distinct
 * shapes mapping to the same key would cause cache poisoning.
 */

import { describe, expect, it } from 'vitest';

import { recruitmentKeys } from './queries';

describe('recruitmentKeys', () => {
  it('roots every key under "recruitment"', () => {
    expect(recruitmentKeys.all[0]).toBe('recruitment');
    expect(recruitmentKeys.sessionsList(1, 20)[0]).toBe('recruitment');
    expect(recruitmentKeys.sessionDetail('abc')[0]).toBe('recruitment');
    expect(recruitmentKeys.sessionFairness('abc')[0]).toBe('recruitment');
  });

  it('namespaces sessions list keys distinctly from detail and fairness', () => {
    const list = JSON.stringify(recruitmentKeys.sessionsList(1, 20));
    const detail = JSON.stringify(recruitmentKeys.sessionDetail('abc'));
    const fairness = JSON.stringify(recruitmentKeys.sessionFairness('abc'));
    expect(list).not.toBe(detail);
    expect(list).not.toBe(fairness);
    expect(detail).not.toBe(fairness);
  });

  it('isolates list keys by page and page_size', () => {
    expect(JSON.stringify(recruitmentKeys.sessionsList(1, 20))).not.toBe(
      JSON.stringify(recruitmentKeys.sessionsList(2, 20)),
    );
    expect(JSON.stringify(recruitmentKeys.sessionsList(1, 20))).not.toBe(
      JSON.stringify(recruitmentKeys.sessionsList(1, 50)),
    );
  });

  it('isolates detail + fairness keys by session id', () => {
    expect(JSON.stringify(recruitmentKeys.sessionDetail('abc'))).not.toBe(
      JSON.stringify(recruitmentKeys.sessionDetail('def')),
    );
    expect(JSON.stringify(recruitmentKeys.sessionFairness('abc'))).not.toBe(
      JSON.stringify(recruitmentKeys.sessionFairness('def')),
    );
  });

  it('keeps the root key terse so invalidateQueries({queryKey: all}) wipes only recruitment', () => {
    expect(recruitmentKeys.all).toEqual(['recruitment']);
  });

  // TASK-037: sessions list filter by date range.
  it('isolates sessions-list keys by since/until date bounds (TASK-037)', () => {
    expect(JSON.stringify(recruitmentKeys.sessionsList(1, 20))).not.toBe(
      JSON.stringify(recruitmentKeys.sessionsList(1, 20, '2026-05-01')),
    );
    expect(
      JSON.stringify(recruitmentKeys.sessionsList(1, 20, '2026-05-01')),
    ).not.toBe(
      JSON.stringify(
        recruitmentKeys.sessionsList(1, 20, '2026-05-01', '2026-05-31'),
      ),
    );
  });
});
