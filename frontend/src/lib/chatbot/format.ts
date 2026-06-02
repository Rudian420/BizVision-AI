/**
 * Display formatters + module-context helpers for the chatbot UI.
 *
 * Kept here (not in components) so the test suite can verify them
 * without rendering React.
 */

import { MODULES, type ModuleMeta } from '@/lib/modules';

/**
 * Human-friendly relative time — "just now" / "5m ago" / "3h ago" /
 * "yesterday" / "Apr 14". Uses a single `now` argument so the test
 * suite can inject deterministic timestamps.
 */
export function formatRelativeTime(isoOrDate: string | Date, now: Date = new Date()): string {
  const then = typeof isoOrDate === 'string' ? new Date(isoOrDate) : isoOrDate;
  if (Number.isNaN(then.getTime())) return '—';
  const diffMs = now.getTime() - then.getTime();
  const minutes = Math.round(diffMs / 60_000);
  if (minutes < 1) return 'just now';
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(diffMs / 3_600_000);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.round(diffMs / 86_400_000);
  if (days === 1) return 'yesterday';
  if (days < 7) return `${days}d ago`;
  // Older — drop to month+day for a stable label across years.
  return new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric' }).format(then);
}

/** Compact ISO-time HH:MM for in-thread timestamps. */
export function formatClockTime(isoOrDate: string | Date): string {
  const d = typeof isoOrDate === 'string' ? new Date(isoOrDate) : isoOrDate;
  if (Number.isNaN(d.getTime())) return '—';
  return new Intl.DateTimeFormat(undefined, {
    hour: '2-digit',
    minute: '2-digit',
  }).format(d);
}

/**
 * Module-context catalog — the *other four* modules a chatbot
 * conversation can fold in via `include_modules`. Excludes the
 * chatbot itself (self-referential is meaningless) and "general"
 * (the chatbot's default scope when nothing else is selected).
 */
export const CONTEXT_MODULES: readonly ModuleMeta[] = MODULES.filter(
  (m) => m.id !== 'chatbot',
);

/** Map a module id → its metadata (accent + glyph + label). */
export function moduleMetaById(id: string): ModuleMeta | null {
  return MODULES.find((m) => m.id === id) ?? null;
}

/**
 * Derive a tier from the elapsed-since-update for the conversation
 * list's freshness affordance. Lets the sidebar surface "fresh"
 * conversations without parsing a date string in JSX.
 */
export type FreshnessTier = 'fresh' | 'recent' | 'stale';

export function freshnessTier(iso: string, now: Date = new Date()): FreshnessTier {
  const then = new Date(iso);
  if (Number.isNaN(then.getTime())) return 'stale';
  const hours = (now.getTime() - then.getTime()) / 3_600_000;
  if (hours < 1) return 'fresh';
  if (hours < 24) return 'recent';
  return 'stale';
}

/**
 * Build a short preview of the most recent assistant content (or
 * fallback to the conversation title). Used by the sidebar's
 * conversation cards.
 */
export function previewSnippet(text: string, max: number = 100): string {
  const clean = text.replace(/\s+/g, ' ').trim();
  if (clean.length <= max) return clean;
  return clean.slice(0, max - 1).trimEnd() + '…';
}
