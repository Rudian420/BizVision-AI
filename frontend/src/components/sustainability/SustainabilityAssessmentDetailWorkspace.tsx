'use client';

import { formatAuthError } from '@/lib/auth/errors';
import { useAssessmentDetailQuery } from '@/lib/sustainability/queries';
import { formatAction } from '@/lib/audits/format';
import { PersistedAnalysisDetail } from '@/components/common/PersistedAnalysisDetail';
import { RiskBadge } from '@/components/common/RiskBadge';
import type { RiskLevel } from '@/lib/risk/types';

type SustainabilityAssessmentDetailWorkspaceProps = {
  assessmentId: string;
};

const KNOWN_RISK_TIERS: ReadonlySet<RiskLevel> = new Set<RiskLevel>([
  'low',
  'medium',
  'high',
  'critical',
]);

/**
 * Sustainability assessment detail — TASK-033 deep-link target
 * from the ML Decision Feed's audit row footer
 * (`reference_type=sustainability_assessment`).
 *
 * Polymorphic-table renderer — one component covers all 4 variants
 * (score / simulation / recommendations / carbon_estimate). The
 * `risk_level` from the score variant is the only module so far
 * that populates `risk_tier` on the audit log, so the shared
 * RiskBadge is shown when present.
 */
export function SustainabilityAssessmentDetailWorkspace({
  assessmentId,
}: SustainabilityAssessmentDetailWorkspaceProps) {
  const query = useAssessmentDetailQuery(assessmentId);
  const detail = query.data;
  const errorMessage = query.isError ? formatAuthError(query.error) : null;

  const riskValue = detail?.risk_level;
  const showRisk = !!riskValue && KNOWN_RISK_TIERS.has(riskValue as RiskLevel);

  return (
    <PersistedAnalysisDetail
      module="sustainability"
      backHref="/modules/sustainability"
      backLabel="Sustainability workspace"
      scopeLabel={`sustainability · ${detail?.assessment_type ?? 'assessment'}`}
      title={
        detail
          ? `${formatAction(detail.assessment_type)} · ${detail.company_name ?? detail.industry ?? '—'}`
          : '…'
      }
      subtitle={
        detail
          ? `${detail.model_version} · ${new Date(detail.created_at)
              .toISOString()
              .slice(0, 10)} · ${detail.processing_time_ms.toFixed(1)}ms`
          : ''
      }
      riskSlot={showRisk ? <RiskBadge risk={riskValue as RiskLevel} /> : null}
      headlineCells={
        detail
          ? [
              { label: 'Composite score', value: detail.composite_score?.toFixed(1) ?? null },
              { label: 'Industry', value: detail.industry },
              {
                label: 'Total tCO2e',
                value: detail.total_tco2e !== null ? detail.total_tco2e.toFixed(2) : null,
              },
              { label: 'Risk level', value: detail.risk_level ?? null },
            ]
          : []
      }
      interpretation={detail?.interpretation ?? null}
      requestPayload={detail?.request_payload ?? {}}
      responsePayload={detail?.response_payload ?? {}}
      isLoading={query.isLoading}
      errorMessage={errorMessage}
    />
  );
}
