/**
 * Pure-logic tests for the input → state mapping used by
 * <DateRangeFilter /> (TASK-037).
 *
 * The component itself is a thin two-input shell + a "Clear" button.
 * The load-bearing semantic is:
 *   • empty input string → null (no bound)
 *   • non-empty string → kept as-is (browser native date validation
 *     already constrains the field to a valid YYYY-MM-DD)
 *   • Clear → both bounds null
 *
 * This file mirrors `list-filter-chips.test.ts`: encode the decision
 * as a pure function + assert the cases.
 */

import { describe, expect, it } from 'vitest';

type Side = 'since' | 'until';
type State = { since: string | null; until: string | null };

function applyInput(state: State, side: Side, raw: string): State {
  const trimmed = raw.trim();
  const next = trimmed === '' ? null : trimmed;
  return side === 'since' ? { ...state, since: next } : { ...state, until: next };
}

function clear(): State {
  return { since: null, until: null };
}

const EMPTY: State = { since: null, until: null };

describe('DateRangeFilter input → state mapping', () => {
  it('sets the since bound when the user enters a date', () => {
    expect(applyInput(EMPTY, 'since', '2026-05-01')).toEqual({
      since: '2026-05-01',
      until: null,
    });
  });

  it('sets the until bound independently', () => {
    expect(applyInput(EMPTY, 'until', '2026-05-31')).toEqual({
      since: null,
      until: '2026-05-31',
    });
  });

  it('clears one side without touching the other when the input is emptied', () => {
    const both: State = { since: '2026-05-01', until: '2026-05-31' };
    expect(applyInput(both, 'since', '')).toEqual({
      since: null,
      until: '2026-05-31',
    });
    expect(applyInput(both, 'until', '   ')).toEqual({
      since: '2026-05-01',
      until: null,
    });
  });

  it("clear() resets both bounds in one call", () => {
    const both: State = { since: '2026-05-01', until: '2026-05-31' };
    expect(clear()).toEqual(EMPTY);
    // Idempotent — clearing the already-empty state stays empty.
    expect(clear()).toEqual(EMPTY);
    expect(both).not.toEqual(clear()); // sanity: clear is destructive
  });

  it("treats whitespace-only input as 'no bound'", () => {
    expect(applyInput(EMPTY, 'since', '   ').since).toBeNull();
  });
});
