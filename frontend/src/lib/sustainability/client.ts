/**
 * Sustainability API client — wraps `/sustainability/score`.
 *
 * Wave 1 exposes only `runScore`. /simulate, /recommendations, and
 * /carbon-estimate arrive in wave 2 behind workspace tabs.
 */

import { API_ROUTES } from '@bizvision/contracts';

import { apiClient } from '@/lib/api-client';

import type {
  ESGScoreRequest,
  ESGScoreResponse,
  SustainabilityAssessmentDetail,
  SustainabilityAssessmentsPage,
} from './types';

export async function runScore(body: ESGScoreRequest): Promise<ESGScoreResponse> {
  const res = await apiClient.post<ESGScoreResponse>(
    API_ROUTES.sustainability.score,
    body,
  );
  return res.data;
}

export async function fetchAssessmentDetail(
  assessmentId: string,
): Promise<SustainabilityAssessmentDetail> {
  const res = await apiClient.get<SustainabilityAssessmentDetail>(
    API_ROUTES.sustainability.assessment(assessmentId),
  );
  return res.data;
}

export async function fetchAssessmentsPage(
  page: number,
  pageSize: number,
  assessmentType?: string | null,
  industry?: string | null,
  since?: string | null,
  until?: string | null,
): Promise<SustainabilityAssessmentsPage> {
  const params: Record<string, string | number> = {
    page,
    page_size: pageSize,
  };
  if (assessmentType) params.assessment_type = assessmentType;
  if (industry) params.industry = industry;
  if (since) params.since = since;
  if (until) params.until = until;
  const res = await apiClient.get<SustainabilityAssessmentsPage>(
    API_ROUTES.sustainability.assessments,
    { params },
  );
  return res.data;
}
