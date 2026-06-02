'use client';

import { formatPassRate, passRateTier } from '@/lib/audits/format';
import type { FairnessAggregate } from '@/lib/audits/types';
import { toneForRisk } from '@/lib/risk/tones';
import { cn } from '@/lib/utils';

type FairnessByAttributeCardProps = {
  data: FairnessAggregate | undefined;
  isLoading: boolean;
};

/**
 * Per-protected-attribute fairness card — Phase-4 wave 2 (TASK-031,
 * FAIR-003). Renders the `/api/v1/audits/fairness` aggregation as a
 * table of attribute buckets with pass-rate progress bars and a
 * tone-coded badge tied to the 4/5ths-rule thresholds.
 *
 * Empty state: when no audit row carries a per-attribute fairness
 * summary (a fresh user, or one who has only used non-fairness
 * modules), shows a stable callout explaining the surface.
 *
 * Loading state: skeleton bars matching the typical row shape so
 * the page layout doesn't shift on first render.
 */
export function FairnessByAttributeCard({ data, isLoading }: FairnessByAttributeCardProps) {
  if (isLoading && !data) return <FairnessSkeleton />;

  const total = data?.total_audited_decisions ?? 0;
  const buckets = data?.by_attribute ?? [];

  return (
    <article className="rounded-2xl border border-white/10 bg-white/[0.02] p-5">
      <header className="mb-4 flex items-baseline justify-between gap-3">
        <span className="font-ui text-[10px] uppercase tracking-widest text-text-secondary">
          Fairness by protected attribute
        </span>
        <span className="font-data text-[11px] text-text-secondary">
          {total} audited decision{total === 1 ? '' : 's'}
        </span>
      </header>

      {buckets.length === 0 ? (
        <p className="font-ui text-sm text-text-secondary">
          No audited decisions carry a per-attribute fairness summary yet. The recruitment
          module is the only one writing this slice today — run an analysis with protected
          attributes selected to populate this card.
        </p>
      ) : (
        <ul className="space-y-3" aria-label="Per-attribute pass rates">
          {buckets.map((row) => {
            const tier = passRateTier(row.pass_rate);
            const tone = toneForRisk(tier);
            const widthPct = Math.max(2, Math.round(row.pass_rate * 100));
            return (
              <li key={row.attribute} className="flex flex-col gap-1.5">
                <div className="flex items-baseline justify-between font-ui text-xs">
                  <span className="text-text-primary">
                    {row.attribute}
                    <span className="ml-2 font-data text-[11px] text-text-secondary">
                      {row.pass_count}/{row.decision_count} pass
                      {row.fail_count > 0 && (
                        <>
                          {' · '}
                          <span className="text-coral">{row.fail_count} fail</span>
                        </>
                      )}
                    </span>
                  </span>
                  <span
                    className={cn(
                      'font-data text-sm font-medium tabular-nums',
                      tone.text,
                    )}
                  >
                    {formatPassRate(row.pass_rate)}
                  </span>
                </div>
                <div
                  role="progressbar"
                  aria-valuenow={Math.round(row.pass_rate * 100)}
                  aria-valuemin={0}
                  aria-valuemax={100}
                  className="h-1.5 overflow-hidden rounded-full bg-white/[0.06]"
                >
                  <span
                    className={cn('block h-full rounded-full transition-all', tone.bg)}
                    style={{ width: `${widthPct}%` }}
                  />
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </article>
  );
}

function FairnessSkeleton() {
  return (
    <article
      aria-hidden
      className="h-56 animate-pulse rounded-2xl border border-white/10 bg-white/[0.02]"
    />
  );
}
