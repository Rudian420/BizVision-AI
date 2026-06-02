/**
 * Tests for the sustainability queryKeys factory (TASK-033).
 */

import { describe, expect, it } from 'vitest';

import { sustainabilityKeys } from './queries';

describe('sustainabilityKeys', () => {
  it('roots every key under "sustainability"', () => {
    expect(sustainabilityKeys.all[0]).toBe('sustainability');
    expect(sustainabilityKeys.assessmentDetail('abc')[0]).toBe('sustainability');
  });

  it('isolates assessment-detail keys by id', () => {
    expect(JSON.stringify(sustainabilityKeys.assessmentDetail('a'))).not.toBe(
      JSON.stringify(sustainabilityKeys.assessmentDetail('b')),
    );
  });

  it('keeps the root key terse', () => {
    expect(sustainabilityKeys.all).toEqual(['sustainability']);
  });

  // TASK-035: assessments list query keys.
  it('namespaces assessments-page keys under "assessments" / "list"', () => {
    // 8 elements after root: page, pageSize, assessmentType, industry,
    // since, until — null sentinels for the optional filter args.
    expect(sustainabilityKeys.assessmentsPage(1, 20)).toEqual([
      'sustainability',
      'assessments',
      'list',
      1,
      20,
      null,
      null,
      null,
      null,
    ]);
  });

  it('isolates assessments-page keys by filter shape', () => {
    expect(JSON.stringify(sustainabilityKeys.assessmentsPage(1, 20))).not.toBe(
      JSON.stringify(sustainabilityKeys.assessmentsPage(1, 20, 'score')),
    );
    expect(
      JSON.stringify(sustainabilityKeys.assessmentsPage(1, 20, 'score')),
    ).not.toBe(
      JSON.stringify(
        sustainabilityKeys.assessmentsPage(1, 20, 'score', 'manufacturing'),
      ),
    );
    expect(JSON.stringify(sustainabilityKeys.assessmentsPage(1, 20))).not.toBe(
      JSON.stringify(sustainabilityKeys.assessmentsPage(2, 20)),
    );
  });

  it('isolates assessments-page keys from assessment-detail keys', () => {
    expect(JSON.stringify(sustainabilityKeys.assessmentsPage(1, 20))).not.toBe(
      JSON.stringify(sustainabilityKeys.assessmentDetail('abc')),
    );
  });

  // TASK-037: assessments-page filter by date range.
  it('isolates assessments-page keys by since/until date bounds (TASK-037)', () => {
    expect(
      JSON.stringify(sustainabilityKeys.assessmentsPage(1, 20)),
    ).not.toBe(
      JSON.stringify(
        sustainabilityKeys.assessmentsPage(1, 20, null, null, '2026-05-01'),
      ),
    );
    expect(
      JSON.stringify(
        sustainabilityKeys.assessmentsPage(1, 20, null, null, '2026-05-01'),
      ),
    ).not.toBe(
      JSON.stringify(
        sustainabilityKeys.assessmentsPage(
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
