'use client';

import { useMemo } from 'react';

import { formatPassRate, passRateTier } from '@/lib/audits/format';
import type { FairnessAggregate, FairnessCell } from '@/lib/audits/types';
import { toneForRisk } from '@/lib/risk/tones';
import { cn } from '@/lib/utils';

type IntersectionalFairnessGridProps = {
  data: FairnessAggregate | undefined;
  isLoading: boolean;
};

/**
 * Intersectional fairness grid — Phase-4 wave 4 (TASK-043, FE-017).
 *
 * Pivots `/api/v1/audits/fairness`'s `by_attribute_metric` cells onto
 * a 2-D matrix: rows are protected attributes, columns are fairness
 * metrics. Each cell carries:
 *   • a pass-rate badge tone-coded by the 4/5ths-rule tier
 *   • the average raw metric value (when present)
 *   • a `title` tooltip with the full breakdown
 *
 * The "intersectional" framing here is per
 * `(protected_attribute × fairness_metric)` — surfacing whether a
 * specific attribute fails a specific metric (e.g. `gender` failing
 * `equal_opportunity` while passing `demographic_parity`). A future
 * iteration can extend to per-group cells once the recruitment
 * fairness auditor writes per-group metric values into the audit
 * payload (today only per-attribute aggregates land there).
 */
export function IntersectionalFairnessGrid({
  data,
  isLoading,
}: IntersectionalFairnessGridProps) {
  const matrix = useMemo(() => buildMatrix(data?.by_attribute_metric ?? []), [data]);

  if (isLoading && !data) return <GridSkeleton />;

  return (
    <article className="rounded-2xl border border-white/10 bg-white/[0.02] p-5">
      <header className="mb-4 flex items-baseline justify-between gap-3">
        <div>
          <span className="block font-ui text-[10px] uppercase tracking-widest text-text-secondary">
            Intersectional fairness grid
          </span>
          <span className="mt-0.5 block font-ui text-[11px] text-text-secondary/80">
            Protected attribute × fairness metric · cells are pass rates
          </span>
        </div>
        <span className="font-data text-[11px] text-text-secondary">
          {matrix.attributes.length}×{matrix.metrics.length} cells
        </span>
      </header>

      {matrix.cells.length === 0 ? (
        <p className="font-ui text-sm text-text-secondary">
          No structured fairness metrics in the audit window yet. The recruitment module
          writes one cell per protected attribute × metric pair — run an analysis with
          protected attributes selected to populate the grid.
        </p>
      ) : (
        <div className="overflow-x-auto pr-1">
          <table
            aria-label="Fairness grid: rows are protected attributes, columns are fairness metrics"
            className="w-full min-w-[420px] border-separate border-spacing-1.5 font-ui text-xs"
          >
            <thead>
              <tr>
                <th
                  scope="col"
                  className="text-left font-medium text-text-secondary"
                >
                  Attribute
                </th>
                {matrix.metrics.map((metric) => (
                  <th
                    key={metric}
                    scope="col"
                    className="text-left font-medium text-text-secondary"
                    title={metric}
                  >
                    {formatMetricLabel(metric)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {matrix.attributes.map((attribute) => (
                <tr key={attribute}>
                  <th
                    scope="row"
                    className="whitespace-nowrap text-left font-medium text-text-primary"
                  >
                    {attribute}
                  </th>
                  {matrix.metrics.map((metric) => {
                    const cell = matrix.lookup.get(cellKey(attribute, metric));
                    return (
                      <td key={metric} className="align-top">
                        {cell ? <GridCell cell={cell} /> : <EmptyCell />}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </article>
  );
}

function GridCell({ cell }: { cell: FairnessCell }) {
  const tier = passRateTier(cell.pass_rate);
  const tone = toneForRisk(tier);
  const tooltip = describeCell(cell);
  return (
    <div
      title={tooltip}
      className={cn(
        'flex h-full min-h-[56px] flex-col justify-between rounded-md border border-white/5 px-2.5 py-2 transition-colors',
        tone.bg,
      )}
    >
      <span
        className={cn('font-data text-sm font-medium tabular-nums', tone.text)}
      >
        {formatPassRate(cell.pass_rate)}
      </span>
      <span className="font-data text-[10px] text-text-secondary/85 tabular-nums">
        {cell.avg_value !== null ? `avg ${cell.avg_value.toFixed(3)}` : '—'}
        {cell.threshold !== null && (
          <span className="ml-1 text-text-secondary/60">/ {cell.threshold.toFixed(2)}</span>
        )}
      </span>
    </div>
  );
}

function EmptyCell() {
  return (
    <div className="flex h-full min-h-[56px] items-center justify-center rounded-md border border-dashed border-white/10 bg-white/[0.01] font-data text-[10px] text-text-secondary/50">
      —
    </div>
  );
}

function GridSkeleton() {
  return (
    <article
      aria-hidden
      className="h-56 animate-pulse rounded-2xl border border-white/10 bg-white/[0.02]"
    />
  );
}

// ── matrix helpers — pure, testable ────────────────────────────────

export type FairnessMatrix = {
  attributes: string[]; // row labels, sorted
  metrics: string[]; // column labels, sorted
  cells: FairnessCell[]; // pass-through
  lookup: Map<string, FairnessCell>; // O(1) cell access
};

export function buildMatrix(cells: readonly FairnessCell[]): FairnessMatrix {
  const attributes = new Set<string>();
  const metrics = new Set<string>();
  const lookup = new Map<string, FairnessCell>();
  for (const cell of cells) {
    attributes.add(cell.attribute);
    metrics.add(cell.metric_name);
    lookup.set(cellKey(cell.attribute, cell.metric_name), cell);
  }
  return {
    attributes: Array.from(attributes).sort(),
    metrics: Array.from(metrics).sort(),
    cells: Array.from(cells),
    lookup,
  };
}

export function cellKey(attribute: string, metric: string): string {
  return `${attribute}::${metric}`;
}

/** Compress snake_case metric names into a tighter display form so
 * the column header doesn't run wide. `demographic_parity` →
 * `Demographic Parity`; falls back to the raw name when there's no
 * underscore to split on. */
export function formatMetricLabel(metric: string): string {
  if (!metric.includes('_')) return metric;
  return metric
    .split('_')
    .map((s) => (s.length === 0 ? s : s[0]!.toUpperCase() + s.slice(1)))
    .join(' ');
}

export function describeCell(cell: FairnessCell): string {
  const lines = [
    `${cell.attribute} × ${cell.metric_name}`,
    `${cell.pass_count} of ${cell.decision_count} decisions passed (${formatPassRate(cell.pass_rate)})`,
  ];
  if (cell.avg_value !== null) lines.push(`avg metric value ${cell.avg_value.toFixed(4)}`);
  if (cell.threshold !== null) lines.push(`pass threshold ${cell.threshold.toFixed(4)}`);
  return lines.join('\n');
}
