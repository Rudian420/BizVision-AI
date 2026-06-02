'use client';

import { LimePanel } from '@/components/shap/LimePanel';
import { ShapPanel } from '@/components/shap/ShapPanel';
import { formatCurrency } from '@/lib/pricing/format';
import type {
  PriceOptimizationRequest,
  PriceOptimizationResponse,
} from '@/lib/pricing/types';

import { RecommendationCard } from './RecommendationCard';
import { RevenueCurveChart } from './RevenueCurveChart';

type PricingResultsProps = {
  result: PriceOptimizationResponse;
  /** Echo of the request — needed for the chart's objective + currentPrice. */
  request: PriceOptimizationRequest;
};

export function PricingResults({ result, request }: PricingResultsProps) {
  return (
    <section aria-label="Pricing analysis" className="space-y-6">
      <header className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="font-ui text-base font-semibold text-text-primary">
          {result.product_id}
        </h3>
        <div className="font-ui text-xs text-text-secondary">
          analysis{' '}
          <span className="font-data text-text-secondary/80">
            {result.analysis_id.slice(0, 8)}
          </span>
        </div>
      </header>

      <RecommendationCard result={result} />

      <section
        aria-label="Revenue curve"
        className="rounded-xl border border-white/10 bg-white/[0.02] p-5"
      >
        <RevenueCurveChart
          curve={result.revenue_curve}
          objective={request.objective ?? 'revenue'}
          currentPrice={result.current_price}
          recommendedPrice={result.recommended_price}
        />
        <CurveTable result={result} />
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
            Game-theoretic Shapley credit from the LightGBM TreeExplainer.
          </p>
          <ShapPanel
            features={result.top_shap_features}
            emptyMessage="No SHAP attributions returned for this analysis."
          />
        </div>
        <div>
          <h3 className="mb-3 font-ui text-base font-semibold text-text-primary">
            LIME attribution
          </h3>
          <p className="mb-3 font-ui text-[11px] text-text-secondary/80">
            Local linear surrogate weights — independent of SHAP. Agreement on
            top features is a robustness signal.
          </p>
          <LimePanel
            features={result.top_lime_features ?? []}
            emptyMessage="No LIME attributions returned for this analysis."
          />
        </div>
      </section>
    </section>
  );
}

/**
 * Compact 4-row preview of the revenue curve — first, current-price-
 * adjacent, recommended-price-adjacent, and last point. Surfaces the
 * exact (price, demand, revenue, profit) at the inflection points
 * without dumping the entire curve as a table.
 */
function CurveTable({ result }: { result: PriceOptimizationResponse }) {
  if (!result.revenue_curve || result.revenue_curve.length === 0) return null;
  const curve = result.revenue_curve;
  const first = curve[0];
  const last = curve[curve.length - 1];
  const nearestCurrent = nearestPoint(curve, result.current_price);
  const nearestRecommended = nearestPoint(curve, result.recommended_price);

  // De-duplicate by price so we don't render the same row twice when
  // a price is at the curve endpoint.
  const rows = uniqueByPrice([first, nearestCurrent, nearestRecommended, last]);

  return (
    <div className="mt-4 overflow-x-auto rounded-lg border border-white/[0.06]">
      <table className="w-full border-collapse font-ui text-sm">
        <thead className="bg-white/[0.03] text-left text-[10px] uppercase tracking-widest text-text-secondary">
          <tr>
            <th className="px-3 py-2">Marker</th>
            <th className="px-3 py-2 text-right">Price</th>
            <th className="px-3 py-2 text-right">Demand</th>
            <th className="px-3 py-2 text-right">Revenue</th>
            <th className="px-3 py-2 text-right">Profit</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const label = labelFor(row, result.current_price, result.recommended_price);
            return (
              <tr
                key={`${row.price.toFixed(4)}-${label}`}
                className="border-t border-white/[0.06]"
              >
                <td className="px-3 py-2 font-data text-xs uppercase text-text-secondary">
                  {label}
                </td>
                <td className="px-3 py-2 text-right font-data text-text-primary">
                  {formatCurrency(row.price)}
                </td>
                <td className="px-3 py-2 text-right font-data text-text-secondary">
                  {row.expected_demand.toFixed(1)}
                </td>
                <td className="px-3 py-2 text-right font-data text-text-primary">
                  {formatCurrency(row.expected_revenue)}
                </td>
                <td className="px-3 py-2 text-right font-data text-text-primary">
                  {formatCurrency(row.expected_profit)}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function nearestPoint(
  curve: PriceOptimizationResponse['revenue_curve'],
  target: number,
): PriceOptimizationResponse['revenue_curve'][number] {
  let best = curve[0];
  let bestDist = Math.abs(best.price - target);
  for (let i = 1; i < curve.length; i++) {
    const d = Math.abs(curve[i].price - target);
    if (d < bestDist) {
      best = curve[i];
      bestDist = d;
    }
  }
  return best;
}

function uniqueByPrice<T extends { price: number }>(rows: T[]): T[] {
  const seen = new Set<string>();
  const out: T[] = [];
  for (const row of rows) {
    const key = row.price.toFixed(4);
    if (!seen.has(key)) {
      seen.add(key);
      out.push(row);
    }
  }
  return out;
}

function labelFor(
  row: { price: number },
  currentPrice: number,
  recommendedPrice: number,
): string {
  if (row.price === recommendedPrice) return 'recommended';
  if (row.price === currentPrice) return 'current';
  return 'curve';
}
