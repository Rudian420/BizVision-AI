'use client';

import {
  PILLAR_META,
  PILLAR_ORDER,
  formatScore,
  pillarBarPercent,
  scoreTier,
} from '@/lib/sustainability/format';
import type { ESGSubScores } from '@/lib/sustainability/types';

type PillarBarsProps = {
  subScores: ESGSubScores;
};

/**
 * Per-pillar 0..100 bar chart. CSS-only — same discipline as the
 * SHAP and revenue panels. Each pillar gets its accent colour from
 * `PILLAR_META`; the bar fill width is clamped to [0, 100] by
 * `pillarBarPercent` so an out-of-range server value can't overflow
 * the rendered chart.
 */
export function PillarBars({ subScores }: PillarBarsProps) {
  return (
    <ul className="space-y-3" aria-label="ESG pillar breakdown">
      {PILLAR_ORDER.map((id) => {
        const meta = PILLAR_META[id];
        const score = subScores[id];
        const pct = pillarBarPercent(score);
        const tier = scoreTier(score);
        return (
          <li key={id} className="font-ui text-sm">
            <div className="mb-1 flex items-center justify-between">
              <span className="text-text-primary">
                <span
                  aria-hidden
                  className="mr-2 font-data text-base"
                  style={{ color: meta.accent }}
                >
                  {meta.glyph}
                </span>
                {meta.label}
              </span>
              <span className="font-data text-text-primary">
                {formatScore(score)}
                <span className="ml-2 font-ui text-xs uppercase tracking-widest text-text-secondary">
                  {tier}
                </span>
              </span>
            </div>
            <div className="h-2 w-full overflow-hidden rounded-full bg-white/[0.04]">
              <div
                aria-hidden
                className="h-full rounded-full"
                style={{ width: `${pct}%`, background: meta.accent }}
              />
            </div>
          </li>
        );
      })}
    </ul>
  );
}
