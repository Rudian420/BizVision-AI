/**
 * Audit-log API client — thin wrappers around `/audits/*`.
 *
 * Errors propagate as axios errors (the api-client interceptor handles
 * 401 → refresh transparently). Callers (`queries.ts`) turn them into
 * React Query error states.
 */

import { API_ROUTES } from '@bizvision/contracts';

import { apiClient } from '@/lib/api-client';

import type {
  AuditListFilters,
  AuditLogPage,
  AuditLogRead,
  AuditSummary,
  FairnessAggregate,
} from './types';

export async function fetchAuditPage(filters: AuditListFilters): Promise<AuditLogPage> {
  const params: Record<string, string | number> = {};
  if (filters.module) params.module = filters.module;
  if (filters.risk_tier) params.risk_tier = filters.risk_tier;
  if (filters.since) params.since = filters.since;
  if (filters.until) params.until = filters.until;
  if (filters.page) params.page = filters.page;
  if (filters.page_size) params.page_size = filters.page_size;

  const res = await apiClient.get<AuditLogPage>(API_ROUTES.audits.list, { params });
  return res.data;
}

export async function fetchAuditSummary(
  since?: string | null,
  until?: string | null,
): Promise<AuditSummary> {
  const params: Record<string, string> = {};
  if (since) params.since = since;
  if (until) params.until = until;
  const res = await apiClient.get<AuditSummary>(API_ROUTES.audits.summary, { params });
  return res.data;
}

export async function fetchAuditDetail(auditId: string): Promise<AuditLogRead> {
  const res = await apiClient.get<AuditLogRead>(API_ROUTES.audits.detail(auditId));
  return res.data;
}

export async function fetchFairnessAggregate(
  since?: string | null,
  until?: string | null,
): Promise<FairnessAggregate> {
  const params: Record<string, string> = {};
  if (since) params.since = since;
  if (until) params.until = until;
  const res = await apiClient.get<FairnessAggregate>(API_ROUTES.audits.fairness, { params });
  return res.data;
}
