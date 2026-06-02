'use client';

import { formatElapsed } from '@/lib/recruitment/format';
import type { RecruitmentAnalysisResponse } from '@/lib/recruitment/types';

import { CandidateList } from './CandidateList';
import { FairnessSummary } from './FairnessSummary';

type AnalysisResultsProps = {
  result: RecruitmentAnalysisResponse;
};

export function AnalysisResults({ result }: AnalysisResultsProps) {
  return (
    <section aria-label="Analysis results" className="space-y-6">
      <header className="rounded-xl border border-white/10 bg-white/[0.02] p-5">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h3 className="font-ui text-base font-semibold text-text-primary">{result.job_title}</h3>
          <div className="font-ui text-xs text-text-secondary">
            session{' '}
            <span className="font-data text-text-secondary/80">{result.session_id.slice(0, 8)}</span>
          </div>
        </div>
        <div className="mt-3 grid grid-cols-2 gap-3 md:grid-cols-4">
          <Stat label="Candidates" value={String(result.total_candidates)} />
          <Stat label="Processing" value={formatElapsed(result.processing_time_ms)} />
          <Stat label="Model" value={result.model_version} />
          <Stat label="Risk" value={result.fairness_audit.overall_risk_level} />
        </div>
      </header>

      <FairnessSummary audit={result.fairness_audit} />

      <section aria-label="Ranked candidates">
        <header className="mb-3 flex items-baseline justify-between">
          <h3 className="font-ui text-base font-semibold text-text-primary">Ranked candidates</h3>
          <p className="font-ui text-xs text-text-secondary">
            click a row to see SHAP attribution + AI rationale
          </p>
        </header>
        <CandidateList candidates={result.ranked_candidates} />
      </section>
    </section>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="font-data text-base font-medium text-text-primary">{value}</div>
      <div className="font-ui text-[10px] uppercase tracking-widest text-text-secondary">{label}</div>
    </div>
  );
}
