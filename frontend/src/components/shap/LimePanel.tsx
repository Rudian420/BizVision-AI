'use client';

import type { SHAPFeature } from '@/lib/shap/types';

type LimePanelProps = {
  /** LIME local linear surrogate weights, in the same
   * `SHAPFeature` shape as the SHAP feature list. The backend
   * translator (`ml_translation.ml_recommendation_to_api`) re-uses
   * `SHAPFeature` here because the field shape is structurally
   * identical even though the semantics differ — see this panel's
   * docstring. */
  features: SHAPFeature[];
  /** Optional empty-state message — overrides the default copy. */
  emptyMessage?: string;
};

/**
 * Per-prediction LIME attribution panel — the explainability counterpart
 * to `<ShapPanel>` (FE-016 wave 1, TASK-044).
 *
 * Why LIME *and* SHAP, not just one:
 * - SHAP gives Shapley game-theoretic credit; LIME fits a local
 *   linear surrogate by perturbing the input. They answer the same
 *   *question* ("which features drove this single prediction?") via
 *   different *math*.
 * - Agreement between LIME and SHAP on the top contributors is the
 *   thesis-defendable robustness signal — if both say the same
 *   feature is the strongest driver, the explanation is much harder
 *   to dismiss as artefact-of-one-explainer.
 * - Disagreement is itself informative: a feature that SHAP ranks
 *   high but LIME ranks low (or vice versa) is a flag for the user
 *   to investigate.
 *
 * Visually distinct from `<ShapPanel>`: violet (positive) and gold
 * (negative) instead of cyan / coral, so a reader can tell at a
 * glance which explainer they're looking at. Same CSS-only bar chart
 * shape so the side-by-side comparison stays clean.
 */
export function LimePanel({ features, emptyMessage }: LimePanelProps) {
  if (!features || features.length === 0) {
    return (
      <p className="font-ui text-xs text-text-secondary">
        {emptyMessage ?? 'No LIME attributions available.'}
      </p>
    );
  }

  // Symmetric scale so the +/- magnitudes line up under a centre column.
  // Min-floor at 0.05 avoids divide-by-near-zero artefacts when every
  // weight is tiny.
  const maxAbs = Math.max(0.05, ...features.map((f) => Math.abs(f.shap_value)));

  return (
    <ul className="space-y-2" aria-label="LIME feature attributions">
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
              <span className={isPositive ? 'text-violet' : 'text-gold'}>
                {formatLime(feature.shap_value)}
              </span>
            </div>
            <div className="flex h-1.5 w-full overflow-hidden rounded-full bg-white/[0.04]">
              <div className="flex w-1/2 justify-end">
                {!isPositive && (
                  <div
                    aria-hidden
                    className="h-full rounded-l-full bg-gold"
                    style={{ width: `${widthPct}%` }}
                  />
                )}
              </div>
              <div className="flex w-1/2">
                {isPositive && (
                  <div
                    aria-hidden
                    className="h-full rounded-r-full bg-violet"
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

// Local formatter mirrors `ShapPanel.formatShap`. Consolidating both
// into a shared `lib/format.ts` is the next-natural cleanup once a
// third explainer (Counterfactual? Anchor?) lands.
function formatLime(value: number): string {
  if (!Number.isFinite(value)) return '—';
  const sign = value > 0 ? '+' : value < 0 ? '−' : '';
  return `${sign}${Math.abs(value).toFixed(2)}`;
}
