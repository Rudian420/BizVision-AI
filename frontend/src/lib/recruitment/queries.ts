/**
 * React Query hooks + key factory for the recruitment module.
 *
 * Wave-1 exposed only the analyze mutation. TASK-032 adds the
 * sessions/list + sessions/detail + per-session fairness reads
 * so the audit feed can deep-link into the persisted session view.
 */

import { useMutation, useQuery } from '@tanstack/react-query';

import {
  fetchSessionDetail,
  fetchSessionFairness,
  fetchSessionsPage,
  runAnalysis,
} from './client';
import type {
  FairnessAuditResponse,
  RecruitmentAnalysisRequest,
  RecruitmentAnalysisResponse,
  RecruitmentSessionDetail,
  RecruitmentSessionsPage,
} from './types';

export const recruitmentKeys = {
  all: ['recruitment'] as const,
  sessionsList: (
    page: number,
    pageSize: number,
    since?: string | null,
    until?: string | null,
  ) =>
    [
      ...recruitmentKeys.all,
      'sessions',
      'list',
      page,
      pageSize,
      since ?? null,
      until ?? null,
    ] as const,
  sessionDetail: (sessionId: string) =>
    [...recruitmentKeys.all, 'sessions', 'detail', sessionId] as const,
  sessionFairness: (sessionId: string) =>
    [...recruitmentKeys.all, 'sessions', 'fairness', sessionId] as const,
};

export function useRunAnalysisMutation() {
  return useMutation<RecruitmentAnalysisResponse, Error, RecruitmentAnalysisRequest>({
    mutationFn: runAnalysis,
  });
}

export function useSessionsListQuery(
  page: number,
  pageSize: number,
  since?: string | null,
  until?: string | null,
) {
  return useQuery<RecruitmentSessionsPage>({
    queryKey: recruitmentKeys.sessionsList(page, pageSize, since, until),
    queryFn: () => fetchSessionsPage(page, pageSize, since, until),
    staleTime: 30_000,
  });
}

export function useSessionDetailQuery(sessionId: string | null) {
  return useQuery<RecruitmentSessionDetail>({
    queryKey: recruitmentKeys.sessionDetail(sessionId ?? ''),
    queryFn: () => {
      if (!sessionId) throw new Error('sessionId required');
      return fetchSessionDetail(sessionId);
    },
    enabled: Boolean(sessionId),
    staleTime: 60_000,
  });
}

export function useSessionFairnessQuery(sessionId: string | null) {
  return useQuery<FairnessAuditResponse>({
    queryKey: recruitmentKeys.sessionFairness(sessionId ?? ''),
    queryFn: () => {
      if (!sessionId) throw new Error('sessionId required');
      return fetchSessionFairness(sessionId);
    },
    enabled: Boolean(sessionId),
    staleTime: 60_000,
  });
}
