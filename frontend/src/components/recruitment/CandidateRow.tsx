'use client';

import { memo, useState } from 'react';

import { LimePanel } from '@/components/shap/LimePanel';
import { ShapPanel } from '@/components/shap/ShapPanel';
import { formatPercent } from '@/lib/recruitment/format';
import type { CandidateRankingResult } from '@/lib/recruitment/types';
import { cn } from '@/lib/utils';

type CandidateRowProps = {
  candidate: CandidateRankingResult;
};

/**
 * One row of the ranked candidates list.
 *
 * **Perf (TASK-039)**: wrapped in `React.memo` so re-ranking (the
 * common case where the user changes the `ensemble_sbert_weight`
 * slider or runs a second analyze) only re-renders the rows whose
 * underlying CandidateRankingResult reference actually changed. The
 * default `Object.is` comparison is safe here because each result is
 * a fresh object per analyze; identical analyses produce identical
 * references via React Query's structural sharing.
 */
export const CandidateRow = memo(function CandidateRow({
  candidate,
}: CandidateRowProps) {
  const [open, setOpen] = useState(false);

  return (
    <li className="rounded-xl border border-white/10 bg-white/[0.02] transition hover:border-white/20">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex w-full items-center justify-between gap-4 px-5 py-4 text-left"
      >
        <div className="flex items-center gap-4">
          <span className="font-data text-2xl font-semibold text-cyan">
            #{String(candidate.rank).padStart(2, '0')}
          </span>
          <div>
            <div className="font-ui text-sm font-medium text-text-primary">
              {candidate.display_name ?? candidate.candidate_id}
            </div>
            <div className="font-ui text-xs text-text-secondary">
              composite {formatPercent(candidate.composite_score)} · semantic{' '}
              {formatPercent(candidate.semantic_score)} · structured{' '}
              {formatPercent(candidate.structured_score)}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-4">
          <ConfidenceChip value={candidate.confidence_level} />
          <span
            aria-hidden
            className={cn(
              'font-data text-base text-text-secondary transition',
              open && 'rotate-180',
            )}
          >
            ▾
          </span>
        </div>
      </button>

      {open && (
        <div className="border-t border-white/10 px-5 pb-5 pt-4">
          <CandidateMeta candidate={candidate} />

          {candidate.ai_rationale && (
            <section aria-label="AI rationale" className="mt-4">
              <h4 className="mb-1 font-ui text-[10px] uppercase tracking-widest text-text-secondary">
                AI rationale
              </h4>
              <p className="font-ui text-sm text-text-primary">{candidate.ai_rationale}</p>
            </section>
          )}

          <section
            aria-label="Feature attribution"
            className="mt-5 grid gap-5 md:grid-cols-2"
          >
            <div>
              <h4 className="mb-2 font-ui text-[10px] uppercase tracking-widest text-text-secondary">
                SHAP attribution
              </h4>
              <p className="mb-2 font-ui text-[10px] text-text-secondary/70">
                Shapley credit on the structured boosting head.
              </p>
              <ShapPanel features={candidate.top_shap_features ?? []} />
            </div>
            <div>
              <h4 className="mb-2 font-ui text-[10px] uppercase tracking-widest text-text-secondary">
                LIME attribution
              </h4>
              <p className="mb-2 font-ui text-[10px] text-text-secondary/70">
                Local linear rules from a perturbation-based surrogate —
                independent of SHAP.
              </p>
              <LimePanel
                features={candidate.top_lime_features ?? []}
                emptyMessage="LIME attributions land here once the real-ML XGBoost explainer is wired."
              />
            </div>
          </section>
        </div>
      )}
    </li>
  );
});

function ConfidenceChip({ value }: { value: number }) {
  const tone =
    value >= 0.75 ? 'text-emerald' : value >= 0.5 ? 'text-gold' : 'text-coral';
  return (
    <div className="hidden flex-col items-end md:flex">
      <span className={cn('font-data text-sm', tone)}>{formatPercent(value)}</span>
      <span className="font-ui text-[10px] uppercase tracking-widest text-text-secondary">
        confidence
      </span>
    </div>
  );
}

function CandidateMeta({ candidate }: { candidate: CandidateRankingResult }) {
  return (
    <dl className="grid grid-cols-1 gap-3 md:grid-cols-3">
      <Meta label="Experience">
        {candidate.years_experience !== null && candidate.years_experience !== undefined
          ? `${candidate.years_experience} years`
          : '—'}
      </Meta>
      <Meta label="Education">{candidate.education_level ?? '—'}</Meta>
      <Meta label="Matched skills">
        {candidate.matched_skills && candidate.matched_skills.length > 0
          ? candidate.matched_skills.join(', ')
          : '—'}
      </Meta>
      <Meta label="Missing skills" className="md:col-span-3">
        {candidate.missing_skills && candidate.missing_skills.length > 0
          ? candidate.missing_skills.join(', ')
          : '—'}
      </Meta>
    </dl>
  );
}

function Meta({
  label,
  children,
  className,
}: {
  label: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={className}>
      <dt className="font-ui text-[10px] uppercase tracking-widest text-text-secondary">{label}</dt>
      <dd className="mt-0.5 font-ui text-sm text-text-primary">{children}</dd>
    </div>
  );
}
