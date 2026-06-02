'use client';

import type { FairnessAuditSummary, FairnessMetric } from '@/lib/recruitment/types';
import { cn } from '@/lib/utils';

import { RiskBadge } from './RiskBadge';

type FairnessSummaryProps = {
  audit: FairnessAuditSummary;
};

/**
 * Thesis-grade panel: per-attribute fairness metrics + overall risk
 * badge + recommendations. The metric table follows ADR-022 / RC-002
 * — each row carries the attribute, metric name, value, threshold,
 * pass/fail, and the interpretation string the backend already
 * generates.
 */
export function FairnessSummary({ audit }: FairnessSummaryProps) {
  return (
    <section
      aria-label="Fairness audit"
      className="rounded-xl border border-white/10 bg-white/[0.02] p-5"
    >
      <header className="mb-4 flex items-center justify-between gap-4">
        <div>
          <h3 className="font-ui text-base font-semibold text-text-primary">Fairness audit</h3>
          <p className="font-ui text-xs text-text-secondary">
            {audit.total_candidates_audited} candidate
            {audit.total_candidates_audited === 1 ? '' : 's'} audited
          </p>
        </div>
        <RiskBadge risk={audit.overall_risk_level} />
      </header>

      <MetricsTable metrics={audit.fairness_metrics} />

      {audit.recommendations.length > 0 && (
        <section aria-label="Recommendations" className="mt-5">
          <h4 className="mb-2 font-ui text-[10px] uppercase tracking-widest text-text-secondary">
            Recommendations
          </h4>
          <ul className="space-y-1">
            {audit.recommendations.map((rec, i) => (
              <li
                key={`${i}-${rec.slice(0, 16)}`}
                className="flex gap-2 font-ui text-sm text-text-primary"
              >
                <span aria-hidden className="text-cyan">
                  →
                </span>
                <span>{rec}</span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </section>
  );
}

function MetricsTable({ metrics }: { metrics: FairnessMetric[] }) {
  if (!metrics || metrics.length === 0) {
    return (
      <p className="font-ui text-xs text-text-secondary">
        No fairness metrics returned for this audit.
      </p>
    );
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-white/[0.06]">
      <table className="w-full border-collapse font-ui text-sm">
        <thead className="bg-white/[0.03] text-left text-[10px] uppercase tracking-widest text-text-secondary">
          <tr>
            <th className="px-3 py-2">Attribute</th>
            <th className="px-3 py-2">Metric</th>
            <th className="px-3 py-2 text-right">Value</th>
            <th className="px-3 py-2 text-right">Threshold</th>
            <th className="px-3 py-2">Status</th>
          </tr>
        </thead>
        <tbody>
          {metrics.map((m, i) => (
            <tr
              key={`${m.attribute}-${m.metric_name}-${i}`}
              className="border-t border-white/[0.06]"
            >
              <td className="px-3 py-2 font-data text-xs uppercase text-text-secondary">
                {m.attribute}
              </td>
              <td className="px-3 py-2 text-text-primary">{m.metric_name}</td>
              <td className="px-3 py-2 text-right font-data text-text-primary">
                {m.value.toFixed(3)}
              </td>
              <td className="px-3 py-2 text-right font-data text-text-secondary">
                {m.threshold.toFixed(3)}
              </td>
              <td className="px-3 py-2">
                <PassFailChip passed={m.passed} />
                <p className="mt-1 text-xs text-text-secondary">{m.interpretation}</p>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
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
