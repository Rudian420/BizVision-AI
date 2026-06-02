/**
 * Sustainability display formatters + pillar metadata.
 *
 * Kept here so the test suite can verify them without rendering
 * React. Same posture as `lib/forecasting/format.ts` and
 * `lib/pricing/format.ts`.
 */

import type { Pillar } from './types';

/** Map a 0..100 ESG sub-score to a labelled tier. */
export type ScoreTier = 'strong' | 'above average' | 'below average' | 'critical';

export function scoreTier(score: number): ScoreTier {
  if (!Number.isFinite(score)) return 'critical';
  if (score >= 75) return 'strong';
  if (score >= 55) return 'above average';
  if (score >= 35) return 'below average';
  return 'critical';
}

/** Tailwind text-colour utility for a score tier. */
export function scoreTierTone(score: number): string {
  const tier = scoreTier(score);
  switch (tier) {
    case 'strong':
      return 'text-emerald';
    case 'above average':
      return 'text-cyan';
    case 'below average':
      return 'text-gold';
    case 'critical':
      return 'text-coral';
  }
}

/** Per-pillar metadata — glyph + accent colour + display label. */
export type PillarMeta = {
  id: Pillar;
  label: string;
  glyph: string;
  accent: string;
};

export const PILLAR_META: Readonly<Record<Pillar, PillarMeta>> = {
  environmental: { id: 'environmental', label: 'Environmental', glyph: '◯', accent: '#10F07C' },
  social: { id: 'social', label: 'Social', glyph: '◇', accent: '#00F5FF' },
  governance: { id: 'governance', label: 'Governance', glyph: '□', accent: '#FFB800' },
} as const;

/** Stable iteration order — matches the backend's E/S/G convention. */
export const PILLAR_ORDER: readonly Pillar[] = ['environmental', 'social', 'governance'] as const;

/**
 * Compute the percentage width (0..100) for a CSS bar gauge given a
 * 0..100 score. Clamps to the [0, 100] interval so a server returning
 * an out-of-range value doesn't overflow the rendered bar.
 */
export function pillarBarPercent(score: number): number {
  if (!Number.isFinite(score)) return 0;
  return Math.max(0, Math.min(100, score));
}

/**
 * Two-decimal score with an em-dash fallback for invalid input.
 * Distinct from `formatPercent` because ESG sub-scores are already
 * on a 0..100 scale.
 */
export function formatScore(score: number, digits = 1): string {
  if (!Number.isFinite(score)) return '—';
  return score.toFixed(digits);
}

/** Compact label for the regulatory-risk-flag chip. */
export function regulatoryRiskLabel(flag: boolean): string {
  return flag ? 'regulatory risk' : 'within compliance';
}
