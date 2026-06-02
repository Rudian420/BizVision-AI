'use client';

import {
  formatCurrency,
  formatUplift,
  upliftTone,
} from '@/lib/pricing/format';
import type { PriceOptimizationResponse } from '@/lib/pricing/types';
import { cn } from '@/lib/utils';

type RecommendationCardProps = {
  result: PriceOptimizationResponse;
};

/**
 * The headline panel: recommended price, current price, fractional
 * uplift, and confidence band. Fairness-first parallel: pricing's
 * "top-line" metric is the uplift signed magnitude, surfaced in cyan
 * if positive / coral if negative.
 */
export function RecommendationCard({ result }: RecommendationCardProps) {
  const tone = upliftTone(result.expected_revenue_uplift);
  const [ciLow, ciHigh] = normalizeBand(result.confidence_interval);

  return (
    <section
      aria-label="Pricing recommendation"
      className="rounded-xl border border-gold/30 bg-gold/[0.04] p-5 shadow-glow-gold"
    >
      <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
        <div>
          <div className="font-ui text-[10px] uppercase tracking-widest text-text-secondary">
            Recommended price
          </div>
          <div className="mt-1 font-data text-3xl font-semibold text-gold">
            {formatCurrency(result.recommended_price)}
          </div>
          <div className="mt-1 font-ui text-xs text-text-secondary">
            current {formatCurrency(result.current_price)}
          </div>
        </div>

        <div>
          <div className="font-ui text-[10px] uppercase tracking-widest text-text-secondary">
            Expected uplift
          </div>
          <div className={cn('mt-1 font-data text-3xl font-semibold', tone)}>
            {formatUplift(result.expected_revenue_uplift)}
          </div>
          <div className="mt-1 font-ui text-xs text-text-secondary">
            vs current price
          </div>
        </div>

        <div>
          <div className="font-ui text-[10px] uppercase tracking-widest text-text-secondary">
            Confidence band
          </div>
          <div className="mt-1 font-data text-base text-text-primary">
            {formatCurrency(ciLow)} – {formatCurrency(ciHigh)}
          </div>
          <div className="mt-1 font-ui text-xs text-text-secondary">
            {result.model_version}
          </div>
        </div>
      </div>

      {result.ai_rationale && (
        <p className="mt-5 border-t border-gold/15 pt-4 font-ui text-sm text-text-primary">
          {result.ai_rationale}
        </p>
      )}
    </section>
  );
}

/** Pull `[low, high]` out of the API's `confidence_interval` array. */
function normalizeBand(raw: number[] | [number, number]): [number, number] {
  if (raw.length < 2) return [0, 0];
  const a = Number(raw[0]);
  const b = Number(raw[1]);
  if (!Number.isFinite(a) || !Number.isFinite(b)) return [0, 0];
  return a <= b ? [a, b] : [b, a];
}
