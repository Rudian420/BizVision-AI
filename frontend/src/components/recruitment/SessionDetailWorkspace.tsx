'use client';

import Link from 'next/link';

import { formatAuthError } from '@/lib/auth/errors';
import { moduleById } from '@/lib/modules';
import {
  useSessionDetailQuery,
  useSessionFairnessQuery,
} from '@/lib/recruitment/queries';
import type { FairnessMetric } from '@/lib/recruitment/types';
import { cn } from '@/lib/utils';

import { CandidateList } from './CandidateList';
import { RiskBadge } from './RiskBadge';

type SessionDetailWorkspaceProps = {
  sessionId: string;
};

/**
 * Recruitment session detail — TASK-032 deep-link target from the ML
 * Decision Feed's audit row footer. Two-column layout:
 *   • left:  session metadata header + ranked candidates list
 *            (reuses `<CandidateList />` from the analyze workspace
 *            so the visual identity matches)
 *   • right: persisted fairness audit (reconstructed from the DB via
 *            `/recruitment/fairness/{session_id}`, NOT the live
 *            `/analyze` response)
 *
 * The detail endpoint surfaces every candidate (not just top-k) in
 * rank order. SHAP attributions survive the round-trip from the
 * persisted JSONB so the per-candidate explainability collapses
 * still work without a separate fetch.
 */
export function SessionDetailWorkspace({ sessionId }: SessionDetailWorkspaceProps) {
  const meta = moduleById('recruitment');
  const detailQuery = useSessionDetailQuery(sessionId);
  const fairnessQuery = useSessionFairnessQuery(sessionId);

  const errorMessage = detailQuery.isError
    ? formatAuthError(detailQuery.error)
    : fairnessQuery.isError
      ? formatAuthError(fairnessQuery.error)
      : null;

  const detail = detailQuery.data;
  const fairness = fairnessQuery.data;

  return (
    <div className="flex flex-col gap-6">
      <header className="border-b border-white/10 pb-6">
        <div className="mb-2 flex items-center gap-3">
          <Link
            href="/modules/recruitment/sessions"
            className="font-ui text-[10px] uppercase tracking-widest text-text-secondary underline-offset-4 hover:text-text-primary hover:underline"
          >
            ← All sessions
          </Link>
        </div>
        <div className="mb-2 flex items-center gap-3">
          <span className="font-data text-3xl" style={{ color: meta.accent }}>
            {meta.glyph}
          </span>
          <span className="font-ui text-[10px] uppercase tracking-widest text-text-secondary">
            recruitment · session
          </span>
        </div>
        <h2 className="font-ui text-3xl font-semibold tracking-tight text-text-primary">
          {detailQuery.isLoading
            ? 'Loading…'
            : (detail?.job_title ?? 'Session not found')}
        </h2>
        {detail && (
          <p className="mt-2 max-w-2xl font-data text-[11px] text-text-secondary">
            {detail.total_candidates} candidate{detail.total_candidates === 1 ? '' : 's'}
            {' · top '}
            {detail.top_k}
            {' · '}
            {detail.anonymize_names ? 'anonymised' : 'named'}
            {' · '}
            {detail.model_version}
            {' · '}
            {new Date(detail.created_at).toISOString().slice(0, 10)}
          </p>
        )}
      </header>

      {errorMessage && (
        <p
          role="alert"
          className="rounded-md border border-coral/40 bg-coral/10 px-3 py-2 font-ui text-sm text-coral"
        >
          {errorMessage}
        </p>
      )}

      {detail && (
        <div className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,_1fr)_minmax(0,_420px)]">
          <section aria-label="Persisted candidate ranking">
            <h3 className="mb-3 font-ui text-[10px] uppercase tracking-widest text-text-secondary">
              Ranked candidates
            </h3>
            <CandidateList candidates={detail.ranked_candidates} />
          </section>

          <aside aria-label="Fairness audit" className="flex flex-col gap-4">
            {fairnessQuery.isLoading ? (
              <div
                aria-hidden
                className="h-64 animate-pulse rounded-2xl border border-white/10 bg-white/[0.02]"
              />
            ) : fairness ? (
              <PersistedFairnessCard fairness={fairness} />
            ) : null}
          </aside>
        </div>
      )}
    </div>
  );
}

