'use client';

import { LimePanel } from '@/components/shap/LimePanel';
import { ShapPanel } from '@/components/shap/ShapPanel';
import type { ESGScoreResponse } from '@/lib/sustainability/types';

import { CompositeScoreCard } from './CompositeScoreCard';
import { PillarBars } from './PillarBars';

type ESGResultsProps = {
  result: ESGScoreResponse;
};

export function ESGResults({ result }: ESGResultsProps) {
  return (
    <section aria-label="ESG assessment" className="space-y-6">
      <header className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="font-ui text-base font-semibold text-text-primary">
          {result.company_name}
        </h3>
        <div className="font-ui text-xs text-text-secondary">
          assessment{' '}
          <span className="font-data text-text-secondary/80">
            {result.assessment_id.slice(0, 8)}
          </span>
        </div>
      </header>

      <CompositeScoreCard result={result} />

      <section
        aria-label="Pillar breakdown"
        className="rounded-xl border border-white/10 bg-white/[0.02] p-5"
      >
        <h3 className="mb-3 font-ui text-base font-semibold text-text-primary">
          Pillar breakdown
        </h3>
        <PillarBars subScores={result.sub_scores} />
      </section>

      <section
        aria-label="Feature attribution"
        className="grid gap-6 rounded-xl border border-white/10 bg-white/[0.02] p-5 md:grid-cols-2"
      >
        <div>
          <h3 className="mb-3 font-ui text-base font-semibold text-text-primary">
            SHAP attribution
          </h3>
          <p className="mb-3 font-ui text-[11px] text-text-secondary/80">
            Closed-form linear contributions on the environmental head:
            `w_i · (x_i − E[x_i])`.
          </p>
          <ShapPanel
            features={result.top_shap_features}
            emptyMessage="No SHAP attributions returned for this assessment."
          />
        </div>
        <div>
          <h3 className="mb-3 font-ui text-base font-semibold text-text-primary">
            LIME attribution
          </h3>
          <p className="mb-3 font-ui text-[11px] text-text-secondary/80">
            Local linear surrogate weights — independent of SHAP.
            Agreement on the top driver is a robustness signal.
          </p>
          <LimePanel
            features={result.top_lime_features ?? []}
            emptyMessage="No LIME attributions returned for this assessment."
          />
        </div>
      </section>
    </section>
  );
}
