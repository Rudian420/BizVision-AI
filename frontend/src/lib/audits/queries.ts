/**
 * React Query hooks + key factory for the audit-log domain.
 *
 * Mirrors the chatbot module's `chatbotKeys` posture so cross-domain
 * cache invalidation stays predictable: every audit-related query
 * lives under one root, and per-shape sub-roots prevent accidentally
 * over-invalidating page-1 of a filtered list when a different
 * filter mutates.
 */

import { useQuery } from '@tanstack/react-query';

import {
  fetchAuditDetail,
  fetchAuditPage,
  fetchAuditSummary,
  fetchFairnessAggregate,
} from './client';
import type {
  AuditListFilters,
  AuditLogPage,
  AuditLogRead,
  AuditSummary,
  FairnessAggregate,
} from './types';

export const auditKeys = {
  all: ['audits'] as const,
  pages: () => [...auditKeys.all, 'page'] as const,
  page: (filters: AuditListFilters) => [...auditKeys.pages(), filters] as const,
  summary: (since?: string | null, until?: string | null) =>
    [...auditKeys.all, 'summary', since ?? null, until ?? null] as const,
  fairness: (since?: string | null, until?: string | null) =>
    [...auditKeys.all, 'fairness', since ?? null, until ?? null] as const,
  detail: (auditId: string) => [...auditKeys.all, 'detail', auditId] as const,
};

export function useAuditPageQuery(filters: AuditListFilters) {
  return useQuery<AuditLogPage>({
    queryKey: auditKeys.page(filters),
    queryFn: () => fetchAuditPage(filters),
    staleTime: 30_000,
  });
}

export function useAuditSummaryQuery(
  since?: string | null,
  until?: string | null,
) {
  return useQuery<AuditSummary>({
    queryKey: auditKeys.summary(since, until),
    queryFn: () => fetchAuditSummary(since, until),
    staleTime: 30_000,
  });
}

export function useFairnessAggregateQuery(
  since?: string | null,
  until?: string | null,
) {
  return useQuery<FairnessAggregate>({
    queryKey: auditKeys.fairness(since, until),
    queryFn: () => fetchFairnessAggregate(since, until),
    staleTime: 30_000,
  });
}

export function useAuditDetailQuery(auditId: string | null) {
  return useQuery<AuditLogRead>({
    queryKey: auditKeys.detail(auditId ?? ''),
    queryFn: () => {
      if (!auditId) {
        // Should never reach here — enabled gates the call.
        throw new Error('auditId required');
      }
      return fetchAuditDetail(auditId);
    },
    enabled: Boolean(auditId),
    staleTime: 60_000,
  });
}