/** Persisted-row fairness card. Differs from `<FairnessSummary />`
 * (which renders the live `/analyze` shape) — this consumes the
 * `FairnessAuditResponse` returned by `/recruitment/fairness/{id}`. */
function PersistedFairnessCard({
  fairness,
}: {
  fairness: {
    overall_risk_level: 'low' | 'medium' | 'high' | 'critical';
    protected_attributes: string[];
    metrics: FairnessMetric[];
    mitigation_strategies: Array<Record<string, unknown>>;
    audit_timestamp: string;
  };
}) {
  return (
    <section
      aria-label="Fairness audit"
      className="rounded-2xl border border-white/10 bg-white/[0.02] p-5"
    >
      <header className="mb-4 flex items-center justify-between gap-4">
        <div>
          <h3 className="font-ui text-base font-semibold text-text-primary">Fairness audit</h3>
          <p className="font-data text-[11px] text-text-secondary">
            {fairness.protected_attributes.length} protected attribute
            {fairness.protected_attributes.length === 1 ? '' : 's'}
            {' · '}
            {new Date(fairness.audit_timestamp).toISOString().slice(0, 10)}
          </p>
        </div>
        <RiskBadge risk={fairness.overall_risk_level} />
      </header>

      {fairness.metrics.length === 0 ? (
        <p className="font-ui text-xs text-text-secondary">
          No fairness metrics recorded for this session.
        </p>
      ) : (
        <ul className="space-y-2.5">
          {fairness.metrics.map((m, i) => (
            <li
              key={`${m.attribute}-${m.metric_name}-${i}`}
              className="rounded-lg border border-white/[0.06] bg-white/[0.02] p-3"
            >
              <div className="flex items-baseline justify-between gap-3 font-ui text-xs">
                <span className="text-text-primary">
                  <span className="font-data uppercase tracking-widest text-text-secondary">
                    {m.attribute}
                  </span>{' '}
                  · {m.metric_name}
                </span>
                <PassFailChip passed={m.passed} />
              </div>
              <div className="mt-1 font-data text-[11px] text-text-secondary">
                value <span className="text-text-primary">{m.value.toFixed(3)}</span> · threshold{' '}
                {m.threshold.toFixed(3)}
              </div>
              {m.interpretation && (
                <p className="mt-1.5 font-ui text-xs text-text-secondary">{m.interpretation}</p>
              )}
            </li>
          ))}
        </ul>
      )}

      {fairness.mitigation_strategies.length > 0 && (
        <section aria-label="Mitigation strategies" className="mt-5">
          <h4 className="mb-2 font-ui text-[10px] uppercase tracking-widest text-text-secondary">
            Mitigation strategies
          </h4>
          <ul className="space-y-1 font-ui text-sm text-text-primary">
            {fairness.mitigation_strategies.map((s, i) => (
              <li key={i} className="flex gap-2">
                <span aria-hidden className="text-cyan">
                  →
                </span>
                <span>
                  {typeof s.strategy === 'string' ? s.strategy : JSON.stringify(s)}
                  {typeof s.expected_effect === 'string' && (
                    <span className="ml-1 text-text-secondary">— {s.expected_effect}</span>
                  )}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </section>
  );
}

function PassFailChip({ passed }: { passed: boolean }) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-md border px-2 py-0.5 font-ui text-[10px] uppercase tracking-widest',
        passed
          ? 'border-emerald/40 bg-emerald/10 text-emerald'
          : 'border-coral/40 bg-coral/10 text-coral',
      )}
    >
      <span aria-hidden className="h-1 w-1 rounded-full bg-current" />
      {passed ? 'pass' : 'fail'}
    </span>
  );
}
