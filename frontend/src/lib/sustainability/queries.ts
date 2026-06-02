/**
 * React Query hooks + key factory for the sustainability module.
 *
 * Wave 1 only shipped the score mutation. TASK-033 adds the
 * assessment-detail read so the audit feed can deep-link into the
 * persisted ESG assessment view.
 */

import { useMutation, useQuery } from '@tanstack/react-query';

import {
  fetchAssessmentDetail,
  fetchAssessmentsPage,
  runScore,
} from './client';
import type {
  ESGScoreRequest,
  ESGScoreResponse,
  SustainabilityAssessmentDetail,
  SustainabilityAssessmentsPage,
} from './types';

export const sustainabilityKeys = {
  all: ['sustainability'] as const,
  assessmentDetail: (assessmentId: string) =>
    [...sustainabilityKeys.all, 'assessments', 'detail', assessmentId] as const,
  assessmentsPage: (
    page: number,
    pageSize: number,
    assessmentType?: string | null,
    industry?: string | null,
    since?: string | null,
    until?: string | null,
  ) =>
    [
      ...sustainabilityKeys.all,
      'assessments',
      'list',
      page,
      pageSize,
      assessmentType ?? null,
      industry ?? null,
      since ?? null,
      until ?? null,
    ] as const,
};

export function useRunScoreMutation() {
  return useMutation<ESGScoreResponse, Error, ESGScoreRequest>({
    mutationFn: runScore,
  });
}

export function useAssessmentDetailQuery(assessmentId: string | null) {
  return useQuery<SustainabilityAssessmentDetail>({
    queryKey: sustainabilityKeys.assessmentDetail(assessmentId ?? ''),
    queryFn: () => {
      if (!assessmentId) throw new Error('assessmentId required');
      return fetchAssessmentDetail(assessmentId);
    },
    enabled: Boolean(assessmentId),
    staleTime: 60_000,
  });
}

export function useAssessmentsListQuery(
  page: number,
  pageSize: number,
  assessmentType?: string | null,
  industry?: string | null,
  since?: string | null,
  until?: string | null,
) {
  return useQuery<SustainabilityAssessmentsPage>({
    queryKey: sustainabilityKeys.assessmentsPage(
      page,
      pageSize,
      assessmentType,
      industry,
      since,
      until,
    ),
    queryFn: () =>
      fetchAssessmentsPage(
        page,
        pageSize,
        assessmentType,
        industry,
        since,
        until,
      ),
    staleTime: 30_000,
  });
}
