/**
 * Date-range presets used by `<DateRangeFilter />`'s quick-range
 * strip (TASK-038). Each preset returns a `{since, until}` pair as
 * ISO-date strings (`YYYY-MM-DD`) — the same shape the filter's
 * `<input type="date">` produces, so the parent state stays flat.
 *
 * `now` is injected for testability; production callers can omit it
 * to use the real wall clock.
 */

export type DateRangePreset = {
  /** Stable identifier (used by tests + the chip's `aria-pressed`). */
  id: 'last7' | 'last30' | 'this-month' | 'last-month' | 'this-year';
  /** Display label on the chip. */
  label: string;
  /** Resolver — returns the bounds at evaluation time so "now" stays current. */
  resolve: (now?: Date) => { since: string; until: string };
};

/** "YYYY-MM-DD" from a Date in the user's local calendar. We avoid
 * `toISOString()` because that emits UTC, which can shift the date by
 * a day when the user's offset is non-zero and they pick "today". */
export function toISODate(date: Date): string {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, '0');
  const d = String(date.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
}

function addDays(d: Date, n: number): Date {
  const out = new Date(d);
  out.setDate(out.getDate() + n);
  return out;
}

function startOfMonth(d: Date): Date {
  return new Date(d.getFullYear(), d.getMonth(), 1);
}

function endOfMonth(d: Date): Date {
  // Day 0 of next month = last day of this month.
  return new Date(d.getFullYear(), d.getMonth() + 1, 0);
}

function startOfYear(d: Date): Date {
  return new Date(d.getFullYear(), 0, 1);
}

function endOfYear(d: Date): Date {
  return new Date(d.getFullYear(), 11, 31);
}

export const DATE_RANGE_PRESETS: ReadonlyArray<DateRangePreset> = [
  {
    id: 'last7',
    label: 'Last 7 days',
    resolve: (now = new Date()) => ({
      since: toISODate(addDays(now, -6)),
      until: toISODate(now),
    }),
  },
  {
    id: 'last30',
    label: 'Last 30 days',
    resolve: (now = new Date()) => ({
      since: toISODate(addDays(now, -29)),
      until: toISODate(now),
    }),
  },
  {
    id: 'this-month',
    label: 'This month',
    resolve: (now = new Date()) => ({
      since: toISODate(startOfMonth(now)),
      until: toISODate(endOfMonth(now)),
    }),
  },
  {
    id: 'last-month',
    label: 'Last month',
    resolve: (now = new Date()) => {
      const lastMonth = new Date(now.getFullYear(), now.getMonth() - 1, 1);
      return {
        since: toISODate(startOfMonth(lastMonth)),
        until: toISODate(endOfMonth(lastMonth)),
      };
    },
  },
  {
    id: 'this-year',
    label: 'This year',
    resolve: (now = new Date()) => ({
      since: toISODate(startOfYear(now)),
      until: toISODate(endOfYear(now)),
    }),
  },
] as const;

/** Resolve a preset by id at call time. */
export function resolvePreset(
  id: DateRangePreset['id'],
  now?: Date,
): { since: string; until: string } {
  const preset = DATE_RANGE_PRESETS.find((p) => p.id === id);
  if (!preset) throw new Error(`Unknown date-range preset: ${id}`);
  return preset.resolve(now);
}

/** Find which preset (if any) matches the current bounds. Used for
 * the chip's `aria-pressed` state — the bounds compare by string
 * equality so trailing-time components don't matter. */
export function matchingPresetId(
  since: string | null,
  until: string | null,
  now: Date = new Date(),
): DateRangePreset['id'] | null {
  if (!since || !until) return null;
  for (const preset of DATE_RANGE_PRESETS) {
    const r = preset.resolve(now);
    if (r.since === since && r.until === until) return preset.id;
  }
  return null;
}
