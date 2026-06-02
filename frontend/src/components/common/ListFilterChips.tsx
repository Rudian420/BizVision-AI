'use client';

import { cn } from '@/lib/utils';

type FilterOption<T extends string> = {
  /** Value passed to `onChange` when selected. Equality is by ===. */
  value: T;
  /** Display text. */
  label: string;
};

type ListFilterChipsProps<T extends string> = {
  /** Visible chip-strip heading (uppercase tracking-widest). */
  legend: string;
  /** Available options. */
  options: ReadonlyArray<FilterOption<T>>;
  /** Currently active value. `null` = "all" (no filter applied). */
  active: T | null;
  /** Toggle handler — pass null to clear. Clicking the active chip
   * passes null too (chip toggle semantics). */
  onChange: (value: T | null) => void;
  /** Label for the implicit "All" chip that clears the filter. */
  allLabel?: string;
};

/**
 * Single-select chip strip used by the per-module history list pages
 * (TASK-036). Mirrors the posture used by `AuditFilters` on the
 * Decision Feed — single-select per strip with an explicit "All" chip
 * that clears the filter. Clicking the active chip is a toggle-off.
 *
 * Generic over the value type so each consumer keeps strong typing
 * (e.g. `PricingAnalysisType`, `ForecastAnalysisType`,
 * `SustainabilityAssessmentType`) without casting at the call site.
 */
export function ListFilterChips<T extends string>({
  legend,
  options,
  active,
  onChange,
  allLabel = 'All',
}: ListFilterChipsProps<T>) {
  return (
    <section>
      <h3 className="mb-2 font-ui text-[10px] uppercase tracking-widest text-text-secondary">
        {legend}
      </h3>
      <div className="flex flex-wrap gap-2" role="toolbar" aria-label={legend}>
        <Chip
          label={allLabel}
          active={active === null}
          onClick={() => onChange(null)}
        />
        {options.map((opt) => {
          const isActive = active === opt.value;
          return (
            <Chip
              key={opt.value}
              label={opt.label}
              active={isActive}
              onClick={() => onChange(isActive ? null : opt.value)}
            />
          );
        })}
      </div>
    </section>
  );
}

type ChipProps = {
  label: string;
  active: boolean;
  onClick: () => void;
};

function Chip({ label, active, onClick }: ChipProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full border px-3 py-1 font-ui text-xs uppercase tracking-widest transition',
        active
          ? 'border-white/30 bg-white/[0.08] text-text-primary'
          : 'border-white/10 bg-white/[0.02] text-text-secondary hover:border-white/20 hover:text-text-primary',
      )}
    >
      {label}
    </button>
  );
}
