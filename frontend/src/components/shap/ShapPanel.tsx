'use client';

import type { SHAPFeature } from '@/lib/shap/types';

type ShapPanelProps = {
  features: SHAPFeature[];
  /** Optional empty-state message — overrides the default copy. */
  emptyMessage?: string;
};

/**
 * CSS-only horizontal bar chart of per-prediction SHAP attributions.
 *
 * Shared across every module that returns SHAP attributions: each row
 * renders the feature name + the signed magnitude on a symmetric scale
 * around a centre column. Positive contributions push right in cyan,
 * negative push left in coral — the cinematic landing's "lift vs drag"
 * gradient.
 *
 * No chart library: the chart is six rows; the data is already sorted
 * by importance; a CSS-only approach keeps the bundle thin and styling
 * consistent across modules.
 */
export function ShapPanel({ features, emptyMessage }: ShapPanelProps) {
  if (!features || features.length === 0) {
    return (
      <p className="font-ui text-xs text-text-secondary">
        {emptyMessage ?? 'No SHAP attributions available.'}
      </p>
    );
  }

  // Symmetric scale so the +/- magnitudes line up under a centre column.
  const maxAbs = Math.max(0.05, ...features.map((f) => Math.abs(f.shap_value)));

  return (
    <ul className="space-y-2" aria-label="SHAP feature attributions">
      {features.map((feature, i) => {
        const widthPct = Math.min(100, (Math.abs(feature.shap_value) / maxAbs) * 100);
        const isPositive = feature.shap_value >= 0;
        return (
          <li key={`${feature.feature_name}-${i}`} className="font-ui text-xs">
            <div className="mb-1 flex items-center justify-between">
              <span className="text-text-secondary">
                <span className="mr-1 font-data text-text-secondary/70">
                  #{feature.importance_rank}
                </span>
                {feature.feature_name}
                {feature.feature_value !== undefined && (
                  <span className="ml-2 text-text-secondary/60">
                    ({String(feature.feature_value)})
                  </span>
                )}
              </span>
              <span className={isPositive ? 'text-cyan' : 'text-coral'}>
                {formatShap(feature.shap_value)}
              </span>
            </div>
            <div className="flex h-1.5 w-full overflow-hidden rounded-full bg-white/[0.04]">
              <div className="flex w-1/2 justify-end">
                {!isPositive && (
                  <div
                    aria-hidden
                    className="h-full rounded-l-full bg-coral"
                    style={{ width: `${widthPct}%` }}
                  />
                )}
              </div>
              <div className="flex w-1/2">
                {isPositive && (
                  <div
                    aria-hidden
                    className="h-full rounded-r-full bg-cyan"
                    style={{ width: `${widthPct}%` }}
                  />
                )}
              </div>
            </div>
          </li>
        );
      })}
    </ul>
  );
}

// Local copy so the shared panel has no module-specific dependency.
// Same formatter as `lib/recruitment/format.ts`; consolidating to a
// shared `lib/format.ts` is the next-natural cleanup once a third
// module needs it.
function formatShap(value: number): string {
  if (!Number.isFinite(value)) return '—';
  const sign = value > 0 ? '+' : value < 0 ? '−' : '';
  return `${sign}${Math.abs(value).toFixed(2)}`;
}
