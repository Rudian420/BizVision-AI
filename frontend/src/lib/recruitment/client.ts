/**
 * Recruitment API client — thin wrappers around `/recruitment/*`.
 *
 * Errors propagate as axios errors (the api-client interceptor handles
 * 401 → refresh transparently). Callers (`queries.ts`) turn them into
 * React Query error states.
 */

import { API_ROUTES } from '@bizvision/contracts';

import { apiClient } from '@/lib/api-client';

import type {
  FairnessAuditResponse,
  RecruitmentAnalysisRequest,
  RecruitmentAnalysisResponse,
  RecruitmentSessionDetail,
  RecruitmentSessionsPage,
  UploadCvsResponse,
} from './types';

export async function runAnalysis(
  body: RecruitmentAnalysisRequest,
): Promise<RecruitmentAnalysisResponse> {
  const res = await apiClient.post<RecruitmentAnalysisResponse>(
    API_ROUTES.recruitment.analyze,
    body,
  );
  return res.data;
}

export async function fetchSessionsPage(
  page: number,
  pageSize: number,
  since?: string | null,
  until?: string | null,
): Promise<RecruitmentSessionsPage> {
  const params: Record<string, string | number> = {
    page,
    page_size: pageSize,
  };
  if (since) params.since = since;
  if (until) params.until = until;
  const res = await apiClient.get<RecruitmentSessionsPage>(
    API_ROUTES.recruitment.sessions,
    { params },
  );
  return res.data;
}

export async function fetchSessionDetail(
  sessionId: string,
): Promise<RecruitmentSessionDetail> {
  const res = await apiClient.get<RecruitmentSessionDetail>(
    API_ROUTES.recruitment.session(sessionId),
  );
  return res.data;
}

/** Per-session fairness audit reconstructed from the persisted rows. */
export async function fetchSessionFairness(
  sessionId: string,
): Promise<FairnessAuditResponse> {
  const res = await apiClient.get<FairnessAuditResponse>(
    API_ROUTES.recruitment.fairness(sessionId),
  );
  return res.data;
}

/** Upload one or more PDF/DOCX/TXT files for batch parsing via the
 * real `ResumeParser` on the backend (TASK-045 / ML-003). The
 * returned `cv_text` + `skills` per file can be piped straight into
 * the `/analyze` request body, skipping the user's manual paste. */
export async function uploadCVs(files: File[]): Promise<UploadCvsResponse> {
  const form = new FormData();
  for (const file of files) {
    form.append('files', file, file.name);
  }
  // The api-client interceptor adds Authorization; we let axios pick
  // the multipart boundary automatically (don't set Content-Type).
  const res = await apiClient.post<UploadCvsResponse>(
    API_ROUTES.recruitment.uploadCvs,
    form,
  );
  return res.data;
}
