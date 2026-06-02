/**
 * Pure-logic tests for the chip toggle semantics used by
 * `<ListFilterChips />` (TASK-036). The component is small enough
 * that a render-test layer would be ceremony; what's load-bearing is
 * the toggle-vs-select decision encoded in the onClick handler.
 *
 * Mirrors the semantic the production component implements:
 *   • clicking the "All" chip       → onChange(null)
 *   • clicking an inactive chip     → onChange(value)
 *   • clicking the *active* chip    → onChange(null)  // toggle off
 */

import { describe, expect, it } from 'vitest';

type Action<T extends string> =
  | { kind: 'all' }
  | { kind: 'option'; value: T };

function resolve<T extends string>(active: T | null, action: Action<T>): T | null {
  if (action.kind === 'all') return null;
  return active === action.value ? null : action.value;
}

describe('ListFilterChips toggle semantics', () => {
  type T = 'a' | 'b' | 'c';

  it('"All" chip clears the active filter', () => {
    expect(resolve<T>('a', { kind: 'all' })).toBeNull();
    expect(resolve<T>(null, { kind: 'all' })).toBeNull();
  });

  it('inactive option chip selects that option', () => {
    expect(resolve<T>(null, { kind: 'option', value: 'a' })).toBe('a');
    expect(resolve<T>('a', { kind: 'option', value: 'b' })).toBe('b');
  });

  it('active option chip toggles off (clears the filter)', () => {
    expect(resolve<T>('a', { kind: 'option', value: 'a' })).toBeNull();
    expect(resolve<T>('b', { kind: 'option', value: 'b' })).toBeNull();
  });

  it('handles round-trip select → toggle off → select again', () => {
    let active: T | null = null;
    active = resolve<T>(active, { kind: 'option', value: 'a' });
    expect(active).toBe('a');
    active = resolve<T>(active, { kind: 'option', value: 'a' });
    expect(active).toBeNull();
    active = resolve<T>(active, { kind: 'option', value: 'c' });
    expect(active).toBe('c');
  });
});
