'use client';

import { RiskBadge } from '@/components/common/RiskBadge';
import {
  formatScore,
  regulatoryRiskLabel,
  scoreTier,
  scoreTierTone,
} from '@/lib/sustainability/format';
import type { ESGScoreResponse } from '@/lib/sustainability/types';
import { cn } from '@/lib/utils';

type CompositeScoreCardProps = {
  result: ESGScoreResponse;
};

/**
 * Headline composite score panel — big number + risk badge +
 * industry percentile + regulatory-risk chip. Same role as
 * pricing's `RecommendationCard` and forecasting's `ScenarioCards`:
 * a stat strip that reads at a glance before the user drills into
 * the per-pillar breakdown.
 */
export function CompositeScoreCard({ result }: CompositeScoreCardProps) {
  const tier = scoreTier(result.composite_score);
  const tone = scoreTierTone(result.composite_score);

  return (
    <section
      aria-label="Composite ESG score"
      className="rounded-xl border border-emerald/30 bg-emerald/[0.04] p-5 shadow-glow-emerald"
    >
      <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
        <div>
          <div className="font-ui text-[10px] uppercase tracking-widest text-text-secondary">
            Composite score
          </div>
          <div className={cn('mt-1 font-data text-4xl font-semibold', tone)}>
            {formatScore(result.composite_score)}
          </div>
          <div className="mt-1 font-ui text-xs uppercase tracking-widest text-text-secondary">
            {tier} · {result.industry}
          </div>
        </div>

        <div>
          <div className="font-ui text-[10px] uppercase tracking-widest text-text-secondary">
            Industry percentile
          </div>
          <div className="mt-1 font-data text-3xl font-semibold text-text-primary">
            {formatScore(result.industry_percentile, 0)}
          </div>
          <div className="mt-1 font-ui text-xs text-text-secondary">
            ranked vs sector peers
          </div>
        </div>

        <div className="flex flex-col items-start gap-2">
          <RiskBadge risk={result.risk_level} />
          <RegulatoryChip flag={result.regulatory_risk_flag} />
          <div className="font-ui text-xs text-text-secondary">
            {result.model_version}
          </div>
        </div>
      </div>
    </section>
  );
}

function RegulatoryChip({ flag }: { flag: boolean }) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full border px-3 py-1 font-ui text-xs font-medium uppercase tracking-wider',
        flag
          ? 'border-coral/40 bg-coral/10 text-coral'
          : 'border-emerald/40 bg-emerald/10 text-emerald',
      )}
    >
      <span aria-hidden className="h-1.5 w-1.5 rounded-full bg-current" />
      {regulatoryRiskLabel(flag)}
    </span>
  );
}
