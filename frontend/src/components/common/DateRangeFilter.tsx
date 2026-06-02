'use client';

import {
  DATE_RANGE_PRESETS,
  matchingPresetId,
  type DateRangePreset,
} from '@/lib/audits/date-presets';
import { cn } from '@/lib/utils';

type DateRangeFilterProps = {
  /** ISO date string ("YYYY-MM-DD") or null. */
  since: string | null;
  until: string | null;
  /** Apply handler. Either value may be null to mean "no bound". */
  onChange: (next: { since: string | null; until: string | null }) => void;
  /** Strip heading rendered uppercase + tracking-widest. */
  legend?: string;
  /** Hide the quick-range preset chips (defaults to showing them). */
  hidePresets?: boolean;
};

/**
 * Shared two-input date-range filter strip used by the per-module
 * history list pages (TASK-037).
 *
 * Behaviour:
 *   • Each `<input type="date">` is uncontrolled by default → the
 *     parent passes the current value through `since`/`until` props.
 *   • An empty input value is treated as `null` (i.e. "no bound" on
 *     that side); the parent's queryKey + backend filter both treat
 *     `null` as "ignore this bound".
 *   • A "Clear" button is rendered when either bound is set, so the
 *     user can reset the range without having to clear both inputs
 *     individually.
 *
 * No date validation is enforced client-side beyond the native
 * `<input type="date">` widget — the backend already returns a
 * stable empty page if `since > until`, and a bad date string from a
 * typed input never reaches submission because the input value is
 * always either "" or a valid date.
 */
export function DateRangeFilter({
  since,
  until,
  onChange,
  legend = 'Date range',
  hidePresets = false,
}: DateRangeFilterProps) {
  const showClear = since !== null || until !== null;
  const activePresetId = hidePresets ? null : matchingPresetId(since, until);

  function handleSince(e: React.ChangeEvent<HTMLInputElement>) {
    const next = e.target.value.trim();
    onChange({ since: next === '' ? null : next, until });
  }

  function handleUntil(e: React.ChangeEvent<HTMLInputElement>) {
    const next = e.target.value.trim();
    onChange({ since, until: next === '' ? null : next });
  }

  function handlePreset(preset: DateRangePreset) {
    // Toggle-off semantics: if the user clicks the active preset
    // chip again, clear the range. Matches `<ListFilterChips />`'s
    // posture (TASK-036).
    if (preset.id === activePresetId) {
      onChange({ since: null, until: null });
      return;
    }
    const next = preset.resolve();
    onChange({ since: next.since, until: next.until });
  }

  function handleClear() {
    onChange({ since: null, until: null });
  }

  return (
    <section>
      <h3 className="mb-2 font-ui text-[10px] uppercase tracking-widest text-text-secondary">
        {legend}
      </h3>

      {!hidePresets && (
        <div
          className="mb-2 flex flex-wrap gap-1.5"
          role="toolbar"
          aria-label="Quick date ranges"
        >
          {DATE_RANGE_PRESETS.map((preset) => {
            const isActive = activePresetId === preset.id;
            return (
              <button
                key={preset.id}
                type="button"
                onClick={() => handlePreset(preset)}
                aria-pressed={isActive}
                className={cn(
                  'rounded-full border px-2.5 py-1 font-ui text-[11px] uppercase tracking-widest transition',
                  isActive
                    ? 'border-white/30 bg-white/[0.08] text-text-primary'
                    : 'border-white/10 bg-white/[0.02] text-text-secondary hover:border-white/20 hover:text-text-primary',
                )}
              >
                {preset.label}
              </button>
            );
          })}
        </div>
      )}

      <div className="flex flex-wrap items-center gap-2">
        <label className="flex items-center gap-2 font-ui text-xs text-text-secondary">
          <span>From</span>
          <input
            type="date"
            value={since ?? ''}
            onChange={handleSince}
            aria-label="From date"
            className={inputClassName}
          />
        </label>
        <label className="flex items-center gap-2 font-ui text-xs text-text-secondary">
          <span>To</span>
          <input
            type="date"
            value={until ?? ''}
            onChange={handleUntil}
            aria-label="To date"
            className={inputClassName}
          />
        </label>
        {showClear && (
          <button
            type="button"
            onClick={handleClear}
            className="rounded-md border border-white/10 px-2.5 py-1 font-ui text-[11px] uppercase tracking-widest text-text-secondary transition hover:border-white/30 hover:text-text-primary"
          >
            Clear
          </button>
        )}
      </div>
    </section>
  );
}

const inputClassName = cn(
  'h-8 rounded-md border border-white/10 bg-white/[0.02] px-2 font-data text-xs text-text-primary',
  'focus:outline-none focus:ring-1 focus:ring-white/30',
  // Tailwind doesn't ship date-input native chrome styling; the browser
  // picks one. We keep the field consistently sized so the row doesn't
  // jump when one bound is set and the other isn't.
);
