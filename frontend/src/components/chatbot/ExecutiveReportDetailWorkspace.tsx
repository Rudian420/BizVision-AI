'use client';

import { formatAuthError } from '@/lib/auth/errors';
import { useExecutiveReportDetailQuery } from '@/lib/chatbot/queries';
import { PersistedAnalysisDetail } from '@/components/common/PersistedAnalysisDetail';

type ExecutiveReportDetailWorkspaceProps = {
  reportId: string;
};

/**
 * Chatbot executive-report detail — TASK-034 deep-link target from
 * the ML Decision Feed's audit row footer
 * (`reference_type=chatbot_executive_report`).
 *
 * Reuses the shared `<PersistedAnalysisDetail />` layout — the
 * executive-report row carries a `response_payload` JSONB the same
 * way the polymorphic-table modules do, so one renderer covers it
 * with a thin adapter.
 *
 * Note: the report payload has NO request_payload (the report is
 * generated from a small request that doesn't merit a JSONB roundtrip
 * — only the produced report sections + recommendations + risks are
 * audit-relevant). The shared layout's Request panel renders an
 * "empty request" state for this case.
 */
export function ExecutiveReportDetailWorkspace({
  reportId,
}: ExecutiveReportDetailWorkspaceProps) {
  const query = useExecutiveReportDetailQuery(reportId);
  const detail = query.data;
  const errorMessage = query.isError ? formatAuthError(query.error) : null;

  return (
    <PersistedAnalysisDetail
      module="chatbot"
      backHref="/modules/chatbot"
      backLabel="Chatbot workspace"
      scopeLabel="chatbot · executive report"
      title={detail?.title ?? '…'}
      subtitle={
        detail
          ? `${detail.model_version} · ${detail.period_label} · ${new Date(
              detail.created_at,
            )
              .toISOString()
              .slice(0, 10)}`
          : ''
      }
      headlineCells={
        detail
          ? [
              { label: 'Period', value: detail.period_label },
              { label: 'Modules', value: detail.modules_included.join(', ') },
              { label: 'Title', value: detail.title },
            ]
          : []
      }
      // Reports are self-generated — no caller-supplied request body
      // to surface. The shared layout renders an empty state for
      // this panel.
      requestPayload={{}}
      responsePayload={detail?.response_payload ?? {}}
      isLoading={query.isLoading}
      errorMessage={errorMessage}
    />
  );
}
